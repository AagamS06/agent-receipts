# Memory — agent-receipts (handoff)

**One-liner:** CLI + GitHub Action that turns Claude Code / Codex session logs into a reviewable receipt per PR: verification verdict, risky actions, tools/MCP used, tokens.
Build status: active

**Owner:** Aagam Shah (@AagamS06) · **Started:** 2026-10-22 · **Lang:** Python 3.11+

## Why it exists
Gaps observed in YC F26/S26 listings: verification bottleneck (Workers IO, Simulithic, GitCafe), silent risky actions (Agent FM, Decawork, machine0, OneCLI), no cross-harness tool/spend view (Codag, Executor), agent babysitting (Herdr, Agent FM, Hoplite), debugging AI-written code (HyperProbe). Details: [PRD.md](PRD.md).

## Decisions (and why)
- Local-first, no backend → privacy; logs never leave the machine.
- Deterministic rules, no LLM in MVP → explainable, testable, free.
- Redact before render, always → receipts are safe for public PRs.
- Pydantic `Receipt` schema v1 is the contract → changes need human approval.
- Codex adapter accepts both `type` and legacy `item_type` → format drift.
- `subprocess` git calls, not GitPython → fewer deps.
- A session belongs to a repo if its cwd is inside it **or** it edited a file inside it (2026-11-23); relative edit paths resolve against the session cwd. `--touching`/`--changed-since` match exact resolved paths, never basenames, to avoid false matches.
- Receipts reach PRs two ways (open question 1 answered 2026-11-27): `publish` from the dev machine (logs stay local), or commit `.agent-receipts/receipt.json` and let the Action post it. The Action never sees raw logs.
- Sticky comment = newest comment starting with `<!-- agent-receipts -->` **written by the same login** (`gh api user`, or `github-actions[bot]` when that call fails under GITHUB_TOKEN), so a crafted comment by someone else can't be hijacked.
- A receipt JSON from a PR is untrusted: it is schema-validated, re-redacted and re-rendered; every log-derived string goes through `md_text` (one line, HTML escaped, mentions defused, URLs as code, punctuation escaped) or `md_code` (one-line code span, backticks → ').
- `--changed-since REF` = `git diff --name-only REF` + untracked files, so uncommitted agent work counts.
- JSON Schema is generated from the pydantic models (`mode="serialization"`) and committed; a test fails on drift. A pydantic upgrade can change the output wording: regenerate with `agent-receipts schema -o schema/receipt.v1.json` and review the diff.

## Status
- **Done (v0.1.0, 2026-11-14):** Phase 0 + Phase 1 (Claude Code + Codex adapters incl. `codex exec --json`, classify, verify, `scan`), most of Phase 2 (19 risk rules, policy file, redaction, Markdown/JSON receipts, assumptions, usage), `render` + `rules` commands, CI (ruff + pytest 3.11–3.13), Claude skill `skills/agent-receipts/SKILL.md`, release v0.1.0 with `agent-receipts-skill.zip`. 57 tests.
- **Learned from dogfooding a real Claude Code log:** heredoc bodies must not be scanned as commands; venv/absolute binary paths must be normalised (`/x/.venv/bin/pytest` → `pytest`); Claude Code writes many bookkeeping record types (attachment, queue-operation, …) that are skipped, not "unknown".
- **Done (v0.1.1, 2026-11-23):** `schema` command + `schema/receipt.v1.json` (draft 2020-12, fixtures validated against it); touched-files matching (`--touching`, `--changed-since`, "Edits here" in `scan`); `mypy --strict` clean and enforced in CI; 72 tests.
- **Done (v0.2.0, 2026-11-27):** `publish --pr N` (sticky comment through `gh api`, `--dry-run`, `--no-fail`, exit 4 on post failure); composite Action `action/action.yml` posting a committed receipt JSON (inputs receipt / pr / require-receipt / fail-on-findings; outputs verdict / posted); `render` and `publish` accept a saved `.json` receipt; Markdown injection hardening (`md_text` / `md_code` filters) + caps (100 files, 50 extra findings); CI smoke-tests `publish --dry-run`; 92 tests. The Action was tested with a simulated `gh`, not yet on a real PR.
- **Next:** tamper-evident footer (full receipt hash + verify command), large/corrupt-file fuzz tests, Dependabot + CodeQL, docs (troubleshooting, how verdicts work, rule catalogue); then more rules (25 target) and the Phase 4 HTML receipt.
- **Backlog:** see [Phases.md](Phases.md#backlog-post-launch).

## Needs Aagam
- Try the Action on a real PR in one of your repos (copy `examples/agent-receipts-workflow.yml`), and run `agent-receipts publish --pr N` once with your own `gh` login.
- Publishing to PyPI (Phase 4) needs your account.

## Open questions
1. ~~Best way to get receipts into CI~~ → both: `publish` locally, or a committed receipt + Action (2026-11-27). Later: CI-artifact input.
2. How to attribute edits when two agents worked on the same branch?
3. Should STALE be a warning or failure by default?

## Docs
[README](README.md) · [PRD](PRD.md) · [Architecture](Architecture.md) · [Rules](Rules.md) · [Phases](Phases.md) · [Design](Design.md) · [Skill](skills/agent-receipts/SKILL.md)
