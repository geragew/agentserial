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

## Declarative mapping

Existing OTLP/JSON producers can supply a strict mapping instead of renaming
their telemetry to `agentserial.*`:

```console
agentserial import-otel traces.json \
  --mapping mapping.yaml \
  --diagnostics mapping-diagnostics.json \
  --output history.json
```

On Windows Command Prompt, place the command on one line. A complete mapping is
available at `examples/09_opentelemetry/mapping.yaml`; its machine-readable schema
is `schemas/otel-mapping.schema.json`.

Mapping files have version `0.1` and explicitly select sources for the history
ID, operation ID, agent, status, predecessors, initial resources, reads, and
effects. A source is a structured object:

```yaml
source: span_attribute
key: company.operation.id
```

| Source | Meaning |
| --- | --- |
| `resource_attribute` | Attribute on the OpenTelemetry Resource |
| `span_attribute` | Attribute on the current span |
| `span_field` | OTLP span field such as `traceId`, `spanId`, or `name` |
| `span_links` | Ordered list of `spanId` values from OTLP span links |
| `span_status` | Numeric OTLP `status.code` |
| `event_attribute` | Attribute on the matching span event |
| `literal` | Explicit constant supplied as `value` |

A span is ignored when its configured operation ID source is absent. Once an ID
is resolved, every other required field must resolve with the declared type or
the import fails. Unknown statuses fail rather than defaulting silently. Only a
missing status may use `default_status`.

The diagnostics sidecar records a SHA-256 mapping fingerprint, mapped and
ignored span counts, mapped and unknown event counts, unused resource/span/event
attributes, and sorted source trace/span IDs. This makes mapping loss reviewable
without adding non-semantic telemetry to the v0.1 `History` model. Identical
mapping content and OTLP input produce deterministic history and diagnostics.

Source timestamps are summarized separately as their observed count and minimum
and maximum Unix-nanosecond values. `ingestion_time_recorded` is explicitly false
because this local converter does not receive a trustworthy collector-ingestion
timestamp and must not substitute its wall clock.

`traceId` and `spanId` are preserved as lineage when present. They become logical
history or operation IDs only when the mapping explicitly selects them. Span
timestamps remain descriptive and are never converted into ordering constraints.
Parent IDs and links likewise do not imply commit order. A predecessor mapping
must point to producer-supplied causal evidence. `parentSpanId` can be selected
through `span_field`; links require the explicit `span_links` source.

## Supported boundary

- OTLP/JSON only; binary Protobuf and OTLP/gRPC are not parsed.
- One AgentSerial history per import.
- No baggage, logs, metrics, or automatic invariant discovery.
- No timestamp-based causality.
- No guarantee that the trace contains every relevant external effect.
- Generic mapping cannot recover reads, effects, versions, atomicity, or causal
  order that the producer did not record.

The OTLP wire format is defined by the OpenTelemetry project:

- https://github.com/open-telemetry/opentelemetry-proto/blob/main/docs/specification.md
- https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/
