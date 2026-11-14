"""Load ``.agent-receipts.toml`` (see ``.agent-receipts.example.toml``)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TESTS = [
    r"^(python3?(\.\d+)? -m )?pytest\b",
    r"^(npm|pnpm|yarn|bun)( run)? test\b",
    r"^cargo test\b",
    r"^go test\b",
    r"^make (test|check)\b",
    r"^(uv run |poetry run )?pytest\b",
    r"^tox\b",
    r"^nox\b",
    r"^jest\b",
    r"^vitest\b",
    r"^python3?(\.\d+)? -m unittest\b",
    r"^mvn( -\S+)* test\b",
    r"^gradle(w)? test\b",
    r"^\./gradlew test\b",
    r"^dotnet test\b",
    r"^rspec\b",
    r"^bundle exec rspec\b",
]
DEFAULT_LINT = [
    r"^(uv run )?ruff (check|format --check)\b",
    r"^eslint\b",
    r"^(npx )?tsc\b",
    r"^mypy\b",
    r"^(npm|pnpm|yarn)( run)? (lint|typecheck)\b",
    r"^cargo (clippy|check)\b",
    r"^go vet\b",
    r"^golangci-lint\b",
    r"^flake8\b",
    r"^pylint\b",
    r"^black --check\b",
    r"^prettier --check\b",
]
DEFAULT_BUILD = [r"^(npm|pnpm|yarn)( run)? build\b", r"^cargo build\b", r"^go build\b", r"^make\b"]


@dataclass
class CustomRule:
    id: str
    severity: str
    title: str
    path_glob: str | None = None
    command_regex: str | None = None


@dataclass
class Policy:
    tests: list[str] = field(default_factory=lambda: list(DEFAULT_TESTS))
    lint: list[str] = field(default_factory=lambda: list(DEFAULT_LINT))
    build: list[str] = field(default_factory=lambda: list(DEFAULT_BUILD))
    stale_is_failure: bool = False
    fail_on: str = "high"
    overrides: dict[str, str] = field(default_factory=dict)
    rules: list[CustomRule] = field(default_factory=list)
    max_output_chars: int = 400
    extra_patterns: list[str] = field(default_factory=list)


def load_policy(path: Path | None) -> Policy:
    policy = Policy()
    if path is None or not path.is_file():
        return policy
    data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    ver = data.get("verification", {})
    # Project patterns are added to the defaults, never silently replace them.
    policy.tests += [str(p) for p in ver.get("tests", []) if str(p) not in policy.tests]
    policy.lint += [str(p) for p in ver.get("lint", []) if str(p) not in policy.lint]
    policy.stale_is_failure = bool(ver.get("stale_is_failure", False))
    risk = data.get("risk", {})
    policy.fail_on = str(risk.get("fail_on", policy.fail_on))
    policy.overrides = {str(k): str(v) for k, v in risk.get("overrides", {}).items()}
    for r in risk.get("rules", []):
        policy.rules.append(
            CustomRule(
                id=str(r["id"]),
                severity=str(r.get("severity", "medium")),
                title=str(r.get("title", r["id"])),
                path_glob=r.get("path_glob"),
                command_regex=r.get("command_regex"),
            )
        )
    red = data.get("redact", {})
    policy.max_output_chars = int(red.get("max_output_chars", policy.max_output_chars))
    policy.extra_patterns = [str(p) for p in red.get("extra_patterns", [])]
    return policy
