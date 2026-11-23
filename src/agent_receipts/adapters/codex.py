"""Codex CLI logs: rollout files (``session_meta`` / ``response_item`` / ``event_msg``)
and the ``codex exec --json`` stream (``thread.*`` / ``item.*`` / ``turn.*``)."""

from __future__ import annotations

import json
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_receipts.models import Event, Session

PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cmd(value: Any) -> str:
    """Codex stores commands as argv lists, often ``["bash", "-lc", "<script>"]``."""
    if isinstance(value, list):
        parts = [str(p) for p in value]
        if (
            len(parts) >= 3
            and parts[0].endswith(("bash", "sh", "zsh"))
            and parts[1] in {"-lc", "-c"}
        ):
            return parts[2]
        return shlex.join(parts)
    return str(value or "")


def _loads(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


class _Builder:
    def __init__(self, path: Path) -> None:
        self.s = Session(harness="codex", path=str(path))
        self.calls: dict[str, Event] = {}
        self.model: str | None = None

    def add(self, ts: datetime | None, **kw: Any) -> Event:
        ev = Event(idx=len(self.s.events), ts=ts, harness="codex", **kw)
        self.s.events.append(ev)
        return ev

    # ---- rollout format -------------------------------------------------
    def rollout(self, rec: dict[str, Any], ts: datetime | None) -> None:
        kind, p = rec.get("type"), rec.get("payload") or {}
        if kind == "session_meta":
            self.s.session_id = self.s.session_id or p.get("id")
            self.s.cwd = self.s.cwd or p.get("cwd")
        elif kind == "turn_context":
            self.s.cwd = self.s.cwd or p.get("cwd")
        elif kind == "response_item":
            t = p.get("type")
            if t == "message":
                text = "\n".join(
                    str(c.get("text", "")) for c in p.get("content") or [] if isinstance(c, dict)
                )
                if p.get("role") == "assistant":
                    self.add(ts, kind="agent_msg", text=text)
                elif p.get("role") == "user" and not text.lstrip().startswith("<"):
                    self.add(ts, kind="user_msg", text=text)
            elif t in {"function_call", "local_shell_call"}:
                args = _loads(p.get("arguments")) if t == "function_call" else p.get("action") or {}
                name = p.get("name", "shell")
                if isinstance(args, dict) and "command" in args:
                    ev = self.add(ts, kind="command", tool=name, command=_cmd(args["command"]))
                elif isinstance(name, str) and "__" in name:
                    ev = self.add(ts, kind="mcp_call", tool="mcp:" + name.replace("__", "/", 1))
                else:
                    ev = self.add(ts, kind="unknown", tool=str(name))
                if p.get("call_id"):
                    self.calls[str(p["call_id"])] = ev
            elif t == "custom_tool_call" and p.get("name") == "apply_patch":
                files = PATCH_FILE.findall(str(p.get("input", "")))
                ev = self.add(
                    ts, kind="file_edit", tool="apply_patch", paths=[f.strip() for f in files]
                )
                if p.get("call_id"):
                    self.calls[str(p["call_id"])] = ev
            elif t in {"function_call_output", "custom_tool_call_output"}:
                done = self.calls.pop(str(p.get("call_id")), None)
                out = _loads(p.get("output"))
                if done is not None:
                    ev = done
                    if isinstance(out, dict):
                        meta = out.get("metadata") or {}
                        if ev.kind == "command" and isinstance(meta.get("exit_code"), int):
                            ev.exit_code = meta["exit_code"]
                        ev.output_excerpt = str(out.get("output", ""))
                    else:
                        ev.output_excerpt = str(out)
                        m = re.search(r"[Ee]xit code: (-?\d+)", str(out))
                        if ev.kind == "command" and m:
                            ev.exit_code = int(m.group(1))
            elif t == "web_search_call":
                self.add(ts, kind="web", tool="web_search")
            elif t == "reasoning":
                pass
            else:
                self.s.unknown_records += 1
        elif kind == "event_msg":
            t = p.get("type")
            if t == "token_count":
                info = p.get("info") or {}
                last = info.get("last_token_usage") or {}
                if last:
                    self.add(
                        ts,
                        kind="usage",
                        tokens={
                            "input": int(last.get("input_tokens", 0) or 0),
                            "output": int(last.get("output_tokens", 0) or 0),
                            "cached": int(last.get("cached_input_tokens", 0) or 0),
                            "reasoning": int(last.get("reasoning_output_tokens", 0) or 0),
                        },
                        model=self.model,
                    )
            elif t == "exec_command_end":
                ended = self.calls.get(str(p.get("call_id")))
                if ended is not None and isinstance(p.get("exit_code"), int):
                    ended.exit_code = p["exit_code"]
        else:
            self.s.unknown_records += 1

    # ---- exec --json stream -------------------------------------------
    def stream(self, rec: dict[str, Any], ts: datetime | None) -> None:
        t = str(rec.get("type", ""))
        if t == "thread.started":
            self.s.session_id = self.s.session_id or rec.get("thread_id")
            return
        if t == "turn.completed":
            u = rec.get("usage") or {}
            self.add(
                ts,
                kind="usage",
                tokens={
                    "input": int(u.get("input_tokens", 0) or 0),
                    "output": int(u.get("output_tokens", 0) or 0),
                    "cached": int(u.get("cached_input_tokens", 0) or 0),
                },
            )
            return
        if t != "item.completed":
            if not t.startswith(("item.", "turn.", "thread.")):
                self.s.unknown_records += 1
            return
        item = rec.get("item") or {}
        it = item.get("type") or item.get("item_type")
        if it in {"agent_message", "assistant_message"}:
            self.add(ts, kind="agent_msg", text=str(item.get("text", "")))
        elif it == "command_execution":
            code = item.get("exit_code")
            self.add(
                ts,
                kind="command",
                tool="shell",
                command=_cmd(item.get("command")),
                exit_code=code if isinstance(code, int) else None,
                output_excerpt=str(item.get("aggregated_output", "")) or None,
            )
        elif it == "file_change":
            paths = [str(c.get("path")) for c in item.get("changes") or [] if isinstance(c, dict)]
            self.add(ts, kind="file_edit", tool="file_change", paths=paths)
        elif it == "mcp_tool_call":
            self.add(ts, kind="mcp_call", tool=f"mcp:{item.get('server')}/{item.get('tool')}")
        elif it == "web_search":
            self.add(ts, kind="web", tool="web_search", text=str(item.get("query", "")))
        elif it in {"plan_update", "todo_list"}:
            self.add(ts, kind="plan", tool=str(it))
        elif it == "reasoning":
            pass
        else:
            self.s.unknown_records += 1


def parse(path: Path) -> Session:
    b = _Builder(path)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                b.s.unknown_records += 1
                continue
            if not isinstance(rec, dict):
                b.s.unknown_records += 1
                continue
            ts = _ts(rec.get("timestamp"))
            if ts:
                b.s.started_at = b.s.started_at or ts
                b.s.ended_at = ts
            if rec.get("type") == "turn_context":
                b.model = (rec.get("payload") or {}).get("model") or b.model
            if "payload" in rec:
                b.rollout(rec, ts)
            else:
                b.stream(rec, ts)
    return b.s
