from __future__ import annotations

import json
from contextlib import AbstractContextManager
from pathlib import Path
from threading import Lock
from types import TracebackType
from typing import Any, Literal, Self

from agentserial.models import JsonValue


class TraceRecorder:
    """Thread-safe JSONL recorder for runtime integrations."""

    def __init__(
        self,
        path: Path | str,
        history_id: str,
        initial_state: dict[str, tuple[JsonValue, int]],
        *,
        overwrite: bool = False,
    ) -> None:
        self.path = Path(path)
        self._lock = Lock()
        if self.path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        events = [{"event": "history", "history_id": history_id, "schema_version": "0.1"}]
        events.extend(
            {"event": "resource", "resource": name, "value": value, "version": version}
            for name, (value, version) in initial_state.items()
        )
        self._write(events, mode="w")

    def operation(self, operation_id: str, agent: str) -> OperationCapture:
        return OperationCapture(self, operation_id, agent)

    def order(self, before: str, after: str) -> None:
        self._write([{"event": "order", "before": before, "after": after}])

    def _write(self, events: list[dict[str, Any]], *, mode: str = "a") -> None:
        with self._lock, self.path.open(mode, encoding="utf-8", newline="\n") as stream:
            for event in events:
                stream.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")


class OperationCapture(AbstractContextManager["OperationCapture"]):
    def __init__(self, recorder: TraceRecorder, operation_id: str, agent: str) -> None:
        self.recorder = recorder
        self.operation_id = operation_id
        self.agent = agent
        self._events: list[dict[str, Any]] = []
        self._closed = False

    def read(self, resource: str, value: JsonValue, version: int) -> Self:
        self._ensure_open()
        self._events.append(
            {
                "event": "read",
                "operation": self.operation_id,
                "resource": resource,
                "value": value,
                "version": version,
            }
        )
        return self

    def effect(
        self,
        effect_type: Literal["set", "increment", "append"],
        resource: str,
        value: JsonValue,
    ) -> Self:
        self._ensure_open()
        self._events.append(
            {
                "event": "effect",
                "operation": self.operation_id,
                "type": effect_type,
                "resource": resource,
                "value": value,
            }
        )
        return self

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._ensure_open()
        self._closed = True
        status = "failure" if exc_type else "success"
        start = {"event": "operation_start", "operation": self.operation_id, "agent": self.agent}
        events = [start]
        if status == "success":
            events.extend(self._events)
        events.append({"event": "operation_end", "operation": self.operation_id, "status": status})
        self.recorder._write(events)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("operation capture is already closed")
