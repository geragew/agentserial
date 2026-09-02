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

## 1. Framework integrations

**Goal:** let teams record AgentSerial histories from popular agent frameworks
with a few lines of configuration and without rewriting application logic.

### Shared integration foundation

- [ ] `INT-001` Define a small adapter protocol for runs, agents, tool calls,
  state reads, effects, messages, and errors.
- [ ] `INT-002` Define stable semantic attributes shared by every adapter.
- [ ] `INT-003` Add adapter contract tests with framework-neutral fixtures.
- [ ] `INT-004` Add redaction hooks before framework data reaches a recorder.
- [ ] `INT-005` Add a compatibility matrix for supported framework versions.
- [ ] `INT-006` Document the integration lifecycle and maintainer policy.

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
- Framework upgrades are tested through a documented compatibility matrix.
- Removing an optional framework dependency does not break the core package.

**Dependencies:** initiatives 2 and 3 improve distribution and automatic
capture, but the shared adapter contract can be implemented immediately.

## 2. Official package distribution

**Goal:** make installation predictable through standard package registries.

- [ ] `PKG-001` Reserve and validate the Python package name on PyPI.
- [ ] `PKG-002` Automate signed Python builds and Trusted Publishing.
- [ ] `PKG-003` Reserve and validate the JavaScript package name on npm.
- [ ] `PKG-004` Automate provenance-enabled npm publishing.
- [ ] `PKG-005` Verify fresh installs on Windows, Linux, and macOS.
- [ ] `PKG-006` Add release notes, upgrade guidance, and rollback instructions.
- [ ] `PKG-007` Block releases when package contents or smoke tests fail.

**Acceptance criteria:** `pip install agentserial` and the documented npm
install command work in clean environments and reproduce the release artifacts.

## 3. Automatic instrumentation

**Goal:** capture relevant behavior without manual event construction.

- [ ] `AUTO-001` Define decorators and context managers for agents and tools.
- [ ] `AUTO-002` Add wrappers for HTTP requests and responses.
- [ ] `AUTO-003` Add wrappers for database reads and writes.
- [ ] `AUTO-004` Propagate run and correlation context across async boundaries.
- [ ] `AUTO-005` Add configurable payload redaction and size limits.
- [ ] `AUTO-006` Detect duplicate instrumentation and prevent duplicate events.
- [ ] `AUTO-007` Benchmark runtime, memory, and serialized-size overhead.

**Acceptance criteria:** common sync and async workflows are captured with one
setup call, secrets are redacted by default, and overhead limits are published.

## 4. Generic OpenTelemetry mapping

**Goal:** convert existing telemetry into useful histories without requiring a
vendor-specific trace layout.

- [ ] `OTEL-001` Define a declarative mapping schema for spans and attributes.
- [ ] `OTEL-002` Map span relationships, events, status, links, and resources.
- [ ] `OTEL-003` Support configurable agent, operation, resource, and effect rules.
- [ ] `OTEL-004` Validate mappings with actionable, line-specific diagnostics.
- [ ] `OTEL-005` Ship presets for common semantic conventions.
- [ ] `OTEL-006` Add fixtures from multiple collectors and observability vendors.
- [ ] `OTEL-007` Document loss of information and ambiguous mappings.

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

**Acceptance criteria:** every case is deterministic, runnable from a clean
checkout, initially demonstrates the failure, and includes a verified repair.

## Delivery order

Work starts with initiative 1 as requested. The smallest useful delivery is:

1. Complete `INT-001` through `INT-006` for the shared adapter foundation.
2. Complete `INT-101` through `INT-107` for the LangGraph integration.
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
