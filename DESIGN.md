# AgentSerial v0.1 Technical Design

This document turns `SPEC.md` into a deliberately small implementation plan.

## 1. Technical synthesis

**Problem:** individually successful agent operations can compose into a history
that is inconsistent with recorded observations or violates a global contract.

**Property:** contract replay classification, as defined in `SPEC.md`: classify
all constraint-compatible total orders that reproduce reads by whether they
preserve all invariants at every committed prefix.

**Assumptions:** complete trusted input, atomic successful operations,
deterministic modeled effects, explicit ordering, reliable producer versions,
and small histories.

**Primary risks:** confusing one safe witness with universal safety; implying
formal serializability; treating timestamps as reliable causality; hiding
instrumentation gaps; and claiming global minimum counterexamples from a
1-minimal shrinker.

**Scope:** local parsing, validation, exhaustive replay, four explicit invariant
types, deterministic verdicts, and reduced counterexamples. No runtime,
adapters, network calls, LLMs, dashboard, or external-effect semantics.

## 2. Minimal implementation types

The normative definitions live in `SPEC.md`. The implementation maps them to:

- `History`: schema version, ID, initial resource map, operations, order edges.
- `ResourceState`: scalar/list value and integer version.
- `Operation`: ID, agent, status, reads, ordered effects.
- `Read`: resource, exact value, exact version.
- `Effect`: one of `set`, `increment`, or `append`, plus resource and value.
- `OrderingConstraint`: before and after operation IDs.
- `Contract`: schema version and invariants.
- `Invariant`: tagged union of `max_sum`, `min_value`, `unique`, and `equals`.
- `Verdict`: status, deterministic reason codes, optional safe and unsafe witness
  orders, diagnostics, search counts, and optional reduced counterexample.
- `Counterexample`: retained operations, induced edges, and failure diagnostics.

Models should be strict Pydantic tagged unions. Unknown fields should be rejected
in v0.1 so misspellings cannot silently weaken a contract.

## 3. File structure

```text
agentserial/
  __init__.py
  cli.py
  models.py
  parsing.py
  invariants.py
  replay.py
  checker.py
  shrink.py
  formatting.py
examples/
  01_overspend/
  02_inventory_race/
  03_double_booking/
  04_safe_parallel/
  05_config_mismatch/
  06_permission_stale/README.md
tests/
  test_parsing.py
  test_invariants.py
  test_replay.py
  test_checker.py
  test_shrink.py
  test_examples.py
README.md
SPEC.md
DESIGN.md
PRIOR_ART.md
ROADMAP.md
CONTRIBUTING.md
LICENSE
pyproject.toml
```

Flat modules are sufficient for v0.1. Separate model/parser/engine package trees
would add navigation cost without yet isolating meaningful subsystems.

## 4. Checker algorithm

1. Strictly parse both documents and perform cross-document validation.
2. Record an initially invalid contract state as a violation shared by every
   feasible replay; the input itself remains valid.
3. Compute reachability in the validated ordering DAG, then project it onto
   successful operations so a path through a failed operation still constrains
   its successful endpoints. Build adjacency and indegree tables for that graph.
4. Backtrack over currently zero-indegree operations in lexicographic ID order.
5. For each choice, compare all reads to the current immutable state snapshot.
6. If reads match, apply effects to a copy, increment each touched resource once,
   and accumulate invariant violations without pruning that feasible branch.
7. Prune only on read mismatch. Memoize suffix results by completed-operation
   set, frozen modeled state, resource versions, and accumulated violations.
   Reuse exact completion counts and deterministic suffix witnesses.
8. Count complete safe and unsafe feasible replays and retain one deterministic
   witness of each class.
9. Return `ROBUST_PASS`, `SCHEDULE_DEPENDENT`, `CONTRACT_FAIL`, or
   `INCONSISTENT_HISTORY` from those counts; return `INCONCLUSIVE` if a declared
   search limit is reached before classification completes.

The deterministic branch order makes output reproducible. The CLI should default
to a conservative maximum operation count and maximum explored-prefix count,
both displayed when they cause `INCONCLUSIVE`.

Memoization collapses convergent interleavings, but it does not remove the
factorial worst case when different orders produce distinct modeled states.

## 5. Shrinker algorithm

Use deterministic single-deletion reduction:

1. Start with all successful operations from the failing history.
2. Visit operation IDs in stable order and test the history without one
   operation, retaining only order edges whose endpoints remain.
3. If the target predicate remains true, keep the deletion and restart the scan.
4. Otherwise restore the operation. Never treat `INCONCLUSIVE` as preservation.
5. Stop after a full scan makes no deletion.

The result is 1-minimal relative to this deletion predicate, not globally
minimum. Failed operations can remain available as display context but do not
belong to the semantic counterexample.

A subtle case is an invariant that fails in the initial state: its correct
counterexample contains zero operations. The formatter must handle that case.

## 6. Initial tests

- Safe parallel spending returns `ROBUST_PASS` with deterministic counts.
- Overspend returns `CONTRACT_FAIL`; removing either operation makes it pass.
- Inventory race returns `INCONSISTENT_HISTORY` due to unreproducible reads.
- Double booking uses `append` plus `unique` and returns `CONTRACT_FAIL`.
- Config mismatch uses scalar resources plus `equals` and returns
  `CONTRACT_FAIL`.
- A constructed order-sensitive case returns `SCHEDULE_DEPENDENT` with one safe
  and one unsafe witness.
- Each invariant is checked initially and after every operation.
- Explicit order constraints are honored; cycles and unknown endpoints are
  `INVALID_HISTORY`.
- Stale values and stale versions reject a replay independently.
- Failed operations cannot contain effects and do not participate in replay.
- Unknown fields, duplicate IDs, missing resources, non-finite numbers, and
  incompatible effect types are rejected with readable paths.
- Search exhaustion is `INCONCLUSIVE`, never a contract violation.
- Shrinking preserves its target classification, is 1-minimal, deterministic,
  and supports the empty initial-state counterexample.
- Repeated checking of identical input returns byte-equivalent structured output
  apart from explicitly excluded timing data.
- JSON history and YAML contract examples parse without network access.
- The permission-stale directory states that the scenario is unsupported rather
  than presenting a misleading expected verdict.

## 7. Terminology audit

- **"Serializability"** is too strong without a precisely chosen database
  history model and conflict/view semantics. The v0.1 property also adds
  application invariants. Use **contract replay classification**.
- **"Contract serializability"** and **"effect serializability"** have no defined
  meaning in this project and should not appear as claims. They may be research
  questions only after a formal definition and prior-art review.
- **"Linearizability"** and **"strict serializability"** are incorrect because
  v0.1 does not enforce trusted real-time precedence.
- **"Formal verification"** overstates bounded exhaustive replay of user-supplied
  traces. Use **deterministic exhaustive checking for small histories**.
- **"Concurrent operations"** is too strong for operations merely unordered by
  recorded constraints. Use **unordered operations** unless concurrency is
  established by a future clock model.
- **"Minimal counterexample"** is too strong for single-deletion shrinking. Use
  **1-minimal reduced counterexample**.
- **"The execution history is the evidence"** is directionally useful but
  incomplete: a history is evidence only within its instrumentation boundary.
- **"Revalidate Agent B"** is not always a justified repair. It may be suggested
  only if a stale recorded read is causally relevant; invariant-only failures do
  not establish that repair.

## 8. Classification decision

The v0.1 classification reports both existential and universal information. This
prevents a safe witness from hiding an unsafe permitted schedule and makes
schedule sensitivity a first-class result. It does not claim safety beyond the
orders and effects represented by the input history.
