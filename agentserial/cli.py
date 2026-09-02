from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from agentserial.checker import check
from agentserial.formatting import render
from agentserial.invariants import validate_contract_effects, validate_contract_resources
from agentserial.jsonl_adapter import TraceImportError, import_jsonl
from agentserial.models import CheckResult, VerdictStatus
from agentserial.otel_adapter import OtelImportError, import_otlp_json
from agentserial.parsing import load_contract, load_history
from agentserial.report import generate_report


app = typer.Typer(help="Classify parallel agent effect histories against global contracts.")
console = Console()


@app.callback()
def main() -> None:
    """AgentSerial command line interface."""


@app.command()
def demo() -> None:
    """Run a built-in schedule-dependent demonstration."""
    from agentserial.models import Contract, History

    history = History.model_validate(json.loads(_DEMO_HISTORY))
    contract = Contract.model_validate(json.loads(_DEMO_CONTRACT))
    render(check(history, contract), console)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind the API server to")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port for the API server", min=1, max=65535)] = 8000,
) -> None:
    """Run the AgentSerial HTTP API without the browser workspace."""
    import uvicorn

    console.print(f"AgentSerial API: http://{host}:{port} (docs: /docs)")
    uvicorn.run("agentserial.api:app", host=host, port=port)


@app.command()
def start(
    host: Annotated[str, typer.Option(help="Interface to bind the local application to")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port, or 0 to select an available port", min=0, max=65535)] = 0,
    browser: Annotated[bool, typer.Option("--browser/--no-browser", help="Open the workspace automatically")] = True,
) -> None:
    """Start the complete local workspace with zero configuration."""
    import uvicorn

    if host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("AGENTSERIAL_API_KEY"):
        console.print("[red]AGENTSERIAL_API_KEY is required when binding outside localhost.[/]")
        raise typer.Exit(2)
    selected_port = port or _available_port(host)
    browser_host = "localhost" if host in {"0.0.0.0", "::"} else host
    url_host = f"[{browser_host}]" if ":" in browser_host else browser_host
    url = f"http://{url_host}:{selected_port}/app/"
    console.print(f"[green]AgentSerial is ready at {url}[/]")
    console.print("Press Ctrl+C to stop.")
    if browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("agentserial.api:app", host=host, port=selected_port, log_level="warning")


def _available_port(host: str) -> int:
    bind_host = "127.0.0.1" if host == "localhost" else host
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as listener:
        listener.bind((bind_host, 0))
        return int(listener.getsockname()[1])


def _open_when_ready(url: str) -> None:
    health_url = f"{url.rsplit('/app/', 1)[0]}/health"
    for _ in range(50):
        try:
            with urllib.request.urlopen(health_url, timeout=0.25) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.1)


@app.command("init")
def initialize(
    directory: Annotated[Path, typer.Argument(help="Directory for starter files")] = Path("agentserial-starter"),
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing starter files")] = False,
) -> None:
    """Create a runnable starter history, contract, and JSONL trace."""
    files = {
        "history.json": _DEMO_HISTORY + "\n",
        "contract.yaml": _STARTER_CONTRACT,
        "events.jsonl": _STARTER_JSONL,
    }
    existing = [name for name in files if (directory / name).exists()]
    if existing and not force:
        console.print(f"[red]Refusing to overwrite: {', '.join(existing)}[/]")
        raise typer.Exit(2)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    console.print(f"Created starter files in {directory}")
    console.print(f"Run: agentserial check {directory / 'history.json'} --contract {directory / 'contract.yaml'}")


@app.command("import-jsonl")
def import_jsonl_command(
    trace_path: Annotated[Path, typer.Argument(help="Incremental JSONL trace")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Generated history JSON")] = Path("history.json"),
    force: Annotated[bool, typer.Option("--force", help="Overwrite the output file")] = False,
) -> None:
    """Convert an incremental, runtime-neutral JSONL trace into a history."""
    if output.exists() and not force:
        console.print(f"[red]Refusing to overwrite: {output}[/]")
        raise typer.Exit(2)
    try:
        history = import_jsonl(trace_path)
    except TraceImportError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(history.model_dump_json(indent=2) + "\n", encoding="utf-8")
    console.print(f"Imported {len(history.operations)} operations into {output}")


@app.command("import-otel")
def import_otel_command(
    trace_path: Annotated[Path, typer.Argument(help="OTLP/JSON trace export")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Generated history JSON")] = Path("history.json"),
    force: Annotated[bool, typer.Option("--force", help="Overwrite the output file")] = False,
) -> None:
    """Convert an AgentSerial-instrumented OTLP/JSON trace into a history."""
    if output.exists() and not force:
        console.print(f"[red]Refusing to overwrite: {output}[/]")
        raise typer.Exit(2)
    try:
        history = import_otlp_json(trace_path)
    except OtelImportError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(history.model_dump_json(indent=2) + "\n", encoding="utf-8")
    console.print(f"Imported {len(history.operations)} OpenTelemetry operations into {output}")


@app.command()
def validate(
    history_path: Annotated[Path, typer.Argument(help="History document")],
    contract_path: Annotated[Path, typer.Option("--contract", "-c", help="Contract document")],
) -> None:
    """Validate history and contract without exploring replay orders."""
    try:
        history = load_history(history_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        console.print(f"[red]INVALID_HISTORY: {error}[/]")
        raise typer.Exit(2)
    try:
        contract = load_contract(contract_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        console.print(f"[red]INVALID_CONTRACT: {error}[/]")
        raise typer.Exit(2)
    errors = validate_contract_resources(contract, history.initial_state)
    errors.extend(validate_contract_effects(contract, history))
    if errors:
        for error in errors:
            console.print(f"[red]INVALID_CONTRACT: {error}[/]")
        raise typer.Exit(2)
    console.print(
        f"[green]VALID[/] {history.history_id}: "
        f"{len(history.operations)} operations, {len(contract.invariants)} invariants"
    )


@app.command()
def report(
    history_path: Annotated[Path, typer.Argument(help="History document")],
    contract_path: Annotated[Path, typer.Option("--contract", "-c", help="Contract document")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Standalone HTML report")] = Path("agentserial-report.html"),
    force: Annotated[bool, typer.Option("--force", help="Overwrite the output file")] = False,
) -> None:
    """Generate a standalone visual report from a real check."""
    if output.exists() and not force:
        console.print(f"[red]Refusing to overwrite: {output}[/]")
        raise typer.Exit(2)
    try:
        history = load_history(history_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        console.print(f"[red]INVALID_HISTORY: {error}[/]")
        raise typer.Exit(2)
    try:
        contract = load_contract(contract_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        console.print(f"[red]INVALID_CONTRACT: {error}[/]")
        raise typer.Exit(2)
    result = check(history, contract)
    if result.status in {VerdictStatus.INVALID_CONTRACT, VerdictStatus.INCONCLUSIVE}:
        for error in result.errors:
            console.print(f"[red]{result.status.value}: {error}[/]")
        raise typer.Exit(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_report(history, contract, result), encoding="utf-8")
    console.print(f"Generated {result.status.value} report: {output}")


@app.command("check")
def check_command(
    history_path: Annotated[Path, typer.Argument(help="History document (.json, .yaml, or .yml)")],
    contract_path: Annotated[Path, typer.Option("--contract", "-c", help="Contract document")],
    max_operations: Annotated[int, typer.Option(help="Maximum successful operations")] = 10,
    max_prefixes: Annotated[int, typer.Option(help="Maximum explored replay prefixes")] = 100_000,
    json_output: Annotated[bool, typer.Option("--json", help="Emit structured JSON")] = False,
) -> None:
    """Check and classify one history."""
    try:
        history = load_history(history_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        _finish(CheckResult(status=VerdictStatus.INVALID_HISTORY, errors=[str(error)]), json_output)
        raise typer.Exit(2)
    try:
        contract = load_contract(contract_path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        _finish(CheckResult(status=VerdictStatus.INVALID_CONTRACT, errors=[str(error)]), json_output)
        raise typer.Exit(2)

    result = check(
        history,
        contract,
        max_operations=max_operations,
        max_prefixes=max_prefixes,
    )
    _finish(result, json_output)
    if result.status != VerdictStatus.ROBUST_PASS:
        raise typer.Exit(2 if result.status in {VerdictStatus.INCONCLUSIVE, VerdictStatus.INVALID_CONTRACT} else 1)


def _finish(result: CheckResult, json_output: bool) -> None:
    if json_output:
        console.print_json(result.model_dump_json())
    else:
        render(result, console)


_DEMO_HISTORY = """{
  "schema_version": "0.1",
  "history_id": "schedule-dependent-balance",
  "initial_state": {"balance": {"value": 0, "version": 0}},
  "operations": [
    {"id": "credit", "agent": "agent-a", "effects": [{"type": "increment", "resource": "balance", "value": 1}]},
    {"id": "debit", "agent": "agent-b", "effects": [{"type": "increment", "resource": "balance", "value": -1}]}
  ],
  "order": []
}"""

_DEMO_CONTRACT = """{
  "version": "0.1",
  "invariants": [{"id": "non-negative", "type": "min_value", "resource": "balance", "min": 0}]
}"""

_STARTER_CONTRACT = """version: "0.1"
invariants:
  - id: non-negative
    type: min_value
    resource: balance
    min: 0
"""

_STARTER_JSONL = """{"event":"history","history_id":"schedule-dependent-balance","schema_version":"0.1"}
{"event":"resource","resource":"balance","value":0,"version":0}
{"event":"operation_start","operation":"credit","agent":"agent-a"}
{"event":"effect","operation":"credit","type":"increment","resource":"balance","value":1}
{"event":"operation_end","operation":"credit","status":"success"}
{"event":"operation_start","operation":"debit","agent":"agent-b"}
{"event":"effect","operation":"debit","type":"increment","resource":"balance","value":-1}
{"event":"operation_end","operation":"debit","status":"success"}
"""


if __name__ == "__main__":
    app()
