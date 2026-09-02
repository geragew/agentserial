import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { TraceRecorder } from "../src/index.js";
import { createFileRecorder } from "../src/node.js";


test("records an atomic successful operation", () => {
  let trace = "";
  const recorder = new TraceRecorder({
    historyId: "payment-run",
    initialState: { balance: { value: 10, version: 0 } },
    emit: chunk => { trace += chunk; },
  });
  recorder.operation("debit", "billing-agent")
    .read("balance", 10, 0)
    .effect("increment", "balance", -4)
    .commit();

  const events = trace.trim().split("\n").map(JSON.parse);
  assert.deepEqual(events.map(event => event.event), [
    "history", "resource", "operation_start", "read", "effect", "operation_end",
  ]);
});

test("capture discards effects when callback fails", async () => {
  let trace = "";
  const recorder = new TraceRecorder({
    historyId: "failed-run",
    initialState: { balance: { value: 10, version: 0 } },
    emit: chunk => { trace += chunk; },
  });

  await assert.rejects(recorder.capture("debit", "billing-agent", operation => {
    operation.effect("increment", "balance", -4);
    throw new Error("provider failed");
  }), /provider failed/);

  const events = trace.trim().split("\n").map(JSON.parse);
  assert.equal(events.at(-1).status, "failure");
  assert.equal(events.some(event => event.event === "effect"), false);
});

test("rejects duplicate operations and unknown resources", () => {
  const recorder = new TraceRecorder({
    historyId: "validation",
    initialState: { balance: { value: 10, version: 0 } },
    emit() {},
  });
  recorder.operation("debit", "agent");
  assert.throws(() => recorder.operation("debit", "agent"), /duplicate operation ID/);
  assert.throws(() => recorder.operation("credit", "agent").read("missing", 0, 0), /unknown resource/);
});

test("node recorder creates an exclusive JSONL file", (context) => {
  const directory = mkdtempSync(join(tmpdir(), "agentserial-sdk-"));
  context.after(() => rmSync(directory, { recursive: true, force: true }));
  const path = join(directory, "events.jsonl");
  const recorder = createFileRecorder(path, {
    historyId: "node-run",
    initialState: { events: { value: [], version: 0 } },
  });
  recorder.operation("append", "node-agent").effect("append", "events", "done").commit();
  const trace = readFileSync(path, "utf8");
  assert.match(trace, /"operation":"append"/);
  assert.throws(() => createFileRecorder(path, {
    historyId: "second-run",
    initialState: { events: { value: [], version: 0 } },
  }), /EEXIST/);
  assert.equal(readFileSync(path, "utf8"), trace);
});

test("invalid options do not leave a file", (context) => {
  const directory = mkdtempSync(join(tmpdir(), "agentserial-sdk-"));
  context.after(() => rmSync(directory, { recursive: true, force: true }));
  const path = join(directory, "invalid.jsonl");

  assert.throws(() => createFileRecorder(path, {
    historyId: "",
    initialState: {},
  }), /historyId must be a non-empty string/);
  assert.throws(() => readFileSync(path), /ENOENT/);
});
