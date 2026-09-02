from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, ValidationError, model_validator
from yaml.nodes import MappingNode, Node, SequenceNode

from agentserial.models import History, JsonValue, StrictModel
from agentserial.otel_adapter import OtelImportError, _attributes, _load_documents

_MISSING = object()


class ValueSource(StrictModel):
    source: Literal[
        "literal",
        "resource_attribute",
        "span_attribute",
        "span_field",
        "span_links",
        "span_status",
        "event_attribute",
    ]
    key: str | None = Field(default=None, min_length=1)
    value: JsonValue | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        needs_key = self.source in {
            "resource_attribute",
            "span_attribute",
            "span_field",
            "event_attribute",
        }
        if needs_key != (self.key is not None):
            requirement = "requires" if needs_key else "does not accept"
            raise ValueError(f"{self.source} {requirement} key")
        if self.source == "literal" and self.value is None:
            raise ValueError("literal source requires a non-null value")
        if self.source != "literal" and self.value is not None:
            raise ValueError(f"{self.source} does not accept value")
        return self


class OperationMapping(StrictModel):
    id: ValueSource
    agent: ValueSource
    status: ValueSource | None = None
    success_values: list[JsonValue] = Field(default_factory=lambda: ["success", "ok", 1])
    failure_values: list[JsonValue] = Field(default_factory=lambda: ["failure", "error", 2])
    default_status: Literal["success", "failure"] = "success"
    predecessors: ValueSource | None = None


class ResourceEventMapping(StrictModel):
    name: str = Field(min_length=1)
    resource: ValueSource
    value: ValueSource
    version: ValueSource


class ReadEventMapping(ResourceEventMapping):
    pass


class EffectEventMapping(StrictModel):
    name: str = Field(min_length=1)
    type: ValueSource
    resource: ValueSource
    value: ValueSource


class OtelMapping(StrictModel):
    version: Literal["0.1"]
    history_id: ValueSource
    operation: OperationMapping
    resource_event: ResourceEventMapping
    read_event: ReadEventMapping
    effect_event: EffectEventMapping


class OtelDiagnostics(StrictModel):
    mapping_fingerprint: str
    spans_seen: int
    spans_mapped: int
    spans_ignored: int
    events_seen: int
    events_mapped: int
    unmapped_events: dict[str, int]
    unmapped_attributes: dict[str, int]
    trace_ids: list[str]
    span_ids: list[str]
    source_timestamps_seen: int
    source_time_min_unix_nano: str | None
    source_time_max_unix_nano: str | None
    ingestion_time_recorded: Literal[False] = False


class MappedOtelImport(StrictModel):
    history: History
    diagnostics: OtelDiagnostics


def load_otel_mapping(path: Path) -> OtelMapping:
    try:
        text = path.read_text(encoding="utf-8")
        document = yaml.safe_load(text)
        return OtelMapping.model_validate(document)
    except OSError as error:
        raise OtelImportError(str(error)) from error
    except yaml.YAMLError as error:
        raise OtelImportError(f"invalid mapping YAML: {error}") from error
    except ValidationError as error:
        issue = error.errors()[0]
        location = tuple(issue["loc"])
        line = _yaml_line(text, location)
        field = ".".join(str(part) for part in location) or "<root>"
        raise OtelImportError(
            f"invalid OpenTelemetry mapping at line {line}, {field}: {issue['msg']}"
        ) from error


def import_otlp_json_mapped(path: Path, mapping: OtelMapping) -> MappedOtelImport:
    documents = _load_documents(path)
    history_ids: set[str] = set()
    resources: dict[str, dict[str, Any]] = {}
    operations: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    constraints: list[dict[str, str]] = []
    unmapped_events: Counter[str] = Counter()
    unmapped_attributes: Counter[str] = Counter()
    trace_ids: set[str] = set()
    span_ids: set[str] = set()
    timestamp_bounds: list[int | None] = [None, None]
    timestamps_seen = 0
    spans_seen = spans_mapped = events_seen = events_mapped = 0

    for document_number, document in enumerate(documents, start=1):
        resource_spans = document.get("resourceSpans")
        if not isinstance(resource_spans, list):
            raise OtelImportError(f"document {document_number}: resourceSpans must be an array")
        for resource_index, resource_span in enumerate(resource_spans):
            context = f"document {document_number}, resourceSpans[{resource_index}]"
            if not isinstance(resource_span, dict):
                raise OtelImportError(f"{context}: entry must be an object")
            resource_attributes = _attributes(
                resource_span.get("resource", {}).get("attributes", []), context
            )
            _count_unused(
                resource_attributes,
                _used_attribute_keys(mapping, "resource_attribute"),
                "resource",
                unmapped_attributes,
            )
            resource_history_id = _resolve(mapping.history_id, resource_attributes, {}, {}, None)
            if resource_history_id is not _MISSING:
                history_ids.add(_identifier(resource_history_id, "history ID", context))
            scope_spans = resource_span.get("scopeSpans", [])
            if not isinstance(scope_spans, list):
                raise OtelImportError(f"{context}: scopeSpans must be an array")
            for scope_index, scope_span in enumerate(scope_spans):
                scope_context = f"{context}, scopeSpans[{scope_index}]"
                if not isinstance(scope_span, dict) or not isinstance(scope_span.get("spans", []), list):
                    raise OtelImportError(f"{scope_context}: spans must be an array")
                for span_index, span in enumerate(scope_span.get("spans", [])):
                    span_context = f"{scope_context}, spans[{span_index}]"
                    if not isinstance(span, dict):
                        raise OtelImportError(f"{span_context}: span must be an object")
                    spans_seen += 1
                    trace_id = span.get("traceId")
                    span_id = span.get("spanId")
                    if isinstance(trace_id, str) and trace_id:
                        trace_ids.add(trace_id)
                    if isinstance(span_id, str) and span_id:
                        span_ids.add(span_id)
                    for field in ("startTimeUnixNano", "endTimeUnixNano"):
                        if field in span:
                            timestamps_seen += 1
                            _observe_timestamp(span[field], f"{span_context}, {field}", timestamp_bounds)
                    attributes = _attributes(span.get("attributes", []), span_context)
                    _count_unused(
                        attributes,
                        _used_attribute_keys(mapping, "span_attribute"),
                        "span",
                        unmapped_attributes,
                    )
                    span_history_id = _resolve(
                        mapping.history_id, resource_attributes, attributes, span, None
                    )
                    if span_history_id is not _MISSING:
                        history_ids.add(_identifier(span_history_id, "history ID", span_context))
                    events = span.get("events", [])
                    if not isinstance(events, list):
                        raise OtelImportError(f"{span_context}: events must be an array")
                    for event_index, event in enumerate(events):
                        if isinstance(event, dict) and "timeUnixNano" in event:
                            timestamps_seen += 1
                            _observe_timestamp(
                                event["timeUnixNano"],
                                f"{span_context}, events[{event_index}].timeUnixNano",
                                timestamp_bounds,
                            )
                    operation_id = _resolve(mapping.operation.id, resource_attributes, attributes, span, None)
                    mapped_for_span = _map_events(
                        events,
                        mapping,
                        resource_attributes,
                        attributes,
                        span,
                        resources,
                        unmapped_events,
                        unmapped_attributes,
                        operation_id is not _MISSING,
                        span_context,
                    )
                    events_seen += len(events)
                    events_mapped += mapped_for_span
                    if operation_id is _MISSING:
                        continue
                    spans_mapped += 1
                    operation_id = _identifier(operation_id, "operation ID", span_context)
                    if operation_id in operation_ids:
                        raise OtelImportError(f"{span_context}: duplicate operation {operation_id!r}")
                    operation_ids.add(operation_id)
                    agent = _required(
                        mapping.operation.agent,
                        resource_attributes,
                        attributes,
                        span,
                        None,
                        "agent",
                        span_context,
                    )
                    reads, effects = _mapped_operation_events(
                        events, mapping, resource_attributes, attributes, span, span_context
                    )
                    status = _status(mapping.operation, resource_attributes, attributes, span, span_context)
                    operations.append(
                        {
                            "id": operation_id,
                            "agent": _identifier(agent, "agent", span_context),
                            "status": status,
                            "reads": reads,
                            "effects": effects,
                        }
                    )
                    constraints.extend(
                        {"before": predecessor, "after": operation_id}
                        for predecessor in _predecessors(
                            mapping.operation,
                            resource_attributes,
                            attributes,
                            span,
                            span_context,
                        )
                    )

    if len(history_ids) != 1:
        raise OtelImportError(
            f"mapped OTLP input must resolve exactly one distinct history ID; found {len(history_ids)}"
        )
    try:
        history = History.model_validate(
            {
                "schema_version": "0.1",
                "history_id": next(iter(history_ids)),
                "initial_state": resources,
                "operations": operations,
                "order": constraints,
            }
        )
    except ValidationError as error:
        raise OtelImportError(f"mapped history is invalid: {error}") from error
    fingerprint = hashlib.sha256(mapping.model_dump_json(exclude_none=True).encode("utf-8")).hexdigest()
    return MappedOtelImport(
        history=history,
        diagnostics=OtelDiagnostics(
            mapping_fingerprint=f"sha256:{fingerprint}",
            spans_seen=spans_seen,
            spans_mapped=spans_mapped,
            spans_ignored=spans_seen - spans_mapped,
            events_seen=events_seen,
            events_mapped=events_mapped,
            unmapped_events=dict(sorted(unmapped_events.items())),
            unmapped_attributes=dict(sorted(unmapped_attributes.items())),
            trace_ids=sorted(trace_ids),
            span_ids=sorted(span_ids),
            source_timestamps_seen=timestamps_seen,
            source_time_min_unix_nano=(str(timestamp_bounds[0]) if timestamp_bounds[0] is not None else None),
            source_time_max_unix_nano=(str(timestamp_bounds[1]) if timestamp_bounds[1] is not None else None),
        ),
    )


def _map_events(
    events: list[Any],
    mapping: OtelMapping,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    resources: dict[str, dict[str, Any]],
    unmapped: Counter[str],
    unmapped_attributes: Counter[str],
    operation_selected: bool,
    context: str,
) -> int:
    mapped = 0
    known_names = {mapping.resource_event.name, mapping.read_event.name, mapping.effect_event.name}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise OtelImportError(f"{context}: events[{index}] must be an object")
        name = event.get("name")
        if name not in known_names:
            unmapped[str(name) if name is not None else "<missing>"] += 1
            event_attributes = _attributes(event.get("attributes", []), f"{context}, event {index}")
            _count_unused(event_attributes, set(), "event", unmapped_attributes)
            continue
        if name in {mapping.read_event.name, mapping.effect_event.name} and not operation_selected:
            unmapped[str(name)] += 1
            event_attributes = _attributes(event.get("attributes", []), f"{context}, event {index}")
            _count_unused(event_attributes, set(), f"event:{name}", unmapped_attributes)
            continue
        mapped += 1
        event_context = f"{context}, event {index}"
        event_attributes = _attributes(event.get("attributes", []), event_context)
        event_mapping = {
            mapping.resource_event.name: mapping.resource_event,
            mapping.read_event.name: mapping.read_event,
            mapping.effect_event.name: mapping.effect_event,
        }[name]
        _count_unused(
            event_attributes,
            _event_attribute_keys(event_mapping),
            f"event:{name}",
            unmapped_attributes,
        )
        if name != mapping.resource_event.name:
            continue
        resource_name = _identifier(
            _required(
                mapping.resource_event.resource,
                resource_attributes,
                span_attributes,
                span,
                event_attributes,
                "resource name",
                event_context,
            ),
            "resource name",
            event_context,
        )
        if resource_name in resources:
            raise OtelImportError(f"{event_context}: duplicate initial resource {resource_name!r}")
        version = _required(
            mapping.resource_event.version,
            resource_attributes,
            span_attributes,
            span,
            event_attributes,
            "resource version",
            event_context,
        )
        if isinstance(version, bool) or not isinstance(version, int):
            raise OtelImportError(f"{event_context}: resource version must be an integer")
        resources[resource_name] = {
            "value": _required(
                mapping.resource_event.value,
                resource_attributes,
                span_attributes,
                span,
                event_attributes,
                "resource value",
                event_context,
            ),
            "version": version,
        }
    return mapped


def _mapped_operation_events(
    events: list[Any],
    mapping: OtelMapping,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    context: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reads: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        name = event.get("name")
        if name not in {mapping.read_event.name, mapping.effect_event.name}:
            continue
        event_context = f"{context}, event {index}"
        event_attributes = _attributes(event.get("attributes", []), event_context)
        event_mapping = mapping.read_event if name == mapping.read_event.name else mapping.effect_event
        resource = _identifier(
            _required(
                event_mapping.resource,
                resource_attributes,
                span_attributes,
                span,
                event_attributes,
                "resource name",
                event_context,
            ),
            "resource name",
            event_context,
        )
        value = _required(
            event_mapping.value,
            resource_attributes,
            span_attributes,
            span,
            event_attributes,
            "resource value",
            event_context,
        )
        if name == mapping.read_event.name:
            version = _required(
                mapping.read_event.version,
                resource_attributes,
                span_attributes,
                span,
                event_attributes,
                "resource version",
                event_context,
            )
            reads.append({"resource": resource, "value": value, "version": version})
        else:
            effect_type = _required(
                mapping.effect_event.type,
                resource_attributes,
                span_attributes,
                span,
                event_attributes,
                "effect type",
                event_context,
            )
            effects.append({"type": effect_type, "resource": resource, "value": value})
    return reads, effects


def _status(
    mapping: OperationMapping,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    context: str,
) -> str:
    if mapping.status is None:
        return mapping.default_status
    value = _resolve(mapping.status, resource_attributes, span_attributes, span, None)
    if value is _MISSING:
        return mapping.default_status
    if value in mapping.success_values:
        return "success"
    if value in mapping.failure_values:
        return "failure"
    raise OtelImportError(f"{context}: unmapped operation status {value!r}")


def _predecessors(
    operation: OperationMapping,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    context: str,
) -> list[str]:
    if operation.predecessors is None:
        return []
    value = _resolve(operation.predecessors, resource_attributes, span_attributes, span, None)
    if value is _MISSING:
        return []
    values = value if isinstance(value, list) else [value]
    return [_identifier(item, "predecessor", context) for item in values]


def _required(
    source: ValueSource,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    event_attributes: dict[str, Any] | None,
    field: str,
    context: str,
) -> Any:
    value = _resolve(source, resource_attributes, span_attributes, span, event_attributes)
    if value is _MISSING:
        raise OtelImportError(f"{context}: mapping could not resolve {field}")
    return value


def _resolve(
    source: ValueSource,
    resource_attributes: dict[str, Any],
    span_attributes: dict[str, Any],
    span: dict[str, Any],
    event_attributes: dict[str, Any] | None,
) -> Any:
    if source.source == "literal":
        return source.value
    if source.source == "resource_attribute":
        return resource_attributes.get(source.key, _MISSING)
    if source.source == "span_attribute":
        return span_attributes.get(source.key, _MISSING)
    if source.source == "span_field":
        return span.get(source.key, _MISSING)
    if source.source == "span_status":
        status = span.get("status")
        return status.get("code", _MISSING) if isinstance(status, dict) else _MISSING
    if source.source == "span_links":
        links = span.get("links", [])
        if not isinstance(links, list) or any(
            not isinstance(link, dict) or not isinstance(link.get("spanId"), str) for link in links
        ):
            raise OtelImportError("span links must be objects with string spanId fields")
        return [link["spanId"] for link in links]
    if event_attributes is None:
        return _MISSING
    return event_attributes.get(source.key, _MISSING)


def _identifier(value: Any, field: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise OtelImportError(f"{context}: {field} must resolve to a non-empty string")
    return value


def _used_attribute_keys(mapping: OtelMapping, source_type: str) -> set[str]:
    sources = [
        mapping.history_id,
        mapping.operation.id,
        mapping.operation.agent,
        mapping.operation.status,
        mapping.operation.predecessors,
    ]
    return {source.key for source in sources if source and source.source == source_type and source.key}


def _event_attribute_keys(mapping: ResourceEventMapping | EffectEventMapping) -> set[str]:
    sources = [mapping.resource, mapping.value]
    sources.append(mapping.version if isinstance(mapping, ResourceEventMapping) else mapping.type)
    return {source.key for source in sources if source.source == "event_attribute" and source.key is not None}


def _count_unused(attributes: dict[str, Any], used: set[str], scope: str, counter: Counter[str]) -> None:
    counter.update(f"{scope}:{key}" for key in attributes if key not in used)


def _observe_timestamp(raw: Any, context: str, bounds: list[int | None]) -> None:
    if isinstance(raw, bool) or not isinstance(raw, str | int):
        raise OtelImportError(f"{context}: timestamp must be a decimal string or integer")
    try:
        timestamp = int(raw)
    except ValueError as error:
        raise OtelImportError(f"{context}: invalid timestamp {raw!r}") from error
    if timestamp < 0:
        raise OtelImportError(f"{context}: timestamp must be non-negative")
    bounds[0] = timestamp if bounds[0] is None else min(bounds[0], timestamp)
    bounds[1] = timestamp if bounds[1] is None else max(bounds[1], timestamp)


def _yaml_line(text: str, location: tuple[Any, ...]) -> int:
    node = yaml.compose(text)
    if node is None:
        return 1
    current: Node = node
    for part in location:
        child = _yaml_child(current, part)
        if child is None:
            break
        current = child
    return current.start_mark.line + 1


def _yaml_child(node: Node, part: Any) -> Node | None:
    if isinstance(node, MappingNode):
        for key, value in node.value:
            if key.value == str(part):
                return value
    elif isinstance(node, SequenceNode) and isinstance(part, int) and 0 <= part < len(node.value):
        return node.value[part]
    return None
