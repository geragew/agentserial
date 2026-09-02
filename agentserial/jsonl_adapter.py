from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentserial.models import History


class TraceImportError(ValueError):
    pass


def import_jsonl(path: Path) -> History:
    history_id: str | None = None
    resources: dict[str, dict[str, Any]] = {}
    operations: dict[str, dict[str, Any]] = {}
    operation_order: list[str] = []
    completed: set[str] = set()
    constraints: list[dict[str, str]] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TraceImportError(str(error)) from error

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise TraceImportError(f"line {line_number}: invalid JSON: {error.msg}") from error
        if not isinstance(event, dict):
            raise TraceImportError(f"line {line_number}: event must be a JSON object")
        event_type = event.get("event")
        try:
            if event_type == "history":
                _require_keys(event, {"event", "history_id", "schema_version"}, line_number)
                if history_id is not None:
                    raise TraceImportError(f"line {line_number}: duplicate history event")
                if event["schema_version"] != "0.1":
                    raise TraceImportError(f"line {line_number}: schema_version must be '0.1'")
                history_id = _non_empty(event["history_id"], "history_id", line_number)
            elif event_type == "resource":
                _require_keys(event, {"event", "resource", "value", "version"}, line_number)
                name = _non_empty(event["resource"], "resource", line_number)
                if name in resources:
                    raise TraceImportError(f"line {line_number}: duplicate resource {name!r}")
                resources[name] = {"value": event["value"], "version": event["version"]}
            elif event_type == "operation_start":
                _require_keys(event, {"event", "operation", "agent"}, line_number)
                operation_id = _non_empty(event["operation"], "operation", line_number)
                if operation_id in operations:
                    raise TraceImportError(f"line {line_number}: duplicate operation {operation_id!r}")
                operations[operation_id] = {
                    "id": operation_id,
                    "agent": _non_empty(event["agent"], "agent", line_number),
                    "status": "success",
                    "reads": [],
                    "effects": [],
                }
                operation_order.append(operation_id)
            elif event_type == "read":
                _require_keys(event, {"event", "operation", "resource", "value", "version"}, line_number)
                operation = _active_operation(event["operation"], operations, completed, line_number)
                operation["reads"].append(
                    {"resource": event["resource"], "value": event["value"], "version": event["version"]}
                )
            elif event_type == "effect":
                _require_keys(event, {"event", "operation", "type", "resource", "value"}, line_number)
                operation = _active_operation(event["operation"], operations, completed, line_number)
                operation["effects"].append(
                    {"type": event["type"], "resource": event["resource"], "value": event["value"]}
                )
            elif event_type == "operation_end":
                _require_keys(event, {"event", "operation", "status"}, line_number)
                operation = _active_operation(event["operation"], operations, completed, line_number)
                operation["status"] = event["status"]
                completed.add(operation["id"])
            elif event_type == "order":
                _require_keys(event, {"event", "before", "after"}, line_number)
                constraints.append({"before": event["before"], "after": event["after"]})
            else:
                raise TraceImportError(f"line {line_number}: unknown event type {event_type!r}")
        except KeyError as error:
            raise TraceImportError(f"line {line_number}: missing field {error.args[0]!r}") from error

    if history_id is None:
        raise TraceImportError("trace is missing a history event")
    unfinished = [operation_id for operation_id in operation_order if operation_id not in completed]
    if unfinished:
        raise TraceImportError(f"operations missing operation_end: {', '.join(unfinished)}")
    document = {
        "schema_version": "0.1",
        "history_id": history_id,
        "initial_state": resources,
        "operations": [operations[operation_id] for operation_id in operation_order],
        "order": constraints,
    }
    try:
        return History.model_validate(document)
    except ValidationError as error:
        raise TraceImportError(f"imported history is invalid: {error}") from error


def _require_keys(event: dict[str, Any], expected: set[str], line_number: int) -> None:
    actual = set(event)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise TraceImportError(f"line {line_number}: missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise TraceImportError(f"line {line_number}: unknown fields: {', '.join(sorted(unknown))}")


def _non_empty(value: Any, field: str, line_number: int) -> str:
    if not isinstance(value, str) or not value:
        raise TraceImportError(f"line {line_number}: {field} must be a non-empty string")
    return value


def _active_operation(
    operation_id: Any,
    operations: dict[str, dict[str, Any]],
    completed: set[str],
    line_number: int,
) -> dict[str, Any]:
    if operation_id not in operations:
        raise TraceImportError(f"line {line_number}: unknown operation {operation_id!r}")
    if operation_id in completed:
        raise TraceImportError(f"line {line_number}: operation {operation_id!r} is already complete")
    return operations[operation_id]

