"""Adapters turn raw session logs into normalized :class:`Session` objects."""

from __future__ import annotations

import json
from pathlib import Path

from agent_receipts.adapters import claude_code, codex
from agent_receipts.models import Session


def detect(path: Path) -> str:
    """Guess the harness from the file name, then from the first JSON records."""
    if path.name.startswith("rollout-") or ".codex" in path.parts:
        return "codex"
    if ".claude" in path.parts:
        return "claude_code"
    with path.open(encoding="utf-8", errors="replace") as fh:
        for _, line in zip(range(20), fh, strict=False):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            if "payload" in rec or str(rec.get("type", "")).startswith(
                ("thread.", "item.", "turn.")
            ):
                return "codex"
            if rec.get("type") in {"session_meta", "response_item", "event_msg"}:
                return "codex"
            if "message" in rec and rec.get("type") in {"user", "assistant"}:
                return "claude_code"
    raise ValueError(f"cannot tell which agent wrote {path.name}")


def load(path: Path, harness: str | None = None) -> Session:
    harness = harness or detect(path)
    if harness == "claude_code":
        return claude_code.parse(path)
    if harness == "codex":
        return codex.parse(path)
    raise ValueError(f"unknown harness {harness!r}")
