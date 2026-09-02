from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentserial.models import CheckResult, VerdictStatus

STATUS_STYLE = {
    VerdictStatus.ROBUST_PASS: "bold green",
    VerdictStatus.SCHEDULE_DEPENDENT: "bold yellow",
    VerdictStatus.CONTRACT_FAIL: "bold red",
    VerdictStatus.INCONSISTENT_HISTORY: "bold magenta",
    VerdictStatus.INCONCLUSIVE: "bold yellow",
    VerdictStatus.INVALID_HISTORY: "bold red",
    VerdictStatus.INVALID_CONTRACT: "bold red",
}


def render(result: CheckResult, console: Console) -> None:
    console.print(Panel("Correctness classification for agent effect histories", title="AgentSerial"))
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_row("History", result.history_id or "-")
    summary.add_row("Agents", str(result.agents))
    summary.add_row("Operations", str(result.operations))
    summary.add_row("Feasible replays", str(result.feasible_replays))
    summary.add_row("Safe / unsafe", f"{result.safe_replays} / {result.unsafe_replays}")
    console.print(summary)
    console.print(f"\n[{STATUS_STYLE[result.status]}]{result.status.value}[/]")

    if result.safe_witness:
        console.print("\n[bold]Safe witness[/]")
        console.print(" -> ".join(result.safe_witness.order) or "(empty replay)")
    if result.unsafe_witness:
        console.print("\n[bold]Unsafe witness[/]")
        console.print(" -> ".join(result.unsafe_witness.order) or "(empty replay)")
        for violation in result.unsafe_witness.violations:
            console.print(f"  {violation}")
    if result.reduced_counterexample is not None:
        console.print("\n[bold]1-minimal reduced counterexample[/]")
        if not result.counterexample_operations:
            console.print("(initial state)")
        for operation in result.counterexample_operations:
            console.print(f"[bold]{operation.id}[/] ({operation.agent})")
            for read in operation.reads:
                console.print(f"  READ {read.resource}={read.value!r}@v{read.version}")
            for effect in operation.effects:
                console.print(f"  {effect.type.upper()} {effect.resource} {effect.value!r}")
    if result.read_conflicts:
        console.print("\n[bold]Read conflicts[/]")
        for conflict in result.read_conflicts:
            console.print(f"  {conflict}")
    for error in result.errors:
        console.print(f"\n[red]{error}[/]")
