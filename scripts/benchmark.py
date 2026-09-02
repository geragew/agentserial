from __future__ import annotations

import argparse
from time import perf_counter
from math import factorial

from agentserial.checker import check
from agentserial.models import Contract, History


def benchmark(operation_count: int) -> float:
    history = History.model_validate(
        {
            "schema_version": "0.1",
            "history_id": f"linear-{operation_count}",
            "initial_state": {"counter": {"value": 0, "version": 0}},
            "operations": [
                {
                    "id": f"op-{index}",
                    "agent": f"agent-{index % 4}",
                    "effects": [{"type": "increment", "resource": "counter", "value": 1}],
                }
                for index in range(operation_count)
            ],
            "order": [
                {"before": f"op-{index}", "after": f"op-{index + 1}"}
                for index in range(operation_count - 1)
            ],
        }
    )
    contract = Contract.model_validate(
        {"version": "0.1", "invariants": [{"id": "floor", "type": "min_value", "resource": "counter", "min": 0}]}
    )
    started = perf_counter()
    result = check(history, contract, max_operations=operation_count, shrink=False)
    elapsed = perf_counter() - started
    assert result.status == "ROBUST_PASS"
    return elapsed


def benchmark_unordered(operation_count: int) -> tuple[float, int]:
    history = History.model_validate(
        {
            "schema_version": "0.1",
            "history_id": f"unordered-{operation_count}",
            "initial_state": {"counter": {"value": 0, "version": 0}},
            "operations": [
                {
                    "id": f"op-{index}",
                    "agent": f"agent-{index}",
                    "effects": [{"type": "increment", "resource": "counter", "value": 1}],
                }
                for index in range(operation_count)
            ],
            "order": [],
        }
    )
    contract = Contract.model_validate(
        {"version": "0.1", "invariants": [{"id": "floor", "type": "min_value", "resource": "counter", "min": 0}]}
    )
    started = perf_counter()
    result = check(history, contract, max_operations=operation_count, max_prefixes=100_000, shrink=False)
    elapsed = perf_counter() - started
    assert result.status == "ROBUST_PASS"
    assert result.feasible_replays == factorial(operation_count)
    return elapsed, result.explored_prefixes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assert-max-seconds", type=float)
    args = parser.parse_args()
    timings = {count: benchmark(count) for count in (10, 50, 100)}
    for count, elapsed in timings.items():
        print(f"{count:>3} operations: {elapsed:.4f}s")
    unordered_elapsed, unordered_prefixes = benchmark_unordered(10)
    print(
        f" 10 unordered operations: {unordered_elapsed:.4f}s, "
        f"{factorial(10):,} replays via {unordered_prefixes:,} explored transitions"
    )
    if args.assert_max_seconds and timings[100] > args.assert_max_seconds:
        raise SystemExit(f"100-operation benchmark exceeded {args.assert_max_seconds}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
