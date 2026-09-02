from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentserial.models import History


class OtelImportError(ValueError):
    pass


def import_otlp_json(path: Path) -> History:
    documents = _load_documents(path)
    history_ids: set[str] = set()
    resources: dict[str, dict[str, Any]] = {}
    operations: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    constraints: list[dict[str, str]] = []

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
            history_id = resource_attributes.get("agentserial.history.id")
            if history_id is not None:
                if not isinstance(history_id, str) or not history_id:
                    raise OtelImportError(f"{context}: agentserial.history.id must be a non-empty string")
                history_ids.add(history_id)
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
                    attributes = _attributes(span.get("attributes", []), span_context)
                    events = span.get("events", [])
                    if not isinstance(events, list):
                        raise OtelImportError(f"{span_context}: events must be an array")
                    _collect_resources(events, resources, span_context)
                    operation_id = attributes.get("agentserial.operation.id")
                    if operation_id is None:
                        continue
                    if not isinstance(operation_id, str) or not operation_id:
                        raise OtelImportError(f"{span_context}: operation ID must be a non-empty string")
                    if operation_id in operation_ids:
                        raise OtelImportError(f"{span_context}: duplicate operation {operation_id!r}")
                    operation_ids.add(operation_id)
                    agent_id = attributes.get("agentserial.agent.id")
                    if not isinstance(agent_id, str) or not agent_id:
                        raise OtelImportError(f"{span_context}: operation span requires agentserial.agent.id")
                    status = attributes.get("agentserial.operation.status", "success")
                    if status not in {"success", "failure"}:
                        raise OtelImportError(f"{span_context}: operation status must be success or failure")
                    reads, effects = _operation_events(events, span_context)
                    operations.append(
                        {
                            "id": operation_id,
                            "agent": agent_id,
                            "status": status,
                            "reads": reads,
                            "effects": effects,
                        }
                    )
                    predecessors = attributes.get("agentserial.order.after", [])
                    if isinstance(predecessors, str):
                        predecessors = [predecessors]
                    if not isinstance(predecessors, list) or any(
                        not isinstance(item, str) for item in predecessors
                    ):
                        raise OtelImportError(
                            f"{span_context}: agentserial.order.after must be a string array"
                        )
                    constraints.extend(
                        {"before": predecessor, "after": operation_id} for predecessor in predecessors
                    )

    if len(history_ids) != 1:
        raise OtelImportError(
            f"OTLP input must contain exactly one distinct agentserial.history.id; found {len(history_ids)}"
        )
    document = {
        "schema_version": "0.1",
        "history_id": next(iter(history_ids)),
        "initial_state": resources,
        "operations": operations,
        "order": constraints,
    }
    try:
        return History.model_validate(document)
    except ValidationError as error:
        raise OtelImportError(f"imported history is invalid: {error}") from error


def _load_documents(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise OtelImportError(str(error)) from error
    try:
        parsed = json.loads(text)
        documents = [parsed]
    except json.JSONDecodeError:
        documents = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise OtelImportError(f"line {line_number}: invalid OTLP JSON: {error.msg}") from error
    if not documents or any(not isinstance(document, dict) for document in documents):
        raise OtelImportError("OTLP input must contain one or more JSON objects")
    return documents


def _attributes(raw_attributes: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw_attributes, list):
        raise OtelImportError(f"{context}: attributes must be an array")
    attributes: dict[str, Any] = {}
    for index, attribute in enumerate(raw_attributes):
        if not isinstance(attribute, dict) or not isinstance(attribute.get("key"), str):
            raise OtelImportError(f"{context}: attributes[{index}] is invalid")
        key = attribute["key"]
        if key in attributes:
            raise OtelImportError(f"{context}: duplicate attribute {key!r}")
        attributes[key] = _any_value(attribute.get("value"), f"{context}, attribute {key!r}")
    return attributes


def _any_value(raw: Any, context: str) -> Any:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise OtelImportError(f"{context}: AnyValue must contain exactly one value field")
    kind, value = next(iter(raw.items()))
    if kind == "stringValue":
        if not isinstance(value, str):
            raise OtelImportError(f"{context}: stringValue must be a string")
        return value
    if kind == "boolValue":
        if not isinstance(value, bool):
            raise OtelImportError(f"{context}: boolValue must be a boolean")
        return value
    if kind == "intValue":
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise OtelImportError(f"{context}: intValue must be a decimal string or integer")
        try:
            return int(value)
        except ValueError as error:
            raise OtelImportError(f"{context}: invalid intValue {value!r}") from error
    if kind == "doubleValue":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OtelImportError(f"{context}: doubleValue must be numeric")
        return float(value)
    if kind == "arrayValue":
        if not isinstance(value, dict) or not isinstance(value.get("values", []), list):
            raise OtelImportError(f"{context}: arrayValue.values must be an array")
        return [_any_value(item, context) for item in value.get("values", [])]
    raise OtelImportError(f"{context}: unsupported AnyValue field {kind!r}")


def _collect_resources(events: list[Any], resources: dict[str, dict[str, Any]], context: str) -> None:
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise OtelImportError(f"{context}: events[{index}] must be an object")
        if event.get("name") != "agentserial.resource":
            continue
        attributes = _attributes(event.get("attributes", []), f"{context}, resource event {index}")
        name = attributes.get("agentserial.resource.name")
        version = attributes.get("agentserial.resource.version")
        if not isinstance(name, str) or not name:
            raise OtelImportError(f"{context}: resource event requires agentserial.resource.name")
        if name in resources:
            raise OtelImportError(f"{context}: duplicate initial resource {name!r}")
        if (
            "agentserial.resource.value" not in attributes
            or isinstance(version, bool)
            or not isinstance(version, int)
        ):
            raise OtelImportError(f"{context}: resource event requires value and integer version")
        resources[name] = {"value": attributes["agentserial.resource.value"], "version": version}


def _operation_events(events: list[Any], context: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reads: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        name = event.get("name")
        if name not in {"agentserial.read", "agentserial.effect"}:
            continue
        attributes = _attributes(event.get("attributes", []), f"{context}, event {index}")
        resource = attributes.get("agentserial.resource.name")
        if not isinstance(resource, str) or not resource:
            raise OtelImportError(f"{context}: {name} requires agentserial.resource.name")
        if "agentserial.resource.value" not in attributes:
            raise OtelImportError(f"{context}: {name} requires agentserial.resource.value")
        if name == "agentserial.read":
            version = attributes.get("agentserial.resource.version")
            if isinstance(version, bool) or not isinstance(version, int):
                raise OtelImportError(f"{context}: read event requires integer resource version")
            reads.append(
                {"resource": resource, "value": attributes["agentserial.resource.value"], "version": version}
            )
        else:
            effect_type = attributes.get("agentserial.effect.type")
            if effect_type not in {"set", "increment", "append"}:
                raise OtelImportError(f"{context}: effect event has invalid agentserial.effect.type")
            effects.append(
                {"type": effect_type, "resource": resource, "value": attributes["agentserial.resource.value"]}
            )
    return reads, effects
