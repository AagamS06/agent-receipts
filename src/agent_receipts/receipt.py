"""Build a :class:`Receipt` from one or more parsed sessions."""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from agent_receipts import __version__
from agent_receipts.classify import classify
from agent_receipts.models import Event, Receipt, Session, SessionRef, UsageSummary
from agent_receipts.policy import Policy
from agent_receipts.risk import scan
from agent_receipts.verify import verdict

ASSUME = re.compile(
    r"(?i)\b(i assume|i'm assuming|assuming|i couldn't verify|not sure|todo\b|left as is)"
)


def _git(cwd: str | None, *args: str) -> str | None:
    if not cwd or not Path(cwd).is_dir():
        return None
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (out.stdout.strip() or None) if out.returncode == 0 else None


def _rel(path: str, root: str | None) -> str:
    if root and path.startswith(root.rstrip("/") + "/"):
        return path[len(root.rstrip("/")) + 1 :]
    return path


def usage(events: list[Event]) -> UsageSummary:
    u = UsageSummary()
    tools: Counter[str] = Counter()
    for ev in events:
        if ev.kind == "usage":
            model = ev.model or "unknown"
            bucket = u.tokens_by_model.setdefault(model, {})
            for k, v in ev.tokens.items():
                bucket[k] = bucket.get(k, 0) + v
                if k in {"input", "output"}:
                    u.total_tokens += v
        elif ev.tool:
            tools[ev.tool.split("/")[0] if ev.tool.startswith("mcp:") else ev.tool] += 1
        if ev.kind == "command":
            u.commands_run += 1
        if ev.kind == "mcp_call" and ev.tool:
            server = ev.tool.removeprefix("mcp:").split("/")[0]
            if server not in u.mcp_servers:
                u.mcp_servers.append(server)
    u.tool_counts = dict(tools.most_common())
    return u


def build(sessions: list[Session], policy: Policy, repo_dir: str | None = None) -> Receipt:
    events: list[Event] = []
    for s in sorted(sessions, key=lambda s: s.started_at or datetime.min.replace(tzinfo=UTC)):
        for ev in s.events:
            events.append(ev.model_copy(update={"idx": len(events)}))
    classify(events, policy)
    cwd = repo_dir or next((s.cwd for s in sessions if s.cwd), None)
    root = _git(cwd, "rev-parse", "--show-toplevel") or cwd
    files: list[str] = []
    for ev in events:
        if ev.kind == "file_edit":
            for p in ev.paths:
                rel = _rel(p, root)
                if rel not in files:
                    files.append(rel)
    assumptions = []
    for ev in events:
        if ev.kind == "agent_msg" and ev.text:
            for sentence in re.split(r"(?<=[.!?])\s+", ev.text):
                if ASSUME.search(sentence) and len(assumptions) < 10:
                    assumptions.append(sentence.strip()[:240])
    refs = [
        SessionRef(
            harness=s.harness,
            session_id=s.session_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            events=len(s.events),
            unknown_records=s.unknown_records,
            models=sorted({e.model for e in s.events if e.model}),
        )
        for s in sessions
    ]
    return Receipt(
        repo=Path(root).name if root else None,
        branch=_git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        head_sha=_git(root, "rev-parse", "HEAD"),
        sessions=refs,
        files_changed=files,
        verdict=verdict(events),
        findings=scan(events, policy),
        usage=usage(events),
        assumptions=assumptions,
        generated_at=datetime.now(UTC).replace(microsecond=0),
        generator=f"agent-receipts/{__version__}",
    )
