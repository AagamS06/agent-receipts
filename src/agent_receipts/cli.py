"""Command-line entry point for agent-receipts."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agent_receipts import __version__
from agent_receipts.adapters import load
from agent_receipts.discovery import find_session_files, parse_since
from agent_receipts.models import Session
from agent_receipts.policy import load_policy
from agent_receipts.receipt import build
from agent_receipts.redact import Redactor
from agent_receipts.render import to_json, to_markdown
from agent_receipts.risk import RULES, fails

app = typer.Typer(
    add_completion=False,
    help="Turn coding-agent session logs into reviewable receipts.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agent-receipts {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """agent-receipts — show your work, agent."""


def _within(cwd: str | None, root: Path) -> bool:
    if not cwd:
        return False
    try:
        Path(cwd).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _recent_sessions(since: str, repo: Path | None) -> list[Session]:
    try:
        seconds = parse_since(since)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    out = []
    for f in sorted(find_session_files(seconds), key=lambda f: f.modified, reverse=True):
        try:
            s = load(f.path, f.harness)
        except (OSError, ValueError):
            continue
        if repo is None or _within(s.cwd, repo):
            out.append(s)
    return out


@app.command()
def scan(
    since: str = typer.Option("24h", help="Look back window, e.g. 30m, 24h, 7d."),
    repo: Path = typer.Option(
        None, help="Only sessions whose working directory is inside this folder."
    ),
) -> None:
    """List recent Claude Code / Codex sessions with their verification verdict."""
    sessions = _recent_sessions(since, repo)
    if not sessions:
        console.print(f"No Claude Code or Codex sessions found in the last {since}.")
        raise typer.Exit(code=3)
    policy = load_policy(Path(".agent-receipts.toml"))
    table = Table(title=f"Agent sessions (last {since})")
    for col in ("Harness", "Ended", "Verdict", "Findings", "Folder"):
        table.add_column(col, overflow="fold")
    for s in sessions:
        r = build([s], policy)
        ended = s.ended_at.astimezone().strftime("%Y-%m-%d %H:%M") if s.ended_at else "?"
        worst = r.findings[0].severity if r.findings else "-"
        table.add_row(
            s.harness,
            ended,
            r.verdict.status,
            f"{len(r.findings)} (worst: {worst})",
            (s.cwd or "?").replace(str(Path.home()), "~"),
        )
    console.print(table)


@app.command()
def render(
    files: list[Path] = typer.Argument(
        None, help="Session .jsonl files. Default: the latest session for --repo."
    ),
    repo: Path = typer.Option(Path("."), help="Repository the agent worked in."),
    since: str = typer.Option("24h", help="Look back window when no files are given."),
    all_sessions: bool = typer.Option(
        False, "--all", help="Combine every matching session in the window."
    ),
    fmt: str = typer.Option("md", "--format", "-f", help="md or json."),
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
    policy_path: Path = typer.Option(
        None, "--policy", help="Policy file (default: <repo>/.agent-receipts.toml)."
    ),
) -> None:
    """Build a receipt. Exit 0 = clean, 1 = failed checks or a finding at/above fail_on,
    2 = bad input, 3 = no session found."""
    if fmt not in {"md", "json"}:
        console.print("[red]error:[/red] --format must be md or json")
        raise typer.Exit(code=2)
    policy = load_policy(policy_path or repo / ".agent-receipts.toml")
    sessions: list[Session] = []
    for f in files or []:
        if not f.is_file():
            console.print(f"[red]error:[/red] no such file: {f}")
            raise typer.Exit(code=2)
        try:
            sessions.append(load(f))
        except ValueError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=2) from exc
    if not files:
        found = _recent_sessions(since, repo)
        sessions = found if all_sessions else found[:1]
    if not sessions:
        console.print(
            f"No agent session for {repo.resolve()} in the last {since}. "
            "Pass a session file, or widen --since."
        )
        raise typer.Exit(code=3)
    receipt = Redactor(policy.extra_patterns, policy.max_output_chars).receipt(
        build(sessions, policy, str(repo.resolve()) if not files else None)
    )
    text = to_json(receipt) if fmt == "json" else to_markdown(receipt)
    if out:
        out.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        console.print(f"Wrote {out} · {receipt.verdict.status} · {len(receipt.findings)} findings")
    else:
        typer.echo(text)
    bad = receipt.verdict.status == "FAILED" or (
        receipt.verdict.status == "STALE" and policy.stale_is_failure
    )
    if bad or fails(receipt.findings, policy.fail_on):
        raise typer.Exit(code=1)


@app.command()
def rules() -> None:
    """List built-in risk rules."""
    table = Table(title="Built-in rules")
    for col in ("Id", "Severity", "Title"):
        table.add_column(col)
    for r in RULES:
        table.add_row(r.id, r.severity, r.title)
    console.print(table)


if __name__ == "__main__":
    app()
