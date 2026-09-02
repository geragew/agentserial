# AgentSerial Effect History Format v0.1

Status: design draft. This document defines the semantics to implement; it does
not claim compatibility with database serializability or linearizability.

## 1. Problem and checked property

Independent agents can each report success while their combined effects violate
a system-wide contract. AgentSerial v0.1 deterministically checks recorded,
small histories without invoking an LLM or an external service.

Given an initial state, a finite set of atomic operations, explicit ordering
constraints, and a contract, the checker enumerates total orders that extend the
constraints and reproduce every recorded read from simulated versioned state.
Those orders are **feasible replays**. It then classifies whether all, some, or
none of the feasible replays satisfy every invariant initially and after each
operation. This property is named **contract replay classification**.

These names deliberately avoid claiming serializability, linearizability,
strict serializability, or formal verification.

An operation that reported failure has no effects in v0.1 and is excluded from
the replay. A successful operation is included in full. Partial commits are not
representable.

## 2. Assumptions

- The history is finite, complete for the resources and effects relevant to the
  contract, and uses trusted logical data supplied by the producer.
- Each successful operation is an atomic unit: its reads are checked against the
  state immediately before it, then all its effects are applied atomically.
- Resource versions are non-negative integers. A successful write increments
  the affected resource version once per operation, regardless of how many
  effects in that operation target it.
- Explicit ordering edges are authoritative. Optional wall-clock timestamps are
  descriptive in v0.1 and do not create ordering edges.
- Effects are deterministic and local to the modeled state. There are no hidden
  reads, writes, retries, or external outcomes.
- Invariants must hold in the initial state and after every committed operation,
  not merely in the final state.
- Numeric operations use JSON numbers. Implementations must reject non-finite
  values and must document their concrete numeric representation.

## 3. Model

### 3.1 History

A `History` is a versioned document containing:

- `schema_version`: exactly `"0.1"`;
- `history_id`: non-empty identifier;
- `initial_state`: map from resource identifier to its initial value and version;
- `operations`: unique operations;
- `order`: explicit directed `before -> after` constraints.

The ordering graph must be acyclic and may be incomplete. Operations unrelated
by its transitive closure may be replayed in either order. In v0.1, that means
only "unordered under the recorded constraints"; it does not prove physical
concurrency.

### 3.2 Resource

A `Resource` is a named cell with a JSON-compatible value and an integer
version. v0.1 supports scalar strings, booleans, numbers, null, and lists of
scalar values. Objects and nested paths are outside the normative core.

### 3.3 Operation

An `Operation` is the atomic unit considered by replay. It has:

- `id`: unique non-empty identifier;
- `agent`: non-empty agent identifier;
- `status`: `success` or `failure`;
- `reads`: zero or more reads, with no duplicate resource;
- `effects`: an ordered list of effects.

For `failure`, `effects` must be empty. For `success`, all reads must match before
any effect is applied. Effects within one operation are evaluated in listed
order but become visible together at commit.

An operation is not necessarily an entire agent task or conversation. The
history producer chooses the atomic boundary and must document it.

### 3.4 Read

A `Read` records `resource`, `value`, and `version`. It matches only when both
value and version equal the simulated resource immediately before the operation.
A missing resource or mismatch rejects that candidate replay.

Reads are observations, not ordering constraints by themselves. They constrain
order indirectly because a feasible replay must reproduce them.

### 3.5 Effect

An `Effect` is an intended deterministic state transition, not evidence that an
external action occurred. The v0.1 effect types are:

- `set`: replace a resource value;
- `increment`: add a finite number to a numeric resource;
- `append`: append a scalar value to a list resource.

Each effect contains `type`, `resource`, and `value`. A type/value mismatch or a
reference to an absent resource rejects the input as `INVALID_HISTORY`, rather
than rejecting only one replay.

Writes are the state transitions produced by effects. `effect` and `write` are
therefore not separate input concepts in v0.1. External effects, approvals, and
irreversible actions are not modeled.

### 3.6 Ordering constraint

An ordering constraint is a pair of operation IDs `{before, after}`. Every
candidate replay must place `before` earlier than `after`. Self-edges, unknown
IDs, duplicate edges, and cycles make the history invalid.

### 3.7 Contract

A `Contract` is a versioned document containing `version: "0.1"` and a non-empty
list of uniquely identified invariants. It contains no executable expression or
arbitrary evaluation facility.

### 3.8 Invariant

The initial implementation should support exactly these invariant types:

- `max_sum`: the sum of all numeric elements currently stored in a named list
  resource must be at most `max`;
- `min_value`: a named numeric resource must be at least `min`;
- `unique`: all scalar elements of a named list resource must be distinct;
- `equals`: the values of two named resources must be equal.

`max_sum` uses modeled state rather than a separate event ledger: spend amounts,
for example, are appended to a `spends` list. This keeps replay and contract
evaluation on one explicit state model.

An invariant is evaluated on the initial state and after each operation. A
contract referencing a missing resource or an incompatible value type is
`INVALID_CONTRACT`.

## 4. Checking semantics

1. Parse and validate the history and contract.
2. Evaluate all invariants on the initial state.
3. Project the ordering graph onto successful operations while preserving
   reachability through excluded failed operations. Enumerate its topological
   orders in deterministic ID order, subject to a configured operation/search
   limit.
4. For each candidate prefix, require all reads of the next operation to match.
5. Apply its effects atomically and increment affected resource versions. Record
   whether invariants hold, but continue the replay because a violating prefix is
   still a feasible replay and is evidence for schedule sensitivity.
6. Classify complete feasible replays as contract-valid or contract-invalid.
7. Derive the verdict from the counts of each class after exhaustive search.

Read mismatches may prune a candidate because it is infeasible. Invariant
violations must not prune it before a complete replay is counted. The checker
must not silently omit a successful operation to obtain a pass.

## 5. Verdicts

- `ROBUST_PASS`: at least one feasible replay exists and every feasible replay
  satisfies the contract.
- `SCHEDULE_DEPENDENT`: feasible contract-valid and contract-invalid replays both
  exist. Correctness depends on an order left open by the recorded constraints.
- `CONTRACT_FAIL`: at least one feasible replay exists and every feasible replay
  violates the contract.
- `INCONSISTENT_HISTORY`: no total order can reproduce all recorded reads. This
  is an observational inconsistency, not a contract violation.
- `INCONCLUSIVE`: a configured operation, state, or search limit was reached
  before classification completed.
- `INVALID_HISTORY`: the history violates its schema or structural semantics.
- `INVALID_CONTRACT`: the contract violates its schema or cannot be evaluated
  against the declared state.

Timeouts and search limits must never be reported as a contract violation.

## 6. Counterexample

For `CONTRACT_FAIL` or `SCHEDULE_DEPENDENT`, a `Counterexample` is a subset of
successful operations plus induced ordering constraints that preserves an
invalid feasible replay. For `INCONSISTENT_HISTORY`, it preserves the absence of
any feasible replay.
The v0.1 shrinker seeks a deterministic **1-minimal reduced counterexample**:
removing any one remaining operation makes the reduction predicate stop holding.

This does not guarantee minimum cardinality. A counterexample must report the
failing invariant(s) and/or unmatched reads found during exhaustive replay. A
repair suggestion may be shown only when it follows from recorded facts; the
core verdict does not require a repair.

## 7. Worked examples

### 7.1 Overspend

Initial state: `budget=1000@v0`, `spends=[]@v0`. Operations A and B both read
`budget=1000@v0`; A appends 800 and B appends 800 to `spends`. They are unordered.
The contract is `max_sum(spends, 1000)`.

Either replay order reproduces both reads because `budget` is unchanged. After
the second append, the sum is 1600. Every feasible replay violates the contract,
so the verdict is `CONTRACT_FAIL`. Both operations form a 1-minimal reduced
counterexample.

### 7.2 Safe parallel spending

The same state and reads are used, but A appends 300 and B appends 200. Both
orders reproduce the reads and every prefix sum is at most 1000. The verdict is
`ROBUST_PASS` after exhaustive classification.

### 7.3 Inventory race

Initial state is `inventory=1@v0`. A and B both read that value and version, then
each increments inventory by -1. Whichever operation is first changes the state
to `0@v1`; the second operation's recorded read cannot be reproduced. With
`min_value(inventory, 0)`, no feasible replay exists. The verdict is
`INCONSISTENT_HISTORY`, not proof that a real execution serialized to `-1`.

## 8. Cases not represented correctly

1. An agent charges a credit card, times out, and retries. Atomic deterministic
   effects cannot express an irreversible external action with an unknown or
   duplicated outcome. Encoding it as `set` or `append` would overstate what the
   checker knows.
2. A permission is read at policy version P1, policy P2 revokes it, and the agent
   later acts using a cached capability. v0.1 cannot express capability lifetime,
   revocation semantics, or a trusted causal relation unless the producer has
   already reduced all of them to explicit resources, reads, effects, and order
   edges. The planned permission-stale example is therefore unsupported.
3. Two operations overlap according to clocks from different machines. Since
   timestamps are descriptive and clock uncertainty is not modeled, v0.1 cannot
   infer real-time precedence or prove linearizability.
4. A contract that is satisfied only at the end but temporarily violated cannot
   be treated as valid: v0.1 deliberately requires every prefix to satisfy it.
   Contracts with commit-group or eventual semantics need a later model.

## 9. Semantic risks and limits

- Classification is over feasible replays admitted by the recorded model. It
  cannot cover schedules excluded by missing or incorrect instrumentation.
- Completeness of instrumentation is assumed and cannot be established by the
  checker. Missing effects can create false confidence.
- Atomic operation boundaries are supplied by the producer and materially alter
  the verdict.
- Version equality has meaning only if producers assign versions consistently.
- Exhaustive enumeration is factorial in the worst case; v0.1 targets small
  histories and must expose hard limits.
- A negative verdict is a bounded model result, not a proof about the external
  system.
