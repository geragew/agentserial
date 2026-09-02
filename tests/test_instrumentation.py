from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agentserial import InstrumentationPolicy, Instrumentor, TraceRecorder, current_operation
from agentserial.jsonl_adapter import import_jsonl


def recorder(tmp_path: Path, history_id: str = "instrumented") -> TraceRecorder:
    return TraceRecorder(
        tmp_path / f"{history_id}.jsonl",
        history_id,
        {"balance": (10, 0), "rows": ([], 0)},
    )


def test_operation_decorator_maps_sanitized_call_data(tmp_path: Path) -> None:
    trace_recorder = recorder(tmp_path)
    instrument = Instrumentor(trace_recorder)
    observed: dict[str, object] = {}

    def before(operation, call) -> None:
        observed.update(call.kwargs)
        operation.read("balance", 10, 0)

    def after(operation, call, result) -> None:
        observed["result"] = result
        operation.effect("increment", "balance", -call.kwargs["amount"])

    @instrument.operation(
        lambda purchase_id, **_: f"purchase-{purchase_id}", "billing", before=before, after=after
    )
    def purchase(purchase_id: str, *, amount: int, api_key: str) -> dict[str, object]:
        return {"accepted": True, "token": api_key}

    assert purchase("42", amount=4, api_key="private") == {"accepted": True, "token": "private"}
    assert observed == {
        "amount": 4,
        "api_key": "[REDACTED]",
        "result": {"accepted": True, "token": "[REDACTED]"},
    }

    history = import_jsonl(trace_recorder.path)
    assert history.operations[0].id == "purchase-42"
    assert history.operations[0].reads[0].resource == "balance"
    assert history.operations[0].effects[0].value == -4


def test_failed_decorated_call_discards_effects_and_preserves_error(tmp_path: Path) -> None:
    trace_recorder = recorder(tmp_path, "failure")
    instrument = Instrumentor(trace_recorder)

    def before(operation, call) -> None:
        operation.effect("increment", "balance", -1)

    @instrument.tool("provider-call", "agent", before=before)
    def fail() -> None:
        raise LookupError("provider failed")

    with pytest.raises(LookupError, match="provider failed"):
        fail()

    operation = import_jsonl(trace_recorder.path).operations[0]
    assert operation.status == "failure"
    assert operation.effects == []


def test_async_context_is_isolated_and_available_to_nested_coroutines(tmp_path: Path) -> None:
    trace_recorder = recorder(tmp_path, "async")
    instrument = Instrumentor(trace_recorder)

    async def add_effect(value: int) -> str:
        await asyncio.sleep(0)
        current_operation().effect("append", "rows", value)
        return current_operation().operation_id

    @instrument.operation(lambda value: f"async-{value}", "worker")
    async def work(value: int) -> str:
        return await add_effect(value)

    async def run() -> list[str]:
        return await asyncio.gather(work(1), work(2))

    assert asyncio.run(run()) == ["async-1", "async-2"]
    history = import_jsonl(trace_recorder.path)
    assert {operation.id for operation in history.operations} == {"async-1", "async-2"}
    assert {operation.effects[0].value for operation in history.operations} == {1, 2}


def test_duplicate_wrapper_does_not_duplicate_recursive_operation(tmp_path: Path) -> None:
    trace_recorder = recorder(tmp_path, "recursive")
    instrument = Instrumentor(trace_recorder)

    @instrument.operation("recursive-call", "agent")
    def recurse(depth: int) -> int:
        return depth if depth == 0 else recurse(depth - 1)

    assert recurse(3) == 0
    assert [operation.id for operation in import_jsonl(trace_recorder.path).operations] == ["recursive-call"]


def test_http_and_database_wrappers_require_explicit_semantic_mapping(tmp_path: Path) -> None:
    trace_recorder = recorder(tmp_path, "wrappers")
    instrument = Instrumentor(trace_recorder)

    @instrument.http(
        "http-balance",
        "api-agent",
        response=lambda operation, call, result: operation.read(
            "balance", result["balance"], result["version"]
        ),
    )
    def fetch_balance() -> dict[str, int]:
        return {"balance": 10, "version": 0}

    @instrument.database(
        "insert-row",
        "storage-agent",
        result=lambda operation, call, result: operation.effect("append", "rows", result["id"]),
    )
    def insert_row() -> dict[str, int]:
        return {"id": 7}

    fetch_balance()
    insert_row()
    operations = import_jsonl(trace_recorder.path).operations
    assert operations[0].reads[0].value == 10
    assert operations[1].effects[0].value == 7


def test_policy_bounds_payload_before_function_execution(tmp_path: Path) -> None:
    instrument = Instrumentor(
        recorder(tmp_path, "bounded"), policy=InstrumentationPolicy(max_payload_bytes=20)
    )
    called = False

    @instrument.operation("bounded-call", "agent")
    def bounded(payload: str) -> None:
        nonlocal called
        called = True

    with pytest.raises(ValueError, match="payload exceeds"):
        bounded("x" * 100)
    assert called is False


@pytest.mark.parametrize("payload", [{"value": float("nan")}, {1: "first", "1": "second"}])
def test_policy_rejects_non_json_or_ambiguous_payload(payload: object) -> None:
    with pytest.raises(ValueError):
        InstrumentationPolicy().sanitize(payload)


def test_current_operation_fails_outside_instrumented_call() -> None:
    with pytest.raises(RuntimeError, match="no AgentSerial operation"):
        current_operation()
