export type JsonScalar = string | number | boolean | null;
export type JsonValue = JsonScalar | JsonScalar[];
export type EffectType = "set" | "increment" | "append";

export interface ResourceState {
  value: JsonValue;
  version: number;
}

export interface RecorderOptions {
  historyId: string;
  initialState: Record<string, ResourceState>;
  emit(chunk: string): void;
}

export class TraceRecorder {
  constructor(options: RecorderOptions);
  operation(operationId: string, agent: string): OperationCapture;
  capture<T>(
    operationId: string,
    agent: string,
    callback: (operation: OperationCapture) => T | Promise<T>,
  ): Promise<T>;
  order(before: string, after: string): void;
}

export class OperationCapture {
  readonly closed: boolean;
  read(resource: string, value: JsonValue, version: number): this;
  effect(type: EffectType, resource: string, value: JsonValue): this;
  commit(): void;
  fail(): void;
}
