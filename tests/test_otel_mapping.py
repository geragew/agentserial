from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentserial.cli import app
from agentserial.otel_adapter import OtelImportError
from agentserial.otel_mapping import import_otlp_json_mapped, load_otel_mapping

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples/09_opentelemetry"
runner = CliRunner()


def test_declarative_mapping_matches_native_adapter() -> None:
    mapping = load_otel_mapping(EXAMPLE / "mapping.yaml")
    imported = import_otlp_json_mapped(EXAMPLE / "traces.json", mapping)

    assert imported.history.history_id == "otel-schedule-dependent"
    assert [operation.id for operation in imported.history.operations] == ["credit", "debit"]
    assert imported.diagnostics.spans_seen == 2
    assert imported.diagnostics.spans_mapped == 2
    assert imported.diagnostics.spans_ignored == 0
    assert imported.diagnostics.events_seen == 3
    assert imported.diagnostics.events_mapped == 3
    assert imported.diagnostics.unmapped_events == {}
    assert imported.diagnostics.unmapped_attributes == {"resource:service.name": 1}
    assert imported.diagnostics.mapping_fingerprint.startswith("sha256:")
    assert imported.diagnostics.source_timestamps_seen == 4
    assert imported.diagnostics.source_time_min_unix_nano == "1544712660000000000"
    assert imported.diagnostics.source_time_max_unix_nano == "1544712663000000000"
    assert imported.diagnostics.ingestion_time_recorded is False


def test_mapping_can_use_trace_span_status_and_custom_event_attributes(tmp_path: Path) -> None:
    document = json.loads((EXAMPLE / "traces.json").read_text(encoding="utf-8"))
    spans = document["resourceSpans"][0]["scopeSpans"][0]["spans"]
    for span in spans:
        span["status"] = {"code": 1}
        for event in span["events"]:
            event["name"] = {
                "agentserial.resource": "state.initial",
                "agentserial.read": "state.read",
                "agentserial.effect": "state.effect",
            }[event["name"]]
            for attribute in event["attributes"]:
                attribute["key"] = attribute["key"].replace("agentserial.", "company.")
    trace = tmp_path / "custom.json"
    trace.write_text(json.dumps(document), encoding="utf-8")
    mapping_text = (EXAMPLE / "mapping.yaml").read_text(encoding="utf-8")
    mapping_text = mapping_text.replace(
        "source: resource_attribute\n  key: agentserial.history.id", "source: span_field\n  key: traceId"
    )
    mapping_text = mapping_text.replace(
        "source: span_attribute\n    key: agentserial.operation.id", "source: span_field\n    key: spanId"
    )
    mapping_text = mapping_text.replace(
        "status:\n    source: span_attribute\n    key: agentserial.operation.status",
        "status:\n    source: span_status",
    )
    mapping_text = mapping_text.replace("success_values: [success]", "success_values: [1]")
    mapping_text = mapping_text.replace("failure_values: [failure]", "failure_values: [2]")
    mapping_text = mapping_text.replace("agentserial.resource", "company.resource")
    mapping_text = mapping_text.replace("agentserial.effect", "company.effect")
    mapping_text = mapping_text.replace("name: company.resource\n", "name: state.initial\n", 1)
    mapping_text = mapping_text.replace("name: company.read", "name: state.read")
    mapping_text = mapping_text.replace("name: company.effect", "name: state.effect")
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(mapping_text, encoding="utf-8")

    imported = import_otlp_json_mapped(trace, load_otel_mapping(mapping_path))

    assert imported.history.history_id == spans[0]["traceId"]
    assert [operation.id for operation in imported.history.operations] == [
        spans[0]["spanId"],
        spans[1]["spanId"],
    ]
    assert all(operation.status == "success" for operation in imported.history.operations)


def test_diagnostics_account_for_ignored_spans_and_unmapped_events(tmp_path: Path) -> None:
    document = json.loads((EXAMPLE / "traces.json").read_text(encoding="utf-8"))
    spans = document["resourceSpans"][0]["scopeSpans"][0]["spans"]
    spans[0]["events"].append({"name": "exception", "attributes": []})
    spans.append(
        {
            "traceId": spans[0]["traceId"],
            "spanId": "EEE19B7EC3C1B176",
            "name": "unmapped infrastructure span",
            "attributes": [],
            "events": [
                {
                    "name": "agentserial.read",
                    "attributes": [
                        {
                            "key": "agentserial.resource.name",
                            "value": {"stringValue": "balance"},
                        },
                        {"key": "agentserial.resource.value", "value": {"intValue": "0"}},
                        {"key": "agentserial.resource.version", "value": {"intValue": "0"}},
                    ],
                }
            ],
        }
    )
    trace = tmp_path / "extra.json"
    trace.write_text(json.dumps(document), encoding="utf-8")

    imported = import_otlp_json_mapped(trace, load_otel_mapping(EXAMPLE / "mapping.yaml"))

    assert imported.diagnostics.spans_seen == 3
    assert imported.diagnostics.spans_mapped == 2
    assert imported.diagnostics.spans_ignored == 1
    assert imported.diagnostics.unmapped_events == {"agentserial.read": 1, "exception": 1}
    assert imported.diagnostics.events_seen == 5
    assert imported.diagnostics.events_mapped == 3


def test_links_create_order_only_when_mapping_explicitly_selects_them(tmp_path: Path) -> None:
    document = json.loads((EXAMPLE / "traces.json").read_text(encoding="utf-8"))
    spans = document["resourceSpans"][0]["scopeSpans"][0]["spans"]
    spans[1]["links"] = [{"traceId": spans[0]["traceId"], "spanId": spans[0]["spanId"]}]
    for span in spans:
        operation_id = next(
            attribute for attribute in span["attributes"] if attribute["key"] == "agentserial.operation.id"
        )
        operation_id["value"]["stringValue"] = span["spanId"]
    trace = tmp_path / "linked.json"
    trace.write_text(json.dumps(document), encoding="utf-8")
    mapping_text = (
        (EXAMPLE / "mapping.yaml")
        .read_text(encoding="utf-8")
        .replace("source: span_attribute\n    key: agentserial.order.after", "source: span_links")
    )
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(mapping_text, encoding="utf-8")

    imported = import_otlp_json_mapped(trace, load_otel_mapping(mapping_path))

    assert [(edge.before, edge.after) for edge in imported.history.order] == [
        (spans[0]["spanId"], spans[1]["spanId"])
    ]


def test_invalid_mapping_is_rejected_before_trace_processing(tmp_path: Path) -> None:
    mapping = tmp_path / "invalid.yaml"
    mapping.write_text('version: "0.1"\nhistory_id:\n  source: span_field\n', encoding="utf-8")

    with pytest.raises(OtelImportError, match=r"line 3, history_id"):
        load_otel_mapping(mapping)


def test_cli_writes_history_and_diagnostics_sidecar(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    diagnostics = tmp_path / "diagnostics.json"

    result = runner.invoke(
        app,
        [
            "import-otel",
            str(EXAMPLE / "traces.json"),
            "--mapping",
            str(EXAMPLE / "mapping.yaml"),
            "--output",
            str(history),
            "--diagnostics",
            str(diagnostics),
        ],
    )

    assert result.exit_code == 0
    assert "Mapping coverage: 2/2 spans, 3/3 events" in result.stdout
    report = json.loads(diagnostics.read_text(encoding="utf-8"))
    assert report["unmapped_attributes"] == {"resource:service.name": 1}
