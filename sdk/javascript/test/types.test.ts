import { TraceRecorder } from "../src/index.js";
import { createFileRecorder } from "../src/node.js";


let trace = "";
const recorder = new TraceRecorder({
  historyId: "typed-run",
  initialState: { balance: { value: 10, version: 0 } },
  emit: chunk => { trace += chunk; },
});
recorder.operation("debit", "billing-agent").read("balance", 10, 0).effect(
  "increment",
  "balance",
  -4,
).commit();
void recorder.capture("credit", "billing-agent", async operation => {
  operation.effect("increment", "balance", 4);
  return trace.length;
});

createFileRecorder("events.jsonl", {
  historyId: "file-run",
  initialState: { events: { value: [], version: 0 } },
  overwrite: true,
});
