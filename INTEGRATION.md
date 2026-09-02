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

## Automatic Python instrumentation

`Instrumentor` wraps synchronous and asynchronous operations while preserving
the recorder's atomic success/failure behavior. IDs remain producer-defined and
deterministic; AgentSerial never derives identity or causality from timing.

```python
from agentserial import Instrumentor, TraceRecorder

recorder = TraceRecorder("events.jsonl", "payment-run", {"balance": (1000, 0)})
instrument = Instrumentor(recorder)

def map_request(operation, call):
    operation.read("balance", call.kwargs["observed_balance"], call.kwargs["version"])

def map_response(operation, call, response):
    if response["accepted"]:
        operation.effect("increment", "balance", -call.kwargs["amount"])

@instrument.http(
    lambda payment_id, **_: f"charge-{payment_id}",
    "billing-agent",
    request=map_request,
    response=map_response,
)
def charge(payment_id, *, amount, observed_balance, version, authorization):
    return payment_provider.charge(payment_id, amount, authorization)
```

Use `operation`, `tool`, `http`, or `database` according to the integration
boundary. HTTP and database wrappers do not infer reads or effects. Their mapping
hooks must add only facts guaranteed by the producer. Omitting a mapping hook
records the operation lifecycle but makes no claim about state access or effects.

`current_operation()` exposes the active capture to nested coroutines and tasks
through `ContextVar`. Applying the same wrapper recursively joins the active
capture instead of emitting duplicate operations. Distinct decorated functions
remain distinct operations and therefore require unique IDs.

Call arguments and results exposed to mapping hooks are copied into a JSON-safe
shape. Keys containing `api_key`, `authorization`, `cookie`, `password`,
`secret`, or `token` are replaced with `[REDACTED]` by default. Unsupported
objects become a type marker rather than invoking `repr`, which could leak data.
`InstrumentationPolicy` configures the key list, replacement, and payload limit.
The wrapped function still receives its original unmodified arguments.

Instrumentation is fail-closed: invalid identity, oversized mapped payload, or a
mapping exception prevents a successful capture and is raised to the caller.
After a wrapped function has produced an external side effect, the application
must treat a subsequent mapping error as a failed trace and must not verify or
publish that incomplete trace.

The recorder uses synchronous file writes. Each completed operation is one
locked, flushed-on-close batch, so producers receive natural backpressure and no
background queue can be lost at shutdown. It deliberately performs no automatic
retry: retrying without a producer-stable operation ID could duplicate effects.
Cross-process retry deduplication remains outside the v0.1 recorder contract.

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
