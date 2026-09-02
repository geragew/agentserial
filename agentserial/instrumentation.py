from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from agentserial.recorder import OperationCapture, TraceRecorder

P = ParamSpec("P")
R = TypeVar("R")
Identifier = str | Callable[..., str]
BeforeHook = Callable[[OperationCapture, "CallData"], None]
AfterHook = Callable[[OperationCapture, "CallData", Any], None]


@dataclass(frozen=True, slots=True)
class CallData:
    """Sanitized invocation data exposed to explicit semantic mapping hooks."""

    args: tuple[Any, ...]
    kwargs: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class InstrumentationPolicy:
    """Privacy and resource limits applied before call data reaches hooks."""

    max_payload_bytes: int = 65_536
    sensitive_keys: tuple[str, ...] = (
        "api_key",
        "authorization",
        "cookie",
        "password",
        "secret",
        "token",
    )
    replacement: str = "[REDACTED]"

    def __post_init__(self) -> None:
        if self.max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be positive")
        if not self.replacement:
            raise ValueError("replacement must be a non-empty string")

    def sanitize(self, value: Any) -> Any:
        sanitized = _sanitize(value, self.sensitive_keys, self.replacement)
        encoded = json.dumps(sanitized, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > self.max_payload_bytes:
            raise ValueError(f"instrumentation payload exceeds {self.max_payload_bytes} bytes")
        return sanitized


_active_keys: ContextVar[frozenset[str]] = ContextVar(
    "agentserial_active_instrumentation", default=frozenset()
)
_current_capture: ContextVar[OperationCapture | None] = ContextVar(
    "agentserial_current_capture", default=None
)


def current_operation() -> OperationCapture:
    """Return the operation active in the current thread or async task."""

    operation = _current_capture.get()
    if operation is None:
        raise RuntimeError("no AgentSerial operation is active")
    return operation


class Instrumentor:
    """Adds deterministic operation capture around synchronous or async calls."""

    def __init__(self, recorder: TraceRecorder, *, policy: InstrumentationPolicy | None = None) -> None:
        self.recorder = recorder
        self.policy = policy or InstrumentationPolicy()

    def operation(
        self,
        operation_id: Identifier,
        agent: Identifier,
        *,
        before: BeforeHook | None = None,
        after: AfterHook | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return self._decorate(operation_id, agent, before=before, after=after)

    def tool(
        self,
        operation_id: Identifier,
        agent: Identifier,
        *,
        before: BeforeHook | None = None,
        after: AfterHook | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return self._decorate(operation_id, agent, before=before, after=after)

    def http(
        self,
        operation_id: Identifier,
        agent: Identifier,
        *,
        request: BeforeHook | None = None,
        response: AfterHook | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return self._decorate(operation_id, agent, before=request, after=response)

    def database(
        self,
        operation_id: Identifier,
        agent: Identifier,
        *,
        query: BeforeHook | None = None,
        result: AfterHook | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return self._decorate(operation_id, agent, before=query, after=result)

    def _decorate(
        self,
        operation_id: Identifier,
        agent: Identifier,
        *,
        before: BeforeHook | None,
        after: AfterHook | None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def decorator(function: Callable[P, R]) -> Callable[P, R]:
            key = f"{function.__module__}.{function.__qualname__}"
            if inspect.iscoroutinefunction(function):

                @wraps(function)
                async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                    if key in _active_keys.get():
                        return await function(*args, **kwargs)
                    return await self._capture_async(
                        key, function, operation_id, agent, before, after, args, kwargs
                    )

                return cast(Callable[P, R], async_wrapper)

            @wraps(function)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if key in _active_keys.get():
                    return function(*args, **kwargs)
                return self._capture(key, function, operation_id, agent, before, after, args, kwargs)

            return wrapper

        return decorator

    def _capture(
        self,
        key: str,
        function: Callable[P, R],
        operation_id: Identifier,
        agent: Identifier,
        before: BeforeHook | None,
        after: AfterHook | None,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> R:
        call = self._call_data(args, kwargs)
        with self.recorder.operation(
            _resolve(operation_id, args, kwargs), _resolve(agent, args, kwargs)
        ) as op:
            tokens = _activate(key, op)
            try:
                if before:
                    before(op, call)
                result = function(*args, **kwargs)
                if after:
                    after(op, call, self.policy.sanitize(result))
                return result
            finally:
                _deactivate(tokens)

    async def _capture_async(
        self,
        key: str,
        function: Callable[P, Any],
        operation_id: Identifier,
        agent: Identifier,
        before: BeforeHook | None,
        after: AfterHook | None,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        call = self._call_data(args, kwargs)
        with self.recorder.operation(
            _resolve(operation_id, args, kwargs), _resolve(agent, args, kwargs)
        ) as op:
            tokens = _activate(key, op)
            try:
                if before:
                    before(op, call)
                result = await function(*args, **kwargs)
                if after:
                    after(op, call, self.policy.sanitize(result))
                return result
            finally:
                _deactivate(tokens)

    def _call_data(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> CallData:
        sanitized = self.policy.sanitize({"args": args, "kwargs": kwargs})
        return CallData(tuple(sanitized["args"]), sanitized["kwargs"])


def _resolve(value: Identifier, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    return value(*args, **kwargs) if callable(value) else value


def _activate(
    key: str, operation: OperationCapture
) -> tuple[Token[frozenset[str]], Token[OperationCapture | None]]:
    keys_token = _active_keys.set(_active_keys.get() | {key})
    operation_token = _current_capture.set(operation)
    return keys_token, operation_token


def _deactivate(tokens: tuple[Token[frozenset[str]], Token[OperationCapture | None]]) -> None:
    _current_capture.reset(tokens[1])
    _active_keys.reset(tokens[0])


def _sanitize(value: Any, sensitive_keys: tuple[str, ...], replacement: str) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if normalized_key in sanitized:
                raise ValueError(f"payload keys collide after normalization: {normalized_key!r}")
            sanitized[normalized_key] = (
                replacement
                if any(marker in normalized_key.casefold() for marker in sensitive_keys)
                else _sanitize(item, sensitive_keys, replacement)
            )
        return sanitized
    if isinstance(value, list | tuple):
        return [_sanitize(item, sensitive_keys, replacement) for item in value]
    return f"<{type(value).__name__}>"
