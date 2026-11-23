"""Rule engine: built-in risky-action rules plus project rules from the policy file."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import cast

from agent_receipts.classify import segments, strip_heredocs
from agent_receipts.models import SEVERITY_ORDER, Event, Finding, Severity
from agent_receipts.policy import Policy


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    title: str
    command: str | None = None  # regex on each command segment
    path: str | None = None  # regex on edited file paths


RULES: list[Rule] = [
    Rule(
        "FS001",
        "high",
        "Recursive force delete",
        command=r"\brm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*|--recursive\s+--force|-r\s+-f|-f\s+-r)\b",
    ),
    Rule(
        "FS002",
        "medium",
        "Deleted or overwrote files with find -delete / shred",
        command=r"\bfind\b.*\s-delete\b|\bshred\b",
    ),
    Rule("GIT001", "medium", "Pushed to a remote", command=r"^git push\b(?!.*--dry-run)"),
    Rule(
        "GIT002",
        "high",
        "Force push",
        command=r"^git push\b.*(--force\b|--force-with-lease\b|\s-f\b|\s\+\S)",
    ),
    Rule(
        "GIT003",
        "high",
        "Hard reset or discarded local changes",
        command=r"^git (reset --hard|checkout -- \.|checkout \.|restore \.|clean -\w*f)",
    ),
    Rule(
        "GIT004",
        "medium",
        "Rewrote history",
        command=r"^git (rebase|commit --amend|filter-branch|filter-repo)\b",
    ),
    Rule("GIT005", "low", "Skipped git hooks", command=r"^git (commit|push)\b.*--no-verify\b"),
    Rule(
        "SEC001",
        "high",
        "Read or edited a secrets file",
        command=r"(^|\s)(cat|less|more|head|tail|vi|vim|nano|cp|scp)\s+\S*(\.env\b|\.pem\b|id_rsa|\.npmrc|\.pypirc|credentials)",
        path=r"(^|/)(\.env(\.[\w-]+)?|[^/]+\.pem|id_rsa[^/]*|\.npmrc|\.pypirc|credentials(\.json)?)$",
    ),
    Rule(
        "SEC002",
        "high",
        "Secret-looking token in a command",
        command=r"(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})",
    ),
    Rule(
        "SEC003",
        "medium",
        "Printed environment variables",
        command=r"^(env|printenv|set)\s*$|^export -p\b",
    ),
    Rule(
        "NET001",
        "high",
        "Piped a download straight into a shell",
        command=r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b",
    ),
    Rule(
        "NET002",
        "low",
        "Installed a package",
        command=r"^(pip3?|uv pip|python3? -m pip)\s+(-\S+\s+)*install\b|^(uv add|poetry add|npm (i|install|add)|pnpm (i|install|add)|yarn add|cargo add|go get)\b",
    ),
    Rule("PERM001", "high", "Ran a command with sudo", command=r"^sudo\b"),
    Rule(
        "PERM002",
        "medium",
        "World-writable permissions",
        command=r"\bchmod\s+(-R\s+)?(777|a\+w|o\+w)\b",
    ),
    Rule(
        "DB001",
        "critical",
        "Destructive SQL",
        command=r"(?i)\b(drop\s+(table|database|schema)|truncate\s+table)\b",
    ),
    Rule(
        "DB002",
        "medium",
        "Edited a database migration",
        path=r"(^|/)(migrations?|alembic/versions|db/migrate)/",
    ),
    Rule(
        "CI001",
        "medium",
        "Edited CI configuration",
        path=r"(^|/)(\.github/workflows/|\.gitlab-ci\.yml$|\.circleci/|Jenkinsfile$|azure-pipelines\.yml$)",
    ),
    Rule(
        "CI002",
        "low",
        "Edited dependency manifest",
        path=r"(^|/)(package\.json|pyproject\.toml|requirements[^/]*\.txt|Cargo\.toml|go\.mod)$",
    ),
    Rule(
        "CI003",
        "high",
        "Disabled or skipped tests",
        command=r"(--no-tests|-k\s+['\"]?not\b|\bit\.skip\b|SKIP_TESTS=1)",
    ),
]


def _evidence(ev: Event) -> str:
    if ev.command:
        return strip_heredocs(ev.command).split("\n")[0]
    return ", ".join(ev.paths)


def scan(events: list[Event], policy: Policy) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int]] = set()

    def add(
        rule_id: str, severity: str, title: str, ev: Event, evidence: str | None = None
    ) -> None:
        severity = policy.overrides.get(rule_id, severity)
        if (rule_id, ev.idx) in seen or severity not in SEVERITY_ORDER:
            return
        seen.add((rule_id, ev.idx))
        findings.append(
            Finding(
                rule_id=rule_id,
                severity=cast(Severity, severity),
                event_idx=ev.idx,
                title=title,
                evidence=evidence or _evidence(ev),
            )
        )

    compiled = [
        (r, re.compile(r.command) if r.command else None, re.compile(r.path) if r.path else None)
        for r in RULES
    ]
    for ev in events:
        if ev.kind == "command" and ev.command:
            segs = segments(ev.command)
            for rule, cre, _ in compiled:
                hit = next((s for s in segs if cre and cre.search(s)), None)
                if hit:
                    add(rule.id, rule.severity, rule.title, ev, hit)
            for cr in policy.rules:
                hit = next(
                    (s for s in segs if cr.command_regex and re.search(cr.command_regex, s)), None
                )
                if hit:
                    add(cr.id, cr.severity, cr.title, ev, hit)
        if ev.kind in {"file_edit", "file_read"}:
            for rule, _, pre in compiled:
                if pre and any(pre.search(p) for p in ev.paths):
                    if ev.kind == "file_read" and rule.id != "SEC001":
                        continue
                    add(rule.id, rule.severity, rule.title, ev)
            if ev.kind == "file_edit":
                for cr in policy.rules:
                    if cr.path_glob and any(
                        fnmatch.fnmatch(p.lstrip("./"), cr.path_glob)
                        or fnmatch.fnmatch(p, "*/" + cr.path_glob)
                        for p in ev.paths
                    ):
                        add(cr.id, cr.severity, cr.title, ev)
    forced = {f.event_idx for f in findings if f.rule_id == "GIT002"}
    findings = [f for f in findings if not (f.rule_id == "GIT001" and f.event_idx in forced)]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.event_idx))
    return findings


def fails(findings: list[Finding], fail_on: str) -> bool:
    if fail_on not in SEVERITY_ORDER:
        return False
    return any(SEVERITY_ORDER[f.severity] <= SEVERITY_ORDER[fail_on] for f in findings)
