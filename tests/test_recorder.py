from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agentserial.jsonl_adapter import import_jsonl
from agentserial.recorder import TraceRecorder


def test_recorder_produces_importable_trace(tmp_path: Path) -> None:
    trace = tmp_path / "events.jsonl"
    recorder = TraceRecorder(trace, "runtime-run", {"balance": (10, 0)})
    with recorder.operation("debit", "billing-agent") as operation:
        operation.read("balance", 10, 0).effect("increment", "balance", -4)
    history = import_jsonl(trace)
    assert history.history_id == "runtime-run"
    assert history.operations[0].effects[0].value == -4


def test_failed_operation_discards_buffered_effects(tmp_path: Path) -> None:
    trace = tmp_path / "events.jsonl"
    recorder = TraceRecorder(trace, "failed-run", {"balance": (10, 0)})
    with pytest.raises(RuntimeError), recorder.operation("debit", "billing-agent") as operation:
        operation.effect("increment", "balance", -4)
        raise RuntimeError("provider failed")
    history = import_jsonl(trace)
    assert history.operations[0].status == "failure"
    assert history.operations[0].effects == []


def test_recorder_is_thread_safe(tmp_path: Path) -> None:
    trace = tmp_path / "events.jsonl"
    recorder = TraceRecorder(trace, "parallel-run", {"events": ([], 0)})

    def record(index: int) -> None:
        with recorder.operation(f"op-{index}", f"agent-{index}") as operation:
            operation.effect("append", "events", index)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(record, range(20)))
    history = import_jsonl(trace)
    assert len(history.operations) == 20
    assert {operation.id for operation in history.operations} == {f"op-{index}" for index in range(20)}
