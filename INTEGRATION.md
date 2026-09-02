# Integrating AgentSerial

The JSONL adapter is the shortest path from an existing agent runtime to
AgentSerial. Emit one JSON object per line while agents execute, import the trace,
then check the generated history.

## Event lifecycle

```text
history
resource ...
operation_start -> read/effect ... -> operation_end
order ...
```

Blank lines are ignored. Every other line must contain exactly one event object.
Unknown fields and incomplete operations are rejected with a line number.

### History

```json
{"event":"history","history_id":"run-123","schema_version":"0.1"}
```

Exactly one history event is required.

### Initial resource

```json
{"event":"resource","resource":"budget","value":1000,"version":0}
```

Emit each modeled resource once. Values and versions describe state before any
recorded operation commits.

### Operation and reads

```json
{"event":"operation_start","operation":"purchase-a","agent":"buyer-agent"}
{"event":"read","operation":"purchase-a","resource":"budget","value":1000,"version":0}
```

The runtime integration, not the LLM, should capture read values and versions.
Do not insert a guessed version.

### Effects and completion

```json
{"event":"effect","operation":"purchase-a","type":"append","resource":"spends","value":800}
{"event":"operation_end","operation":"purchase-a","status":"success"}
```

Effect types are `set`, `increment`, and `append`. Failed operations must not
contain effects because v0.1 cannot represent partial commits.

### Ordering

```json
{"event":"order","before":"policy-update","after":"deployment"}
```

Record an order only when the producer has causal evidence. File position and
timestamps do not imply operation order in v0.1.

## Commands

Try the built-in demonstration without creating files:

```console
agentserial demo
```

Create editable starter files:

```console
agentserial init my-agent-check
```

Import and validate a real trace:

```console
agentserial import-jsonl events.jsonl --output history.json
agentserial validate history.json --contract contract.yaml
agentserial check history.json --contract contract.yaml
```

The importer is runtime-neutral. Framework-specific adapters should translate
their native trace events into this JSONL lifecycle rather than bypassing the
versioned `History` model.

## Python runtime recorder

`TraceRecorder` writes the same lifecycle with thread-safe, atomic operation
batches. It buffers an operation until the context exits, preventing partial
effect records when a provider or tool call fails.

```python
from agentserial.recorder import TraceRecorder

recorder = TraceRecorder(
    "events.jsonl",
    history_id="payment-run-42",
    initial_state={"spends": ([], 0)},
)

with recorder.operation("purchase-a", "buyer-agent") as operation:
    operation.read("spends", [], 0)
    operation.effect("append", "spends", 800)

recorder.order("policy-check", "purchase-a")
```

Pass `overwrite=True` only when replacing an existing trace intentionally.

## JavaScript runtime recorder

The typed ESM SDK under `sdk/javascript` implements the same atomic lifecycle
without runtime dependencies. Its core accepts a synchronous output callback;
the `/node` entry point provides exclusive JSONL file creation.

```js
import { createFileRecorder } from "@geragew/agentserial/node";

const recorder = createFileRecorder("events.jsonl", {
  historyId: "payment-run-42",
  initialState: { spends: { value: [], version: 0 } },
});

await recorder.capture("purchase-a", "buyer-agent", async operation => {
  operation.read("spends", [], 0);
  operation.effect("append", "spends", 800);
  await executePurchase();
});
```

`capture` commits when the callback resolves. When it throws or rejects, the
original error is rethrown after a failed operation is recorded. For runtimes
without a filesystem, instantiate `TraceRecorder` from the base entry point and
provide `emit(chunk)` to route complete JSONL batches to durable storage.
