"""Make receipts safe to paste into a public PR: mask secrets, home paths and long output."""

from __future__ import annotations

import math
import re
from pathlib import Path

from agent_receipts.models import Receipt

PATTERNS = [
    r"sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"AIza[0-9A-Za-z_-]{30,}",
    r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    r"(?i)((?:api[_-]?key|token|secret|password|passwd)\s*[=:]\s*)['\"]?[^\s'\"]{6,}",
]
_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{32,}")


def _entropy(s: str) -> float:
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


class Redactor:
    def __init__(self, extra: list[str] | None = None, max_chars: int = 400) -> None:
        self.patterns = [re.compile(p) for p in PATTERNS + list(extra or [])]
        self.max_chars = max_chars
        self.home = str(Path.home())

    def text(self, value: str | None, limit: bool = True) -> str | None:
        if value is None:
            return None
        out = value
        for pat in self.patterns:
            out = pat.sub(
                lambda m: (m.group(1) if m.re.groups and m.group(1) else "") + "[REDACTED]", out
            )
        out = _TOKEN.sub(lambda m: "[REDACTED]" if _entropy(m.group(0)) > 4.2 else m.group(0), out)
        if self.home and self.home != "/":
            out = out.replace(self.home, "~")
        out = re.sub(r"/(home|Users)/[^/\s]+", "~", out)
        if limit and len(out) > self.max_chars:
            out = out[: self.max_chars] + f"… [+{len(out) - self.max_chars} chars]"
        return out

    def receipt(self, r: Receipt) -> Receipt:
        r = r.model_copy(deep=True)
        for f in r.findings:
            f.evidence = self.text(f.evidence) or ""
        r.verdict.reason = self.text(r.verdict.reason, limit=False) or ""
        r.verdict.checks = [self.text(c) or "" for c in r.verdict.checks]
        r.files_changed = [self.text(p, limit=False) or "" for p in r.files_changed]
        r.assumptions = [self.text(a) or "" for a in r.assumptions]
        if r.repo:
            r.repo = self.text(r.repo, limit=False)
        return r
