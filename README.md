# 🧾 agent-receipts

**Show your work, agent.** A local-first CLI + GitHub Action that turns Claude Code and Codex CLI session logs into a reviewable *receipt* for every agent-authored pull request.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Status](https://img.shields.io/badge/status-phase%200%20%E2%80%94%20scaffold-orange)
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

| | MVP | Later |
|---|---|---|
| Claude Code + Codex CLI adapters → one event schema | ✅ planned | Gemini CLI, Aider, Cursor |
| Verification verdict (tests after last edit?) | ✅ planned | hunk → step attribution |
| 25 deterministic risk rules + policy file | ✅ planned | org policy packs |
| Secret redaction before any output | ✅ planned | |
| Markdown / JSON / terminal receipts | ✅ planned | HTML timeline |
| `ls` digest of all recent agent sessions | ✅ planned | |
| GitHub Action sticky PR comment | | ✅ Phase 3 |

## Tech stack

Python 3.11+ · Typer · Pydantic v2 · Rich · Jinja2 · pytest · ruff · mypy · GitHub Actions. No backend, no database, no LLM calls. Reasons in [Architecture.md](Architecture.md#4-tech-stack-and-why).

## Getting started

```bash
git clone https://github.com/AagamS06/agent-receipts.git
cd agent-receipts
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

agent-receipts --version
agent-receipts scan --since 24h      # Phase 0: stub that lists session files it can see
pytest
```

Optional: copy `.agent-receipts.example.toml` to `.agent-receipts.toml` in your project to define your own test commands and risk rules.

## Project structure

```
src/agent_receipts/   cli · models · discovery · classify · verify · usage · redact · policy
  adapters/           claude_code · codex
  risk/               engine · rules
  render/             markdown · json_out · terminal
tests/                fixtures + unit tests
action/               GitHub Action (Phase 3)
```
Full tree in [Architecture.md](Architecture.md#3-folder-and-file-structure).

## Roadmap

Phase 0 Setup → Phase 1 Ingest + verification → Phase 2 Risk, redaction, rendering → Phase 3 GitHub Action + hardening → Phase 4 Launch. Checklists and exit criteria in [Phases.md](Phases.md).

## Docs

| Doc | What's inside |
|---|---|
| [PRD.md](PRD.md) | Problem, gaps (with source companies), users, stories, features, metrics |
| [Architecture.md](Architecture.md) | Flow diagram, modules, file tree, stack, data model, log formats |
| [Rules.md](Rules.md) | Conventions, approved libs, AI-contributor boundaries, testing, security |
| [Phases.md](Phases.md) | Phase-by-phase tasks and exit criteria |
| [Design.md](Design.md) | Palette, themes, typography, components, accessibility |
| [Memory.md](Memory.md) | Short handoff: decisions, status, next steps |

## Contributing

Issues and PRs welcome — including ones written by agents, as long as they follow [Rules.md](Rules.md) (and ideally come with their own receipt). Please don't include real session logs or secrets in issues; use anonymised snippets.

## Licence

[MIT](LICENSE) © 2026 Aagam Shah
