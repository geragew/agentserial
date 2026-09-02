from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agentserial.checker import check
from agentserial.cli import app
from agentserial.models import VerdictStatus
from agentserial.otel_adapter import import_otlp_json
from agentserial.parsing import load_contract, load_history


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "09_opentelemetry"
runner = CliRunner()


def test_otlp_json_import_classifies_schedule_dependency() -> None:
    history = import_otlp_json(EXAMPLE / "traces.json")
    contract = load_contract(EXAMPLE / "contract.yaml")
    result = check(history, contract)
    assert history.history_id == "otel-schedule-dependent"
    assert history.initial_state["balance"].value == 0
    assert result.status == VerdictStatus.SCHEDULE_DEPENDENT


def test_timestamps_do_not_create_order() -> None:
    history = import_otlp_json(EXAMPLE / "traces.json")
    assert history.order == []
    assert history.operations[0].id == "credit"
    assert history.operations[1].id == "debit"


def test_explicit_after_attribute_creates_order(tmp_path: Path) -> None:
    document = json.loads((EXAMPLE / "traces.json").read_text(encoding="utf-8"))
    debit = document["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    debit["attributes"].append(
        {
            "key": "agentserial.order.after",
            "value": {"arrayValue": {"values": [{"stringValue": "credit"}]}},
        }
    )
    trace = tmp_path / "ordered.json"
    trace.write_text(json.dumps(document), encoding="utf-8")
    history = import_otlp_json(trace)
    result = check(history, load_contract(EXAMPLE / "contract.yaml"))
    assert [(edge.before, edge.after) for edge in history.order] == [("credit", "debit")]
    assert result.status == VerdictStatus.ROBUST_PASS


def test_cli_import_otel_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "history.json"
    imported = runner.invoke(
        app,
        ["import-otel", str(EXAMPLE / "traces.json"), "--output", str(output)],
    )
    assert imported.exit_code == 0
    assert "OpenTelemetry operations" in imported.stdout
    history = load_history(output)
    assert len(history.operations) == 2
    checked = runner.invoke(
        app,
        ["check", str(output), "--contract", str(EXAMPLE / "contract.yaml")],
    )
    assert checked.exit_code == 1
    assert "SCHEDULE_DEPENDENT" in checked.stdout


def test_missing_history_attribute_is_readable_error(tmp_path: Path) -> None:
    document = json.loads((EXAMPLE / "traces.json").read_text(encoding="utf-8"))
    attributes = document["resourceSpans"][0]["resource"]["attributes"]
    attributes[:] = [item for item in attributes if item["key"] != "agentserial.history.id"]
    trace = tmp_path / "missing-history.json"
    trace.write_text(json.dumps(document), encoding="utf-8")
    result = runner.invoke(app, ["import-otel", str(trace), "--output", str(tmp_path / "out.json")])
    assert result.exit_code == 2
    assert "exactly one distinct agentserial.history.id" in result.stdout

