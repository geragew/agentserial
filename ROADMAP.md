# Roadmap

The detailed, task-level adoption backlog is maintained in
[`docs/adoption/README.md`](docs/adoption/README.md).

## Delivered through v0.7

Strict schemas, exhaustive contract replay classification, four invariant types,
safe and unsafe witnesses, memoized replay, deterministic 1-minimal reduction,
CLI, local API, zero-configuration workspace, JSONL recording, OpenTelemetry
import, Python and JavaScript recording SDKs, standalone reports, containers,
and cross-version CI.

## Next engineering milestones

- Partial-order and logical-clock ingestion.
- Provenance and instrumentation coverage metadata.
- Explicit external-effect outcomes and idempotency keys.
- Partial-order reduction and dependency-graph analysis.
- SAT/SMT-backed checking for larger histories.
- Published compatibility fixtures for trace producers.
- Resource-bounded worker isolation for untrusted API workloads.

Live enforcement, orchestration, and hosted services remain outside the current
correctness-checking boundary.
