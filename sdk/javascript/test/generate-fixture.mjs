import { createFileRecorder } from "../src/node.js";


const output = process.argv[2];
if (!output) throw new Error("usage: node generate-fixture.mjs OUTPUT.jsonl");

const recorder = createFileRecorder(output, {
  historyId: "javascript-compatibility",
  initialState: { balance: { value: 10, version: 0 } },
  overwrite: true,
});
await recorder.capture("debit", "billing-agent", operation => {
  operation.read("balance", 10, 0);
  operation.effect("increment", "balance", -4);
});
