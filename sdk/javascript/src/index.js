const EFFECT_TYPES = new Set(["set", "increment", "append"]);

export class TraceRecorder {
  #emit;
  #operationIds = new Set();
  #orderEdges = new Set();
  #resources;

  constructor({ historyId, initialState, emit }) {
    this.#emit = requireFunction(emit, "emit");
    this.#resources = new Set(Object.keys(requireObject(initialState, "initialState")));
    const events = [{ event: "history", history_id: requireName(historyId, "historyId"), schema_version: "0.1" }];
    for (const [resource, state] of Object.entries(initialState)) {
      requireName(resource, "resource");
      const { value, version } = requireObject(state, `initialState.${resource}`);
      events.push({ event: "resource", resource, value: requireJsonValue(value), version: requireVersion(version) });
    }
    this.#write(events);
  }

  operation(operationId, agent) {
    const id = requireName(operationId, "operationId");
    const agentId = requireName(agent, "agent");
    if (this.#operationIds.has(id)) throw new Error(`duplicate operation ID: ${JSON.stringify(id)}`);
    this.#operationIds.add(id);
    const start = { event: "operation_start", operation: id, agent: agentId };
    return new OperationCapture(start, this.#resources, events => this.#write(events));
  }

  async capture(operationId, agent, callback) {
    const operation = this.operation(operationId, agent);
    try {
      const value = await requireFunction(callback, "callback")(operation);
      if (!operation.closed) operation.commit();
      return value;
    } catch (error) {
      if (!operation.closed) operation.fail();
      throw error;
    }
  }

  order(before, after) {
    const edge = {
      event: "order",
      before: requireName(before, "before"),
      after: requireName(after, "after"),
    };
    if (edge.before === edge.after) throw new Error("an ordering constraint cannot be a self-edge");
    const key = `${edge.before}\0${edge.after}`;
    if (this.#orderEdges.has(key)) throw new Error(`duplicate ordering constraint: ${edge.before} -> ${edge.after}`);
    this.#orderEdges.add(key);
    this.#write([edge]);
  }

  #write(events) {
    this.#emit(`${events.map(event => JSON.stringify(event)).join("\n")}\n`);
  }
}

export class OperationCapture {
  #events = [];
  #open = true;
  #resources;
  #start;
  #write;

  constructor(start, resources, write) {
    this.#start = start;
    this.#resources = resources;
    this.#write = write;
  }

  get closed() {
    return !this.#open;
  }

  read(resource, value, version) {
    this.#assertOpen();
    this.#assertResource(resource);
    this.#events.push({
      event: "read",
      operation: this.#start.operation,
      resource,
      value: requireJsonValue(value),
      version: requireVersion(version),
    });
    return this;
  }

  effect(type, resource, value) {
    this.#assertOpen();
    if (!EFFECT_TYPES.has(type)) throw new TypeError(`unsupported effect type: ${JSON.stringify(type)}`);
    this.#assertResource(resource);
    this.#events.push({
      event: "effect",
      operation: this.#start.operation,
      type,
      resource,
      value: requireJsonValue(value),
    });
    return this;
  }

  commit() {
    this.#finish("success");
  }

  fail() {
    this.#finish("failure");
  }

  #finish(status) {
    this.#assertOpen();
    this.#open = false;
    const events = [this.#start];
    if (status === "success") events.push(...this.#events);
    events.push({ event: "operation_end", operation: this.#start.operation, status });
    this.#write(events);
  }

  #assertResource(resource) {
    requireName(resource, "resource");
    if (!this.#resources.has(resource)) throw new Error(`unknown resource: ${JSON.stringify(resource)}`);
  }

  #assertOpen() {
    if (!this.#open) throw new Error("operation capture is already closed");
  }
}

function requireFunction(value, field) {
  if (typeof value !== "function") throw new TypeError(`${field} must be a function`);
  return value;
}

function requireName(value, field) {
  if (typeof value !== "string" || value.length === 0) throw new TypeError(`${field} must be a non-empty string`);
  return value;
}

function requireObject(value, field) {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`${field} must be an object`);
  }
  return value;
}

function requireVersion(value) {
  if (!Number.isSafeInteger(value) || value < 0) throw new TypeError("version must be a non-negative safe integer");
  return value;
}

function requireJsonValue(value) {
  if (isJsonScalar(value)) return value;
  if (Array.isArray(value) && value.every(isJsonScalar)) return value;
  throw new TypeError("value must be a finite JSON scalar or a list of scalars");
}

function isJsonScalar(value) {
  return value === null
    || typeof value === "string"
    || typeof value === "boolean"
    || (typeof value === "number" && Number.isFinite(value));
}
