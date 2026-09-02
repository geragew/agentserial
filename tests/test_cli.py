from pathlib import Path

from typer.testing import CliRunner

from agentserial.cli import app


ROOT = Path(__file__).parents[1]
runner = CliRunner()


def test_cli_exposes_check_subcommand() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def test_cli_schedule_dependent() -> None:
    example = ROOT / "examples" / "06_schedule_dependent"
    result = runner.invoke(
        app,
        ["check", str(example / "history.json"), "--contract", str(example / "contract.yaml")],
    )
    assert result.exit_code == 1
    assert "SCHEDULE_DEPENDENT" in result.stdout
    assert "credit -> debit" in result.stdout
    assert "debit -> credit" in result.stdout


def test_cli_explains_inconsistent_history() -> None:
    example = ROOT / "examples" / "02_inventory_race"
    result = runner.invoke(
        app,
        ["check", str(example / "history.json"), "--contract", str(example / "contract.yaml")],
    )
    assert result.exit_code == 1
    assert "INCONSISTENT_HISTORY" in result.stdout
    assert "Read conflicts" in result.stdout
    assert "replay state was" in result.stdout


def test_cli_generates_standalone_html_report(tmp_path: Path) -> None:
    example = ROOT / "examples" / "01_overspend"
    output = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(example / "history.json"),
            "--contract",
            str(example / "contract.yaml"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    report = output.read_text(encoding="utf-8")
    assert "CONTRACT_FAIL" in report
    assert "spend-a" in report
    assert "spend-b" in report
    assert "<style>" in report
    assert "http://" not in report and "https://" not in report
