# 🧾 agent-receipts

**Show your work, agent.** A local-first CLI + GitHub Action that turns Claude Code and Codex CLI session logs into a reviewable *receipt* for every agent-authored pull request.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Version](https://img.shields.io/badge/version-0.1.0-2B8A3E)
[![CI](https://github.com/AagamS06/agent-receipts/actions/workflows/ci.yml/badge.svg)](https://github.com/AagamS06/agent-receipts/actions/workflows/ci.yml)
![Claude skill](https://img.shields.io/badge/Claude-skill-D97757)
![Local-first](https://img.shields.io/badge/data-stays%20local-2B8A3E)

---

## The problem

Coding agents now write code faster than humans can review it. When an agent opens a PR, the reviewer sees the final diff — but not **what the agent ran, whether tests ran on the final code, or whether it did something risky along the way**. That evidence already exists in local JSONL session logs; nobody turns it into something a reviewer can read in a minute.

agent-receipts reads those logs and answers four questions per PR:

1. **Was it verified?** `VERIFIED` · `STALE` (tests ran before the last edit) · `FAILED` · `UNVERIFIED`
2. **Did anything risky happen?** `rm -rf`, force-push, `.env` reads, `curl | sh`, DB drops, CI edits…
3. **What did it assume?** Agent-stated assumptions, pulled out of the transcript.
4. **What did it use and cost?** Tools, MCP servers and tokens across Claude Code and Codex.

### Who it helps

Solo devs and small teams who let agents open PRs, reviewers who want a consistent evidence bar, and OSS maintainers receiving agent-generated contributions.

### Where the idea came from

Built from a gap analysis of YC **Fall 2026** and **Summer 2026** companies. The same pain points showed up again and again in their public descriptions: the verification bottleneck (Workers IO, Simulithic, GitCafe), silent destructive actions (Agent FM, Decawork, machine0, OneCLI), no cross-harness view of tool usage (Codag, Executor), babysitting many agents (Herdr, Hoplite) and debugging AI-written code (HyperProbe). This is an independent student project and is not affiliated with or endorsed by any of them. Full analysis: [PRD.md](PRD.md).

## Features

| | v0.1.0 | Later |
|---|---|---|
| Claude Code + Codex CLI adapters (rollout files and `codex exec --json`) → one event schema | ✅ | Gemini CLI, Aider, Cursor |
| Verification verdict: `VERIFIED` / `STALE` / `FAILED` / `UNVERIFIED`, with the reason | ✅ | hunk → step attribution |
| 19 deterministic risk rules (FS, GIT, SEC, NET, PERM, DB, CI) + `.agent-receipts.toml` overrides and project rules | ✅ | more rules, org policy packs |
| Secret redaction (key patterns, entropy, home paths, truncation) before any output | ✅ | |
| Markdown (PR comment) and JSON receipts, `scan` table of recent sessions | ✅ | HTML timeline |
| Stated-assumption extraction, tool / MCP / token summary | ✅ | |
| Claude skill (`skills/agent-receipts/`) | ✅ | |
| GitHub Action sticky PR comment | | Phase 3 |

## Tech stack

Python 3.11+ · Typer · Pydantic v2 · Rich · Jinja2 · pytest · ruff · mypy · GitHub Actions. No backend, no database, no LLM calls. Reasons in [Architecture.md](Architecture.md#4-tech-stack-and-why).

## Getting started

```bash
pip install "git+https://github.com/AagamS06/agent-receipts.git@v0.1.0"   # or: pipx install ...

agent-receipts scan --since 24h                 # recent Claude Code / Codex sessions + verdicts
agent-receipts render                           # receipt for the latest session in this repo
agent-receipts render ~/.claude/projects/<dir>/<session>.jsonl -o receipt.md
agent-receipts render --all --since 2h -f json  # combine every session in the window
agent-receipts rules                            # list the built-in rules
```

Try it without any logs of your own, using the example sessions in the repo:

```bash
git clone https://github.com/AagamS06/agent-receipts.git && cd agent-receipts
pip install -e ".[dev]"
agent-receipts render examples/claude-code-session.jsonl
agent-receipts render examples/codex-rollout.jsonl
pytest
```

Real output for `examples/claude-code-session.jsonl`:

```markdown
### 🧾 Agent receipt — ✔ VERIFIED
`pytest -q && ruff check .` ran at step 14 after the final edit (step 12) and passed.

| Files | Commands | Findings | Tokens |
|---|---|---|---|
| 2 | 3 | 1 high | 12k |

> [!WARNING]
> **GIT002 · high** — Force push: `git push --force origin fix/rate-limit` (step 16)
```

Exit codes (for scripts and CI): `0` clean · `1` checks failed, or a finding at/above `fail_on` (default `high`) · `2` bad input · `3` no session found.

Optional: copy `.agent-receipts.example.toml` to `.agent-receipts.toml` in your project to add your own test commands, change rule severities or add project rules.

## Use it with Claude (skill)

1. Download **`agent-receipts-skill.zip`** from the [latest release](https://github.com/AagamS06/agent-receipts/releases/latest) (or copy `skills/agent-receipts/`).
2. Unzip it and add the `agent-receipts` folder as a skill in Claude.
3. Ask: *"Make a receipt for the agent session that wrote this branch."*

## Project structure

```
src/agent_receipts/   cli · models · discovery · classify · verify · receipt · redact · policy
  adapters/           claude_code · codex
  risk/               rule engine + built-in rules
  render/             Markdown + JSON
tests/                fixtures (synthetic sessions) + unit tests
examples/             sample sessions to try the CLI on
skills/agent-receipts/SKILL.md
```
Full tree in [Architecture.md](Architecture.md#3-folder-and-file-structure).

## Roadmap

Done: Phase 0 Setup, Phase 1 Ingest + verification, most of Phase 2 (risk, redaction, Markdown/JSON). Next: JSON Schema export, `mypy --strict`, then Phase 3 GitHub Action + hardening → Phase 4 Launch. Checklists and exit criteria in [Phases.md](Phases.md).

## Docs

| Doc | What's inside |
|---|---|
| [PRD.md](PRD.md) | Problem, gaps (with source companies), users, stories, features, metrics |
| [Architecture.md](Architecture.md) | Flow diagram, modules, file tree, stack, data model, log formats |
| [Rules.md](Rules.md) | Conventions, approved libs, AI-contributor boundaries, testing, security |
| [Phases.md](Phases.md) | Phase-by-phase tasks and exit criteria |
| [Design.md](Design.md) | Palette, themes, typography, components, accessibility |
| [Memory.md](Memory.md) | Short handoff: decisions, status, next steps |
| [skills/agent-receipts/SKILL.md](skills/agent-receipts/SKILL.md) | Claude skill |

## Contributing

Issues and PRs welcome — including ones written by agents, as long as they follow [Rules.md](Rules.md) (and ideally come with their own receipt). Please don't include real session logs or secrets in issues; use anonymised snippets.

## Licence

[MIT](LICENSE) © 2026 Aagam Shah
