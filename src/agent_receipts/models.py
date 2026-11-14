"""Data model for receipts (schema version 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Harness = Literal["claude_code", "codex"]
EventKind = Literal[
    "user_msg",
    "agent_msg",
    "command",
    "file_edit",
    "file_read",
    "mcp_call",
    "web",
    "plan",
    "usage",
    "unknown",
]
Severity = Literal["info", "low", "medium", "high", "critical"]
Status = Literal["VERIFIED", "STALE", "FAILED", "UNVERIFIED"]

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class Event(BaseModel):
    idx: int
    ts: datetime | None = None
    harness: Harness
    kind: EventKind
    command: str | None = None
    exit_code: int | None = None
    paths: list[str] = Field(default_factory=list)
    tool: str | None = None
    text: str | None = None
    output_excerpt: str | None = None
    tokens: dict[str, int] = Field(default_factory=dict)
    model: str | None = None
    labels: set[str] = Field(default_factory=set)
    check_commands: list[str] = Field(default_factory=list)


class Session(BaseModel):
    harness: Harness
    path: str
    session_id: str | None = None
    cwd: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    events: list[Event] = Field(default_factory=list)
    unknown_records: int = 0


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    event_idx: int
    title: str
    evidence: str


class Verdict(BaseModel):
    status: Status
    last_edit_idx: int | None = None
    last_check_idx: int | None = None
    checks: list[str] = Field(default_factory=list)
    reason: str


class SessionRef(BaseModel):
    harness: Harness
    session_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    models: list[str] = Field(default_factory=list)
    events: int = 0
    unknown_records: int = 0


class UsageSummary(BaseModel):
    tokens_by_model: dict[str, dict[str, int]] = Field(default_factory=dict)
    total_tokens: int = 0
    tool_counts: dict[str, int] = Field(default_factory=dict)
    mcp_servers: list[str] = Field(default_factory=list)
    commands_run: int = 0


class Receipt(BaseModel):
    schema_version: str = "1"
    repo: str | None = None
    branch: str | None = None
    head_sha: str | None = None
    sessions: list[SessionRef]
    files_changed: list[str]
    verdict: Verdict
    findings: list[Finding]
    usage: UsageSummary
    assumptions: list[str]
    generated_at: datetime
    generator: str
