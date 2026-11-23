"""Locate coding-agent session logs on this machine and match them to a repository.

A session belongs to a repo when its working directory is inside the repo, or when it
edited at least one file inside the repo (agents started in a parent folder or another
worktree). ``--touching`` / ``--changed-since`` narrow that to sessions that edited
specific files, e.g. the files of the pull request under review.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from agent_receipts.models import Session


@dataclass(frozen=True)
class SessionFile:
    harness: str
    path: Path
    modified: float


def _claude_root() -> Path:
    return Path.home() / ".claude" / "projects"


def _codex_root() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"


def find_session_files(since_seconds: float) -> Iterator[SessionFile]:
    """Yield session JSONL files modified within the last ``since_seconds``."""
    cutoff = time.time() - since_seconds
    roots = {
        "claude_code": (_claude_root(), "*.jsonl"),
        "codex": (_codex_root(), "rollout-*.jsonl"),
    }
    for harness, (root, pattern) in roots.items():
        if not root.is_dir():
            continue
        for path in root.rglob(pattern):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                yield SessionFile(harness=harness, path=path, modified=mtime)


def parse_since(value: str) -> float:
    """Parse durations like ``30m``, ``24h`` or ``7d`` into seconds."""
    units = {"m": 60, "h": 3600, "d": 86400}
    value = value.strip().lower()
    if len(value) < 2 or value[-1] not in units or not value[:-1].isdigit():
        raise ValueError(f"invalid duration {value!r}; use e.g. 30m, 24h, 7d")
    return int(value[:-1]) * units[value[-1]]


def _resolve(path: str, base: str | None) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute() and base:
        p = Path(base) / p
    return Path(os.path.normpath(p))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def edited_paths(session: Session) -> list[Path]:
    """Absolute, normalised paths of every file the session edited (relative to its cwd)."""
    out: list[Path] = []
    for ev in session.events:
        if ev.kind != "file_edit":
            continue
        for raw in ev.paths:
            p = _resolve(raw, session.cwd)
            if p not in out:
                out.append(p)
    return out


def edits_in(session: Session, root: Path) -> list[Path]:
    """Edited files that fall inside ``root``."""
    base = Path(os.path.normpath(root.resolve()))
    return [p for p in edited_paths(session) if _inside(p, base)]


def belongs_to(session: Session, root: Path) -> bool:
    """True when the session ran inside ``root`` or edited a file inside it."""
    base = Path(os.path.normpath(root.resolve()))
    if session.cwd and _inside(_resolve(session.cwd, None), base):
        return True
    return bool(edits_in(session, root))


def touches(session: Session, root: Path, files: list[str]) -> list[str]:
    """Which of ``files`` (paths relative to ``root``, or absolute) the session edited."""
    base = Path(os.path.normpath(root.resolve()))
    edited = set(edited_paths(session))
    hits: list[str] = []
    for f in files:
        if _resolve(f, str(base)) in edited and f not in hits:
            hits.append(f)
    return hits


def changed_files(root: Path, ref: str) -> list[str]:
    """Files changed since git ``ref`` (committed + working tree + untracked), repo-relative.

    Raises ``ValueError`` when ``root`` is not a git repo or ``ref`` is unknown.
    """

    def git(*args: str) -> list[str]:
        try:
            out = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"git failed: {exc}") from exc
        if out.returncode != 0:
            msg = out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "git error"
            raise ValueError(f"git {' '.join(args[:2])}: {msg}")
        return [line for line in out.stdout.splitlines() if line.strip()]

    top = git("rev-parse", "--show-toplevel")[0]
    files = git("diff", "--name-only", ref, "--")
    files += git("ls-files", "--others", "--exclude-standard")
    prefix = Path(os.path.normpath(root.resolve()))
    out: list[str] = []
    for f in files:
        absolute = Path(top) / f
        try:
            rel = str(absolute.relative_to(prefix))
        except ValueError:
            continue
        if rel not in out:
            out.append(rel)
    return out
