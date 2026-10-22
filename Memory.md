# Memory — agent-receipts (handoff)

**One-liner:** CLI + GitHub Action that turns Claude Code / Codex session logs into a reviewable receipt per PR: verification verdict, risky actions, tools/MCP used, tokens.
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

## Status
- **Done:** repo + docs (PRD, Architecture, Rules, Phases, Design); Phase 0 scaffold (pyproject, package skeleton, `--version`, `scan` stub that lists Claude Code/Codex session files, 7 passing smoke tests, policy example).
- **In progress:** —
- **Next:** CI workflow (ruff + pytest); collect anonymised fixtures; Phase 1 `models.py` + Claude Code adapter.
- **Backlog:** see [Phases.md](Phases.md#backlog-post-launch).

## Open questions
1. Best way to get receipts into CI when logs live on the dev machine — artifact upload vs `publish --pr` from local? (leaning: both)
2. How to attribute edits when two agents worked on the same branch?
3. Should STALE be a warning or failure by default?

## Docs
[README](README.md) · [PRD](PRD.md) · [Architecture](Architecture.md) · [Rules](Rules.md) · [Phases](Phases.md) · [Design](Design.md)
