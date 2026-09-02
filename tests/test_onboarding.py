from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from typer.testing import CliRunner

from agentserial.cli import app
from agentserial.jsonl_adapter import import_jsonl
from agentserial.models import VerdictStatus
from agentserial.checker import check
from agentserial.parsing import load_contract


runner = CliRunner()
ROOT = Path(__file__).parents[1]


def test_demo_runs_without_files() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "SCHEDULE_DEPENDENT" in result.stdout


def test_init_creates_runnable_starter(tmp_path: Path) -> None:
    starter = tmp_path / "starter"
    initialized = runner.invoke(app, ["init", str(starter)])
    assert initialized.exit_code == 0
    assert {path.name for path in starter.iterdir()} == {"history.json", "contract.yaml", "events.jsonl"}
    checked = runner.invoke(
        app,
        ["check", str(starter / "history.json"), "--contract", str(starter / "contract.yaml")],
    )
    assert checked.exit_code == 1
    assert "SCHEDULE_DEPENDENT" in checked.stdout


def test_init_refuses_to_overwrite(tmp_path: Path) -> None:
    starter = tmp_path / "starter"
    assert runner.invoke(app, ["init", str(starter)]).exit_code == 0
    result = runner.invoke(app, ["init", str(starter)])
    assert result.exit_code == 2
    assert "Refusing to overwrite" in result.stdout


def test_jsonl_import_is_equivalent_to_starter_history(tmp_path: Path) -> None:
    trace = ROOT / "examples" / "08_jsonl_trace" / "events.jsonl"
    output = tmp_path / "history.json"
    result = runner.invoke(app, ["import-jsonl", str(trace), "--output", str(output)])
    assert result.exit_code == 0
    imported = import_jsonl(trace)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == json.loads(imported.model_dump_json())
    contract = load_contract(ROOT / "examples" / "08_jsonl_trace" / "contract.yaml")
    assert check(imported, contract).status == VerdictStatus.SCHEDULE_DEPENDENT


def test_jsonl_import_reports_line_number(tmp_path: Path) -> None:
    trace = tmp_path / "broken.jsonl"
    trace.write_text('{"event":"history","history_id":"x","schema_version":"0.1"}\nnot-json\n', encoding="utf-8")
    result = runner.invoke(app, ["import-jsonl", str(trace), "--output", str(tmp_path / "out.json")])
    assert result.exit_code == 2
    assert "line 2" in result.stdout


def test_validate_does_not_run_replay_search() -> None:
    example = ROOT / "examples" / "01_overspend"
    result = runner.invoke(
        app,
        ["validate", str(example / "history.json"), "--contract", str(example / "contract.yaml")],
    )
    assert result.exit_code == 0
    assert "VALID" in result.stdout


def test_start_launches_complete_workspace(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(app, ["start", "--port", "9123", "--no-browser"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:9123/app/" in result.stdout
    assert calls == [
        (("agentserial.api:app",), {"host": "127.0.0.1", "port": 9123, "log_level": "warning"})
    ]


def test_start_requires_api_key_for_public_binding(monkeypatch) -> None:
    monkeypatch.delenv("AGENTSERIAL_API_KEY", raising=False)
    result = runner.invoke(app, ["start", "--host", "0.0.0.0", "--no-browser"])
    assert result.exit_code == 2
    assert "AGENTSERIAL_API_KEY is required" in result.stdout
