from __future__ import annotations

import argparse
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter

from agentserial import Instrumentor, TraceRecorder, current_operation


def benchmark(operations: int) -> tuple[float, int, int]:
    with tempfile.TemporaryDirectory(prefix="agentserial-instrumentation-") as directory:
        trace = Path(directory) / "events.jsonl"
        instrument = Instrumentor(TraceRecorder(trace, "benchmark", {"values": ([], 0)}))

        @instrument.operation(lambda value: f"operation-{value}", "benchmark-agent")
        def record(value: int) -> None:
            current_operation().effect("append", "values", value)

        tracemalloc.start()
        started = perf_counter()
        for value in range(operations):
            record(value)
        elapsed = perf_counter() - started
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return elapsed, peak_memory, trace.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark automatic instrumentation")
    parser.add_argument("--operations", type=int, default=1_000)
    parser.add_argument("--assert-max-seconds", type=float)
    arguments = parser.parse_args()
    if arguments.operations < 1:
        parser.error("--operations must be positive")

    elapsed, peak_memory, size = benchmark(arguments.operations)
    throughput = arguments.operations / elapsed
    print(f"operations: {arguments.operations}")
    print(f"seconds: {elapsed:.6f}")
    print(f"operations_per_second: {throughput:.2f}")
    print(f"peak_memory_bytes: {peak_memory}")
    print(f"trace_bytes: {size}")
    if arguments.assert_max_seconds is not None and elapsed > arguments.assert_max_seconds:
        parser.error(f"instrumentation exceeded {arguments.assert_max_seconds:.3f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
