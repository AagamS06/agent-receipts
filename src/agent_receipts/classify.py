"""Label commands as test / lint / build / git / install so verify and risk can use them."""

from __future__ import annotations

import re

from agent_receipts.models import Event
from agent_receipts.policy import Policy

_PREFIX = re.compile(r"^\s*(?:cd\s+\S+\s*&&\s*|(?:[A-Z_][A-Z0-9_]*=\S*\s+)+|timeout\s+\d+\s+)*")
_SPLIT = re.compile(r"\s*(?:&&|\|\||;)\s*")
_INSTALL = re.compile(
    r"^(pip3?|uv pip|uv add|poetry add|npm (i|install|add)|pnpm (i|install|add)|"
    r"yarn add|cargo add|go get|brew install|apt(-get)? install)\b"
)


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def strip_heredocs(command: str) -> str:
    """Drop here-document bodies: they are file contents, not commands."""
    lines = command.split("\n")
    out: list[str] = []
    end: str | None = None
    for line in lines:
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = _HEREDOC.search(line)
        if m:
            end = m.group(2)
    return "\n".join(out)


def segments(command: str) -> list[str]:
    """Split ``a && b; c`` into single commands (heredoc bodies and env/cd prefixes removed)."""
    parts = _SPLIT.split(strip_heredocs(command).replace("\n", " ; "))
    out = []
    for part in parts:
        seg = _PREFIX.sub("", part).strip()
        if not seg:
            continue
        exe, _, rest = seg.partition(" ")
        if "/" in exe and not exe.endswith("/"):
            # /tmp/venv/bin/pytest, ./node_modules/.bin/jest, .venv/bin/python -> bare name
            seg = (exe.rsplit("/", 1)[1] + " " + rest).strip()
        out.append(seg)
    return out


def classify(events: list[Event], policy: Policy) -> None:
    pats = {
        "test": [re.compile(p) for p in policy.tests],
        "lint": [re.compile(p) for p in policy.lint],
        "build": [re.compile(p) for p in policy.build],
    }
    for ev in events:
        if ev.kind != "command" or not ev.command:
            continue
        for seg in segments(ev.command):
            for label, regexes in pats.items():
                if any(r.search(seg) for r in regexes):
                    ev.labels.add(label)
                    if label in {"test", "lint"}:
                        ev.check_commands.append(seg)
            if seg.startswith("git "):
                ev.labels.add("git")
            if _INSTALL.search(seg):
                ev.labels.add("install")
        if ev.labels & {"test", "lint"}:
            ev.labels.add("check")
