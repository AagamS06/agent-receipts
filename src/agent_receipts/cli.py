"""Command-line entry point for agent-receipts."""

from __future__ import annotations

from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from agent_receipts import __version__
from agent_receipts.discovery import find_session_files, parse_since

app = typer.Typer(
    add_completion=False,
    help="Turn coding-agent session logs into reviewable receipts.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"agent-receipts {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """agent-receipts — show your work, agent."""


@app.command()
def scan(
    since: str = typer.Option("24h", help="Look back window, e.g. 30m, 24h, 7d."),
) -> None:
    """List agent session logs found on this machine (Phase 0 stub)."""
    try:
        seconds = parse_since(since)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    files = sorted(find_session_files(seconds), key=lambda f: f.modified, reverse=True)
    if not files:
        console.print(f"No Claude Code or Codex sessions found in the last {since}.")
        raise typer.Exit(code=3)

    table = Table(title=f"Agent sessions (last {since})")
    table.add_column("Harness")
    table.add_column("Modified")
    table.add_column("File", overflow="fold")
    for f in files:
        modified = datetime.fromtimestamp(f.modified).strftime("%Y-%m-%d %H:%M")
        table.add_row(f.harness, modified, str(f.path).replace(str(f.path.home()), "~"))
    console.print(table)
    console.print("[grey58]Verdicts and risk findings arrive in Phase 1–2.[/grey58]")


if __name__ == "__main__":
    app()
