"""Locate coding-agent session logs on this machine.

Phase 0: only lists candidate files. Matching sessions to a git repo arrives in Phase 1.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


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
