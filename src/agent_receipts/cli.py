"""Command-line entry point for agent-receipts."""

from __future__ import annotations

import os
import re
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from agent_receipts import __version__
from agent_receipts.adapters import load
from agent_receipts.discovery import (
    belongs_to,
    changed_files,
    edits_in,
    find_session_files,
    parse_since,
    touches,
)
from agent_receipts.github import CURRENT_REPO, Publisher, PublishError
from agent_receipts.models import Receipt, Session
from agent_receipts.policy import Policy, load_policy
from agent_receipts.receipt import build
from agent_receipts.redact import Redactor
from agent_receipts.render import to_json, to_markdown
from agent_receipts.risk import RULES, fails
from agent_receipts.schema import schema_text

app = typer.Typer(
    add_completion=False,
    help="Turn coding-agent session logs into reviewable receipts.",
    no_args_is_help=True,
)
console = Console()
_SLUG = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")


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


def _touch_list(repo: Path, touching: list[str] | None, changed_since: str | None) -> list[str]:
    files = list(touching or [])
    if changed_since:
        try:
            files += changed_files(repo, changed_since)
        except ValueError as exc:
            console.print(f"[red]error:[/red] --changed-since: {exc}")
            raise typer.Exit(code=2) from exc
        if not files:
            console.print(f"No files changed since {changed_since} in {repo.resolve()}.")
            raise typer.Exit(code=3)
    return files


def _recent_sessions(
    since: str, repo: Path | None, touching: list[str] | None = None
) -> list[Session]:
    """Sessions in the window, newest first, that belong to ``repo`` (ran in it or edited
    a file in it) and, when ``touching`` is given, edited at least one of those files."""
    try:
        seconds = parse_since(since)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    root = repo or Path(".")
    out = []
    for f in sorted(find_session_files(seconds), key=lambda f: f.modified, reverse=True):
        try:
            s = load(f.path, f.harness)
        except (OSError, ValueError):
            continue
        if repo is not None and not belongs_to(s, repo):
            continue
        if touching and not touches(s, root, touching):
            continue
        out.append(s)
    return out


@app.command()
def scan(
    since: str = typer.Option("24h", help="Look back window, e.g. 30m, 24h, 7d."),
    repo: Path = typer.Option(
        None, help="Only sessions that ran inside this folder or edited a file in it."
    ),
    touching: list[str] = typer.Option(
        None, "--touching", help="Only sessions that edited this file (repeatable)."
    ),
    changed_since: str = typer.Option(
        None, "--changed-since", help="Only sessions that edited a file changed since this git ref."
    ),
) -> None:
    """List recent Claude Code / Codex sessions with their verification verdict."""
    root = repo or Path(".")
    files = _touch_list(root, touching, changed_since)
    sessions = _recent_sessions(since, repo, files)
    if not sessions:
        console.print(f"No Claude Code or Codex sessions found in the last {since}.")
        raise typer.Exit(code=3)
    policy = load_policy(Path(".agent-receipts.toml"))
    table = Table(title=f"Agent sessions (last {since})")
    for col in ("Harness", "Ended", "Verdict", "Findings", "Edits here", "Folder"):
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
            str(len(edits_in(s, root))),
            (s.cwd or "?").replace(str(Path.home()), "~"),
        )
    console.print(table)


def _load_receipt_json(path: Path) -> Receipt:
    try:
        return Receipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError) as exc:
        first = str(exc).splitlines()[0]
        console.print(f"[red]error:[/red] {path} is not a valid agent-receipts receipt: {first}")
        raise typer.Exit(code=2) from exc


def _make_receipt(
    files: list[Path] | None,
    repo: Path,
    since: str,
    all_sessions: bool,
    touching: list[str] | None,
    changed_since: str | None,
    policy: Policy,
) -> Receipt:
    """Build (and redact) a receipt from session logs, or load one saved with ``-f json``."""
    redactor = Redactor(policy.extra_patterns, policy.max_output_chars)
    given = list(files or [])
    for f in given:
        if not f.is_file():
            console.print(f"[red]error:[/red] no such file: {f}")
            raise typer.Exit(code=2)
    receipts = [f for f in given if f.suffix.lower() == ".json"]
    if receipts:
        if len(given) > 1:
            console.print("[red]error:[/red] pass one receipt .json, or session .jsonl files")
            raise typer.Exit(code=2)
        return redactor.receipt(_load_receipt_json(receipts[0]))
    sessions: list[Session] = []
    for f in given:
        try:
            sessions.append(load(f))
        except ValueError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=2) from exc
    if not given:
        wanted = _touch_list(repo, touching, changed_since)
        found = _recent_sessions(since, repo, wanted)
        sessions = found if all_sessions else found[:1]
    if not sessions:
        scope = " that edited the selected files" if (touching or changed_since) else ""
        console.print(
            f"No agent session{scope} for {repo.resolve()} in the last {since}. "
            "Pass a session file, or widen --since."
        )
        raise typer.Exit(code=3)
    return redactor.receipt(build(sessions, policy, str(repo.resolve()) if not given else None))


def _exit_code(receipt: Receipt, policy: Policy) -> int:
    bad = receipt.verdict.status == "FAILED" or (
        receipt.verdict.status == "STALE" and policy.stale_is_failure
    )
    return 1 if bad or fails(receipt.findings, policy.fail_on) else 0


FILES_ARG = typer.Argument(
    None,
    help="Session .jsonl files, or one receipt .json saved with -f json. "
    "Default: the latest session for --repo.",
)
REPO_OPT = typer.Option(Path("."), help="Repository the agent worked in.")
SINCE_OPT = typer.Option("24h", help="Look back window when no files are given.")
ALL_OPT = typer.Option(False, "--all", help="Combine every matching session in the window.")
TOUCHING_OPT = typer.Option(
    None, "--touching", help="Only sessions that edited this file (repeatable)."
)
CHANGED_OPT = typer.Option(
    None,
    "--changed-since",
    help="Only sessions that edited a file changed since this git ref (e.g. origin/main).",
)
POLICY_OPT = typer.Option(
    None, "--policy", help="Policy file (default: <repo>/.agent-receipts.toml)."
)


@app.command()
def render(
    files: list[Path] = FILES_ARG,
    repo: Path = REPO_OPT,
    since: str = SINCE_OPT,
    all_sessions: bool = ALL_OPT,
    touching: list[str] = TOUCHING_OPT,
    changed_since: str = CHANGED_OPT,
    fmt: str = typer.Option("md", "--format", "-f", help="md or json."),
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
    policy_path: Path = POLICY_OPT,
) -> None:
    """Build a receipt. Exit 0 = clean, 1 = failed checks or a finding at/above fail_on,
    2 = bad input, 3 = no session found."""
    if fmt not in {"md", "json"}:
        console.print("[red]error:[/red] --format must be md or json")
        raise typer.Exit(code=2)
    policy = load_policy(policy_path or repo / ".agent-receipts.toml")
    receipt = _make_receipt(files, repo, since, all_sessions, touching, changed_since, policy)
    text = to_json(receipt) if fmt == "json" else to_markdown(receipt)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        console.print(f"Wrote {out} · {receipt.verdict.status} · {len(receipt.findings)} findings")
    else:
        typer.echo(text)
    code = _exit_code(receipt, policy)
    if code:
        raise typer.Exit(code=code)


@app.command()
def publish(
    files: list[Path] = FILES_ARG,
    pr: int = typer.Option(..., "--pr", min=1, help="Pull request number to comment on."),
    gh_repo: str = typer.Option(
        None,
        "--gh-repo",
        help="GitHub repo as OWNER/NAME (default: the repo gh detects here, or $GH_REPO).",
    ),
    repo: Path = REPO_OPT,
    since: str = SINCE_OPT,
    all_sessions: bool = ALL_OPT,
    touching: list[str] = TOUCHING_OPT,
    changed_since: str = CHANGED_OPT,
    policy_path: Path = POLICY_OPT,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the comment instead of posting it (no network)."
    ),
    no_fail: bool = typer.Option(
        False, "--no-fail", help="Exit 0 after posting even if the receipt has failures."
    ),
) -> None:
    """Post the receipt as one sticky PR comment (created once, then updated in place) using
    your `gh` login. Same exit codes as render, plus 4 = could not post to GitHub."""
    if gh_repo is not None and not _SLUG.fullmatch(gh_repo):
        console.print("[red]error:[/red] --gh-repo must look like OWNER/NAME")
        raise typer.Exit(code=2)
    policy = load_policy(policy_path or repo / ".agent-receipts.toml")
    receipt = _make_receipt(files, repo, since, all_sessions, touching, changed_since, policy)
    body = to_markdown(receipt)
    target = gh_repo or os.environ.get("GH_REPO") or "the current repo"
    if dry_run:
        typer.echo(f"[dry run] would create or update the receipt comment on {target} #{pr}:")
        typer.echo(body)
    else:
        try:
            action, url = Publisher(gh_repo or CURRENT_REPO).upsert(pr, body)
        except PublishError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=4) from exc
        typer.echo(
            f"{action.capitalize()} receipt comment on PR #{pr} · {receipt.verdict.status} · "
            f"{len(receipt.findings)} findings · {url}"
        )
    code = 0 if no_fail else _exit_code(receipt, policy)
    if code:
        raise typer.Exit(code=code)


@app.command()
def schema(
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
    check: Path = typer.Option(
        None, "--check", help="Exit 1 if this file differs from the current schema."
    ),
) -> None:
    """Print the JSON Schema (draft 2020-12) for `render -f json` receipts."""
    text = schema_text()
    if check:
        if not check.is_file():
            console.print(f"[red]error:[/red] no such file: {check}")
            raise typer.Exit(code=2)
        if check.read_text(encoding="utf-8") != text:
            console.print(f"{check} is out of date; run: agent-receipts schema -o {check}")
            raise typer.Exit(code=1)
        console.print(f"{check} is up to date.")
        return
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        console.print(f"Wrote {out}")
    else:
        typer.echo(text, nl=False)


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
