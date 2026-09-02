# AgentSerial Input Formats v0.1

This is the practical input reference. `SPEC.md` is normative when this document
and the specification differ. Unknown fields are rejected.

## History

Histories may be JSON or YAML and have this shape:

```json
{
  "schema_version": "0.1",
  "history_id": "example",
  "initial_state": {
    "balance": {"value": 0, "version": 0}
  },
  "operations": [
    {
      "id": "credit",
      "agent": "agent-a",
      "status": "success",
      "reads": [],
      "effects": [
        {"type": "increment", "resource": "balance", "value": 1}
      ]
    }
  ],
  "order": []
}
```

`initial_state` values are scalar JSON values or lists of scalars. Versions are
non-negative integers. Operation IDs must be unique.

`status` defaults to `success`. A `failure` operation cannot contain effects and
does not participate in replay. Ordering reachability through failed operations
is preserved.

Each read contains an exact `resource`, `value`, and `version`. Both must match
the simulated state for a replay to be feasible.

Supported effects:

| Type | Required resource | Behavior |
|---|---|---|
| `set` | Any modeled resource | Replaces its value |
| `increment` | Numeric resource | Adds a numeric value |
| `append` | List resource | Appends one scalar value |

All effects in an operation commit atomically. Each touched resource version is
incremented once per operation.

An ordering entry is `{"before": "operation-a", "after": "operation-b"}`.
Edges must be unique, reference known operations, and form an acyclic graph.
Timestamps are not part of v0.1.

## Contract

Contracts may be JSON or YAML:

```yaml
version: "0.1"
invariants:
  - id: non-negative-balance
    type: min_value
    resource: balance
    min: 0
```

Invariant IDs must be unique. Invariants apply to the initial state and every
committed operation prefix.

| Type | Fields | Meaning |
|---|---|---|
| `max_sum` | `resource`, `max` | Numeric list sum is at most `max` |
| `min_value` | `resource`, `min` | Numeric resource is at least `min` |
| `unique` | `resource` | List contains no duplicate scalar values |
| `equals` | `left`, `right` | Two modeled values are exactly equal |

There is no expression evaluator. A contract that references an absent resource
or cannot evaluate values written by the history is rejected.

## Schemas

Machine-readable schemas are committed under `schemas/`. Regenerate them after
model changes:

```console
python scripts/export_schemas.py
python scripts/export_schemas.py --check
```

JSON Schema validates document shape. AgentSerial still performs additional
semantic checks such as acyclic ordering and cross-document resource types.

## Limits

The CLI defaults to 10 successful operations and 100,000 explored prefixes.
Reaching either limit produces `INCONCLUSIVE`, never a contract violation.

