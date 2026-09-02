import { OperationCapture, RecorderOptions, TraceRecorder } from "./index.js";

export interface FileRecorderOptions extends Omit<RecorderOptions, "emit"> {
  overwrite?: boolean;
}

export function createFileRecorder(path: string, options: FileRecorderOptions): TraceRecorder;
export { OperationCapture, TraceRecorder };
