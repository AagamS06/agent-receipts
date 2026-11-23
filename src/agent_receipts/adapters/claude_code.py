"""Claude Code session logs (``~/.claude/projects/<cwd>/<session>.jsonl``)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_receipts.models import Event, Session

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead"}
WEB_TOOLS = {"WebFetch", "WebSearch"}


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(b.get("text", ""))
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _dict(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a JSON object, else an empty dict (logs drift; never crash)."""
    return value if isinstance(value, dict) else {}


def _tool_event(block: dict[str, Any], base: dict[str, Any]) -> Event:
    name = str(block.get("name", "?"))
    inp = _dict(block.get("input"))
    if name == "Bash":
        return Event(**base, kind="command", tool=name, command=str(inp.get("command", "")))
    if name in EDIT_TOOLS:
        path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        return Event(**base, kind="file_edit", tool=name, paths=[str(path)] if path else [])
    if name in READ_TOOLS:
        path = inp.get("file_path") or inp.get("path")
        return Event(**base, kind="file_read", tool=name, paths=[str(path)] if path else [])
    if name in WEB_TOOLS:
        return Event(
            **base, kind="web", tool=name, text=str(inp.get("url") or inp.get("query") or "")
        )
    if name.startswith("mcp__"):
        parts = name.split("__")
        tool = f"mcp:{parts[1]}/{'__'.join(parts[2:])}" if len(parts) > 2 else name
        return Event(**base, kind="mcp_call", tool=tool)
    if name in {"TodoWrite", "ExitPlanMode"}:
        return Event(**base, kind="plan", tool=name)
    return Event(**base, kind="unknown", tool=name)


def parse(path: Path) -> Session:
    session = Session(harness="claude_code", path=str(path))
    pending: dict[str, Event] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                session.unknown_records += 1
                continue
            if not isinstance(rec, dict):
                session.unknown_records += 1
                continue
            ts = _ts(rec.get("timestamp"))
            if ts:
                session.started_at = session.started_at or ts
                session.ended_at = ts
            session.session_id = session.session_id or rec.get("sessionId")
            session.cwd = session.cwd or rec.get("cwd")
            kind = rec.get("type")
            msg = _dict(rec.get("message"))
            content = msg.get("content")
            if kind == "assistant":
                usage = _dict(msg.get("usage"))
                model = msg.get("model")
                if usage:
                    tokens = {
                        "input": int(usage.get("input_tokens", 0) or 0),
                        "output": int(usage.get("output_tokens", 0) or 0),
                        "cached": int(usage.get("cache_read_input_tokens", 0) or 0)
                        + int(usage.get("cache_creation_input_tokens", 0) or 0),
                    }
                    session.events.append(
                        Event(
                            idx=len(session.events),
                            ts=ts,
                            harness="claude_code",
                            kind="usage",
                            tokens=tokens,
                            model=model,
                        )
                    )
                blocks = content if isinstance(content, list) else []
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    base: dict[str, Any] = {
                        "idx": len(session.events),
                        "ts": ts,
                        "harness": "claude_code",
                    }
                    if block.get("type") == "text" and block.get("text"):
                        session.events.append(
                            Event(**base, kind="agent_msg", text=str(block["text"]))
                        )
                    elif block.get("type") == "tool_use":
                        ev = _tool_event(block, base)
                        session.events.append(ev)
                        if block.get("id"):
                            pending[str(block["id"])] = ev
            elif kind == "user":
                if isinstance(content, str):
                    session.events.append(
                        Event(
                            idx=len(session.events),
                            ts=ts,
                            harness="claude_code",
                            kind="user_msg",
                            text=content,
                        )
                    )
                    continue
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        use_id = str(block.get("tool_use_id"))
                        if use_id not in pending:
                            continue
                        ev = pending.pop(use_id)
                        out = _text(block.get("content"))
                        result = _dict(rec.get("toolUseResult"))
                        if not out and result:
                            out = str(result.get("stdout", "")) + str(result.get("stderr", ""))
                        ev.output_excerpt = out or None
                        if ev.kind == "command":
                            code = result.get("exitCode", result.get("exit_code"))
                            if isinstance(code, int):
                                ev.exit_code = code
                            else:
                                ev.exit_code = 1 if block.get("is_error") else 0
                    elif block.get("type") == "text" and block.get("text"):
                        session.events.append(
                            Event(
                                idx=len(session.events),
                                ts=ts,
                                harness="claude_code",
                                kind="user_msg",
                                text=str(block["text"]),
                            )
                        )
            # Other record types (summary, system, attachment, queue-operation, ...) are
            # Claude Code bookkeeping, not agent actions: skip them.
    return session
