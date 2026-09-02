from __future__ import annotations

import asyncio
import os
import secrets
from collections import defaultdict, deque
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from time import monotonic
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentserial import __version__
from agentserial.checker import check
from agentserial.invariants import validate_contract_effects, validate_contract_resources
from agentserial.models import CheckResult, Contract, History, StrictModel
from agentserial.parsing import parse_document


class CheckRequest(StrictModel):
    history: History
    contract: Contract
    max_operations: int = Field(default=10, ge=1, le=100)
    max_prefixes: int = Field(default=100_000, ge=1, le=10_000_000)


class ValidationResponse(StrictModel):
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class ApiSettings:
    api_key: str | None = None
    max_body_bytes: int = 2_000_000
    timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 120
    cors_origins: tuple[str, ...] = ("http://localhost", "http://127.0.0.1", "null")

    def __post_init__(self) -> None:
        if self.max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.rate_limit_per_minute < 0:
            raise ValueError("rate_limit_per_minute cannot be negative")

    @classmethod
    def from_environment(cls) -> ApiSettings:
        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "AGENTSERIAL_CORS_ORIGINS", "http://localhost,http://127.0.0.1,null"
            ).split(",")
            if origin.strip()
        )
        return cls(
            api_key=os.getenv("AGENTSERIAL_API_KEY") or None,
            max_body_bytes=int(os.getenv("AGENTSERIAL_MAX_BODY_BYTES", "2000000")),
            timeout_seconds=float(os.getenv("AGENTSERIAL_TIMEOUT_SECONDS", "30")),
            rate_limit_per_minute=int(os.getenv("AGENTSERIAL_RATE_LIMIT_PER_MINUTE", "120")),
            cors_origins=origins,
        )


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        content_length = dict(scope.get("headers", [])).get(b"content-length")
        if content_length and int(content_length) > self.max_bytes:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
            await response(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail="request body too large")
            return message

        try:
            await self.app(scope, limited_receive, send)
        except HTTPException as error:
            response = JSONResponse({"detail": error.detail}, status_code=error.status_code)
            await response(scope, receive, send)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_environment()
    application = FastAPI(
        title="AgentSerial API",
        summary="Correctness checks for parallel AI-agent effect histories.",
        description=(
            "Validate recorded agent histories against global contracts and classify "
            "their feasible execution orders. The API is deterministic and does not "
            "call an LLM or external service."
        ),
        version=__version__,
        license_info={"name": "MIT", "identifier": "MIT"},
    )
    application.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-AgentSerial-Key", "X-Request-ID"],
    )
    rate_buckets: dict[str, deque[float]] = defaultdict(deque)
    rate_lock = asyncio.Lock()

    async def authorize(x_agentserial_key: Annotated[str | None, Header()] = None) -> None:
        if settings.api_key and not (
            x_agentserial_key and secrets.compare_digest(x_agentserial_key, settings.api_key)
        ):
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    @application.middleware("http")
    async def operational_controls(request: Any, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        if request.url.path.startswith("/v1/") and settings.rate_limit_per_minute > 0:
            client = request.client.host if request.client else "unknown"
            now = monotonic()
            async with rate_lock:
                bucket = rate_buckets[client]
                while bucket and bucket[0] <= now - 60:
                    bucket.popleft()
                if len(bucket) >= settings.rate_limit_per_minute:
                    response = JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
                    response.headers["Retry-After"] = "60"
                    response.headers["X-Request-ID"] = request_id
                    return response
                bucket.append(now)
        try:
            response = await asyncio.wait_for(call_next(request), timeout=settings.timeout_seconds)
        except TimeoutError:
            response = JSONResponse({"detail": "analysis timed out"}, status_code=504)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    web_directory = Path(str(files("agentserial").joinpath("web")))
    source_web_directory = Path(__file__).parents[1]
    if not web_directory.is_dir() and (source_web_directory / "index.html").is_file():
        web_directory = source_web_directory
    if web_directory.is_dir():
        application.mount("/app", StaticFiles(directory=web_directory, html=True), name="app")

        @application.get("/", include_in_schema=False)
        def application_home() -> RedirectResponse:
            return RedirectResponse("/app/")

    @application.post(
        "/v1/validate",
        response_model=ValidationResponse,
        tags=["analysis"],
        dependencies=[Depends(authorize)],
    )
    def validate_documents(request: CheckRequest) -> ValidationResponse:
        errors = validate_contract_resources(request.contract, request.history.initial_state)
        errors.extend(validate_contract_effects(request.contract, request.history))
        return ValidationResponse(valid=not errors, errors=errors)

    @application.post(
        "/v1/check", response_model=CheckResult, tags=["analysis"], dependencies=[Depends(authorize)]
    )
    def check_history(request: CheckRequest) -> CheckResult:
        return _run_check(request)

    @application.post(
        "/v1/check-files", response_model=CheckResult, tags=["analysis"], dependencies=[Depends(authorize)]
    )
    async def check_files(
        history: Annotated[UploadFile, File(description="History document in JSON or YAML")],
        contract: Annotated[UploadFile, File(description="Contract document in JSON or YAML")],
        max_operations: int = 10,
        max_prefixes: int = 100_000,
    ) -> CheckResult:
        try:
            request = CheckRequest(
                history=History.model_validate(_decode_document(await history.read(), history.filename)),
                contract=Contract.model_validate(_decode_document(await contract.read(), contract.filename)),
                max_operations=max_operations,
                max_prefixes=max_prefixes,
            )
        except (ValueError, ValidationError, UnicodeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return await run_in_threadpool(_run_check, request)

    return application


def _run_check(request: CheckRequest) -> CheckResult:
    return check(
        request.history,
        request.contract,
        max_operations=request.max_operations,
        max_prefixes=request.max_prefixes,
    )


def _decode_document(content: bytes, filename: str | None) -> dict[str, Any]:
    if not content:
        raise ValueError("uploaded document is empty")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValueError("uploaded documents must use .json, .yaml, or .yml")
    return parse_document(content.decode("utf-8"), suffix)


app = create_app()
