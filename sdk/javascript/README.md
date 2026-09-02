# AgentSerial JavaScript SDK

This zero-dependency recorder emits the AgentSerial JSONL lifecycle from
JavaScript runtimes. The core accepts a synchronous `emit` callback; the Node
entry point provides exclusive file creation.

```js
import { createFileRecorder } from "@geragew/agentserial/node";

const recorder = createFileRecorder("events.jsonl", {
  historyId: "payment-run-42",
  initialState: { spends: { value: [], version: 0 } },
});

await recorder.capture("purchase-a", "buyer-agent", async operation => {
  operation.read("spends", [], 0);
  operation.effect("append", "spends", 800);
  await purchase();
});
```

`capture` commits only when the callback resolves. If it throws or rejects, the
SDK records a failed operation and discards its buffered reads and effects.
