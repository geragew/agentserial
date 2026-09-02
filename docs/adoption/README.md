# AgentSerial Adoption Plan

This document turns the product-improvement roadmap into an executable backlog.
It is intentionally tracked by Git; `.gitignore` is only for excluding files and
must not contain project documentation.

## Working agreement

- `[ ]` means not started, `[x]` means completed.
- Every task must include automated tests where behavior changes.
- An initiative is complete only when its acceptance criteria are demonstrable.
- Public APIs require documentation, examples, and compatibility tests.
- Integration-specific code must stay outside the verification core.

## Data engineering principles

Every initiative must preserve the following system properties:

- **Canonical semantics:** adapters translate source concepts into one documented
  model; they must not silently invent reads, effects, order, or atomicity.
- **Stable identity:** history, operation, event, agent, and resource identifiers
  are deterministic within their documented scope and safe to replay.
- **Deterministic processing:** identical accepted input and configuration produce
  byte-equivalent normalized data and the same verdict.
- **Idempotent ingestion:** retries and duplicate delivery cannot create additional
  logical operations or effects.
- **Explicit time semantics:** event time, ingestion time, causal order, clock
  source, and clock uncertainty are distinct concepts. Wall-clock order is never
  treated as causality without an explicit producer guarantee.
- **Schema evolution:** every persisted or exchanged record has a schema version,
  compatibility policy, migration path, and golden compatibility fixtures.
- **Data quality:** completeness, uniqueness, validity, consistency, and causal
  integrity are measured. Invalid records are rejected or quarantined explicitly.
- **Lineage and provenance:** reports retain the source, adapter version, mapping
  version, transformations, and evidence needed to reproduce a conclusion.
- **Privacy by default:** collection is minimized; secrets and sensitive payloads
  are redacted before persistence, logs, exports, and diagnostic output.
- **Bounded operation:** memory, latency, input size, and state-growth limits are
  documented, observable, and return an explicit inconclusive result when hit.

## 1. Framework integrations

**Goal:** let teams record AgentSerial histories from popular agent frameworks
with a few lines of configuration and without rewriting application logic.

### Shared integration foundation

- [ ] `INT-001` Define a small adapter protocol for runs, agents, tool calls,
  state reads, effects, messages, errors, and source metadata.
- [ ] `INT-002` Define canonical identities, lifecycle states, cardinality,
  nullability, ordering, and atomicity semantics shared by every adapter.
- [ ] `INT-003` Add adapter contract tests with framework-neutral golden fixtures,
  including retries, duplicates, late events, missing events, and invalid order.
- [ ] `INT-004` Add redaction hooks before framework data reaches a recorder.
- [ ] `INT-005` Add a compatibility matrix for supported framework versions.
- [ ] `INT-006` Document the integration lifecycle and maintainer policy.
- [ ] `INT-007` Define a versioned adapter envelope containing source framework,
  adapter version, mapping version, capture time, and producer instance.
- [ ] `INT-008` Specify deterministic deduplication keys and collision behavior.
- [ ] `INT-009` Define explicit loss accounting for unmapped source events.

### LangGraph, first delivery

- [ ] `INT-101` Inspect LangGraph callback and event-stream APIs and record the
  minimum supported version.
- [ ] `INT-102` Implement a LangGraph adapter using the shared protocol.
- [ ] `INT-103` Capture graph runs, nodes, tool calls, state access, and errors.
- [ ] `INT-104` Add a runnable multi-agent LangGraph example with a contract.
- [ ] `INT-105` Add unit, compatibility, and end-to-end verification tests.
- [ ] `INT-106` Document installation and a copy-paste quick start.
- [ ] `INT-107` Publish the adapter as an optional dependency and verify a clean
  installation in CI.
- [ ] `INT-108` Verify checkpoint replay, resumed runs, parallel branches, and
  duplicate callback delivery without duplicating logical effects.

### OpenAI Agents SDK

- [ ] `INT-201` Map agents, handoffs, tools, guardrails, and traces.
- [ ] `INT-202` Implement the adapter without requiring application changes.
- [ ] `INT-203` Add a runnable handoff example and end-to-end tests.
- [ ] `INT-204` Document version support, limitations, and redaction behavior.

### AutoGen

- [ ] `INT-301` Map conversations, agents, tool execution, and termination.
- [ ] `INT-302` Implement the adapter and lifecycle hooks.
- [ ] `INT-303` Add a runnable multi-agent example and end-to-end tests.
- [ ] `INT-304` Document version support and unsupported event types.

### CrewAI

- [ ] `INT-401` Map crews, agents, tasks, tools, and delegation.
- [ ] `INT-402` Implement the adapter and lifecycle hooks.
- [ ] `INT-403` Add a runnable delegated-task example and end-to-end tests.
- [ ] `INT-404` Document version support and unsupported event types.

**Acceptance criteria**

- A new user instruments each supported framework in five lines or fewer,
  excluding imports and secrets.
- All adapters emit the same canonical AgentSerial history format.
- Replaying the same captured run produces the same normalized history.
- Every dropped, inferred, or lossy mapping is counted and reported.
- Framework upgrades are tested through a documented compatibility matrix.
- Removing an optional framework dependency does not break the core package.

**Dependencies:** initiatives 2 and 3 improve distribution and automatic
capture, but the shared adapter contract can be implemented immediately.

## 2. Official package distribution

**Goal:** make installation predictable through standard package registries.

- [ ] `PKG-001` Reserve and validate the Python package name on PyPI.
- [x] `PKG-002` Automate signed Python builds and Trusted Publishing.
- [ ] `PKG-003` Reserve and validate the JavaScript package name on npm.
- [x] `PKG-004` Automate provenance-enabled npm publishing.
- [x] `PKG-005` Verify fresh installs on Windows, Linux, and macOS.
- [x] `PKG-006` Add release notes, upgrade guidance, and rollback instructions.
- [x] `PKG-007` Block releases when package contents or smoke tests fail.
- [x] `PKG-008` Publish an artifact manifest with checksums, schema compatibility,
  supported runtimes, and software bill of materials.

**Acceptance criteria:** `pip install agentserial` and the documented npm
install command work in clean environments and reproduce the release artifacts.

## 3. Automatic instrumentation

**Goal:** capture relevant behavior without manual event construction.

- [x] `AUTO-001` Define decorators and context managers for agents and tools.
- [x] `AUTO-002` Add wrappers for HTTP requests and responses.
- [x] `AUTO-003` Add wrappers for database reads and writes.
- [x] `AUTO-004` Propagate run and correlation context across async boundaries.
- [x] `AUTO-005` Add configurable payload redaction and size limits.
- [x] `AUTO-006` Detect duplicate instrumentation and prevent duplicate events.
- [x] `AUTO-007` Benchmark runtime, memory, and serialized-size overhead.
- [x] `AUTO-008` Define backpressure, buffering, flush, retry, and shutdown
  guarantees for process failure and high-volume capture.
- [ ] `AUTO-009` Test deterministic deduplication across process and transport
  retries without suppressing distinct operations.

**Acceptance criteria:** common sync and async workflows are captured with one
setup call, secrets are redacted by default, and overhead limits are published.

## 4. Generic OpenTelemetry mapping

**Goal:** convert existing telemetry into useful histories without requiring a
vendor-specific trace layout.

- [x] `OTEL-001` Define a declarative mapping schema for spans and attributes.
- [x] `OTEL-002` Map span relationships, events, status, links, and resources.
- [x] `OTEL-003` Support configurable agent, operation, resource, and effect rules.
- [x] `OTEL-004` Validate mappings with actionable, line-specific diagnostics.
- [ ] `OTEL-005` Ship presets for common semantic conventions.
- [ ] `OTEL-006` Add fixtures from multiple collectors and observability vendors.
- [x] `OTEL-007` Document loss of information and ambiguous mappings.
- [x] `OTEL-008` Preserve trace/span identity and distinguish event time from
  ingestion time without deriving causal order from timestamps alone.
- [x] `OTEL-009` Version and fingerprint mapping configurations in output lineage.

**Acceptance criteria:** users can adapt an existing trace through configuration,
and conversion reports every dropped or unresolved field.

## 5. Visual contract editor

**Goal:** let non-specialists build and validate invariants without writing YAML.

- [ ] `UI-001` Model editor state independently from the DOM.
- [ ] `UI-002` Add guided controls for scopes, resources, limits, and ordering.
- [ ] `UI-003` Provide live validation with field-level error messages.
- [ ] `UI-004` Import existing YAML without losing supported semantics.
- [ ] `UI-005` Export deterministic, human-readable YAML.
- [ ] `UI-006` Add accessible keyboard navigation and screen-reader labels.
- [ ] `UI-007` Add browser tests for create, edit, import, and export flows.
- [ ] `UI-008` Preserve contract schema versions and require an explicit migration
  preview before applying incompatible edits.

**Acceptance criteria:** a user can create, inspect, edit, and export a valid
contract from the browser without learning the YAML schema first.

## 6. Guided import experience

**Goal:** make trace ingestion understandable and recoverable for ordinary users.

- [ ] `IMP-001` Add drag-and-drop and file-picker import.
- [ ] `IMP-002` Detect supported formats and explain unsupported inputs.
- [ ] `IMP-003` Show line- or event-level errors with suggested corrections.
- [ ] `IMP-004` Preview normalized agents, operations, and resources.
- [ ] `IMP-005` Let users download the converted AgentSerial history.
- [ ] `IMP-006` Recommend the closest bundled example for failed imports.
- [ ] `IMP-007` Keep all local-file processing private by default.
- [ ] `IMP-008` Produce a data-quality summary for accepted, rejected, duplicate,
  incomplete, late, and unmapped records.
- [ ] `IMP-009` Quarantine invalid records with stable error codes and provenance.
- [ ] `IMP-010` Guarantee deterministic output for repeated imports of the same
  content and mapping configuration.

**Acceptance criteria:** a first-time user can import a supported trace, correct
problems, inspect the normalized result, and download it in one guided flow.

## 7. CI/CD integration

**Goal:** make concurrency-contract verification a normal pull-request check.

- [ ] `CI-001` Build an official GitHub Action with pinned runtime dependencies.
- [ ] `CI-002` Accept histories, contracts, configuration, and failure policy.
- [ ] `CI-003` Publish a concise job summary and machine-readable report.
- [ ] `CI-004` Add source annotations for actionable failures where possible.
- [ ] `CI-005` Document required-check and branch-protection setup.
- [ ] `CI-006` Add a versioning and deprecation policy for action inputs.
- [ ] `CI-007` Test the action in a separate consumer fixture repository.
- [ ] `CI-008` Emit versioned SARIF or equivalent machine-readable diagnostics
  with stable rule identifiers and artifact provenance.

**Acceptance criteria:** a repository can block a pull request on a violated
contract using one documented workflow step and a pinned AgentSerial version.

## 8. Scalable verification

**Goal:** analyze substantially larger concurrent histories while preserving
sound, explainable results.

- [ ] `SCALE-001` Establish benchmark datasets and performance budgets.
- [ ] `SCALE-002` Model independence between operations and resources.
- [ ] `SCALE-003` Implement partial-order reduction behind a feature flag.
- [ ] `SCALE-004` Cache equivalent verification states deterministically.
- [ ] `SCALE-005` Add bounded-search controls and explicit incomplete results.
- [ ] `SCALE-006` Evaluate SAT/SMT encoding against current algorithms.
- [ ] `SCALE-007` Publish complexity limits and benchmark regressions in CI.
- [ ] `SCALE-008` Benchmark skewed resource cardinality, dense causal graphs,
  duplicate delivery, and adversarial histories rather than average cases only.
- [ ] `SCALE-009` Measure peak memory, state count, throughput, and tail latency
  with reproducible datasets and fixed hardware metadata.

**Acceptance criteria:** larger reference histories meet published budgets, and
the engine never presents a bounded or incomplete search as a proof.

## 9. Provenance and coverage

**Goal:** show users which conclusions are justified by observed evidence.

- [ ] `COV-001` Define coverage for agents, tools, resources, and event classes.
- [ ] `COV-002` Record instrumentation source and confidence metadata.
- [ ] `COV-003` Detect missing intervals, participants, and causal context.
- [ ] `COV-004` Surface coverage warnings in CLI, API, and browser reports.
- [ ] `COV-005` Prevent strong conclusions when required evidence is absent.
- [ ] `COV-006` Add coverage thresholds to contracts and CI configuration.
- [ ] `COV-007` Test partial, duplicated, reordered, and corrupted telemetry.
- [ ] `COV-008` Define a versioned lineage record from raw source through mapping,
  normalization, verification, and report generation.
- [ ] `COV-009` Add quality metrics with documented denominators and `unknown`
  states so missing evidence is never represented as zero.

**Acceptance criteria:** every report distinguishes observed facts, inferred
relationships, and evidence gaps, with consistent results across interfaces.

## 10. Reproducible real-world cases

**Goal:** demonstrate practical value with failures users recognize and can run.

- [ ] `CASE-001` Add a payment double-spend case.
- [ ] `CASE-002` Add an inventory oversell case.
- [ ] `CASE-003` Add a duplicate booking case.
- [ ] `CASE-004` Add a stale authorization or permission case.
- [ ] `CASE-005` Add a conflicting deployment case.
- [ ] `CASE-006` Include failing trace, contract, minimal counterexample, and fix.
- [ ] `CASE-007` Validate every case in CI and document expected output.
- [ ] `CASE-008` Add an index organized by industry, failure, and invariant.
- [ ] `CASE-009` Include duplicate, late, missing, malformed, and schema-migration
  variants for each applicable domain case.
- [ ] `CASE-010` Pin generators, seeds, expected fingerprints, and benchmark
  metadata so cases remain reproducible across releases.

**Acceptance criteria:** every case is deterministic, runnable from a clean
checkout, initially demonstrates the failure, and includes a verified repair.

## Delivery order

Work starts with initiative 1 as requested. The smallest useful delivery is:

1. Complete `INT-001` through `INT-009` for the shared adapter foundation.
2. Complete `INT-101` through `INT-108` for the LangGraph integration.
3. Complete initiative 2 so adapters can be installed from registries.
4. Complete initiative 7 so projects can enforce contracts in pull requests.
5. Deliver the remaining framework adapters in measured adoption order.
6. Add automatic instrumentation and generic OpenTelemetry mapping.
7. Improve the browser workflow through initiatives 5 and 6.
8. Expand engine scale, evidence coverage, and real-world proof cases.

## Definition of done

A task is done only when its implementation, tests, documentation, failure
behavior, and compatibility impact have been reviewed. An initiative is done
only when its acceptance criteria pass in CI and from a clean user environment.
Any change to persisted data or public events must also include schema impact,
migration behavior, golden old-reader/new-writer and new-reader/old-writer tests,
lineage impact, quality metrics, operational limits, and rollback instructions.
