import { appendFileSync, closeSync, openSync, writeFileSync } from "node:fs";

import { TraceRecorder } from "./index.js";


export function createFileRecorder(path, options) {
  let initialized = false;
  let initialChunk = "";
  const recorder = new TraceRecorder({
    ...options,
    emit: chunk => {
      if (initialized) appendFileSync(path, chunk, { encoding: "utf8" });
      else initialChunk += chunk;
    },
  });
  const descriptor = openSync(path, options.overwrite ? "w" : "wx");
  try {
    writeFileSync(descriptor, initialChunk, { encoding: "utf8" });
  } finally {
    closeSync(descriptor);
  }
  initialized = true;
  return recorder;
}

export { OperationCapture, TraceRecorder } from "./index.js";
