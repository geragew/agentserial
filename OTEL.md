# OpenTelemetry Adapter

AgentSerial imports trace exports encoded as official OTLP/JSON
`ExportTraceServiceRequest`/`TracesData` objects. It also accepts the OpenTelemetry
file-exporter form with one OTLP/JSON object per line.

The adapter adds an AgentSerial-specific instrumentation convention. These
attributes are not official OpenTelemetry semantic conventions.

## Resource attribute

Every imported batch must resolve to exactly one history ID:

```text
agentserial.history.id = "production-run-123"
```

Place it in the OpenTelemetry Resource attributes. Multiple `resourceSpans`
entries may repeat the same ID.

## Operation spans

A span participates as an AgentSerial operation only when it has:

```text
agentserial.operation.id     = "purchase-a"
agentserial.agent.id         = "buyer-agent"
agentserial.operation.status = "success"  # optional; defaults to success
```

Non-AgentSerial spans are ignored, but their `agentserial.resource` events are
still read. A failed operation cannot contain effects.

## Span events

Initial resource:

```text
event name: agentserial.resource
agentserial.resource.name    = "budget"
agentserial.resource.value   = 1000
agentserial.resource.version = 0
```

Recorded read:

```text
event name: agentserial.read
agentserial.resource.name    = "budget"
agentserial.resource.value   = 1000
agentserial.resource.version = 0
```

Modeled effect:

```text
event name: agentserial.effect
agentserial.effect.type      = "append"
agentserial.resource.name    = "spends"
agentserial.resource.value   = 800
```

OTLP attributes use the standard `AnyValue` JSON representation. AgentSerial
supports string, boolean, integer, double, and arrays of those scalar values.

## Explicit order

An operation may declare predecessor operation IDs:

```text
agentserial.order.after = ["policy-update", "approval"]
```

AgentSerial deliberately does not infer ordering from file position,
`startTimeUnixNano`, `endTimeUnixNano`, `parentSpanId`, or span links. The
OpenTelemetry file exporter does not guarantee file or timestamp ordering, and
parent-child relationships do not by themselves prove commit precedence.

## Usage

Configure an OpenTelemetry exporter to retain OTLP/JSON traces, instrument spans
using the convention above, then run:

```console
agentserial import-otel traces.json --output history.json
agentserial validate history.json --contract contract.yaml
agentserial check history.json --contract contract.yaml
```

See `examples/09_opentelemetry` for a complete payload. The adapter is local and
does not send telemetry to any service.

## Supported boundary

- OTLP/JSON only; binary Protobuf and OTLP/gRPC are not parsed.
- One AgentSerial history per import.
- No baggage, logs, metrics, or automatic invariant discovery.
- No timestamp-based causality.
- No guarantee that the trace contains every relevant external effect.

The OTLP wire format is defined by the OpenTelemetry project:

- https://github.com/open-telemetry/opentelemetry-proto/blob/main/docs/specification.md
- https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/

