# PRD — agent-receipts

> A local-first CLI + GitHub Action that turns coding-agent session logs (Claude Code, Codex CLI) into a reviewable **receipt** for every agent-authored pull request: what the agent ran, what it changed, whether tests ran *after* the last edit, which risky actions it took, and what it cost.

Status: Draft v0.1 · Owner: Aagam Shah (@AagamS06) · Last updated: 2026-10-22

---

## 1. Problem statement

Teams now run several coding agents in parallel (Claude Code, Codex CLI, cloud "software factories"). Writing code is no longer the bottleneck — **trusting and reviewing** it is. When an agent opens a PR, the reviewer sees only the final diff. They cannot see:

- which commands the agent actually ran, and whether tests were run on the *final* version of the code or only on an earlier one;
- whether the agent did something risky along the way (`rm -rf`, `git push --force`, reading `.env`, dropping a table, `curl | sh`, installing an unknown package);
- what assumptions it made, which tools/MCP servers it called, and how many tokens it burned.

That evidence already exists — it is sitting in local JSONL session logs — but nobody turns it into something a reviewer can read in 60 seconds.

## 2. Gaps this addresses (observed in YC Fall 2026 and Summer 2026 companies)

Every gap below is taken from the company's own YC listing / launch post (researched 2026-10-22). agent-receipts does **not** compete with these products; it is a small open-source layer that fills the space between them.

| # | Gap / pain point | Where it was observed | How agent-receipts helps |
|---|---|---|---|
| G1 | **Verification is the bottleneck** — agents write code faster than teams can review or verify it | Workers IO (F26): "Coding agents generate code faster than teams can review it"; Simulithic (F26): "verification is now the bottleneck"; GitCafe (S26): teams struggle to "understand changes, review them safely" | A receipt attached to each PR with a *verification verdict*: were tests/linters run after the final edit, and did they pass? |
| G2 | **Silent risky or destructive actions and bad assumptions** | Agent FM (S26): agents "make bad assumptions, or take destructive actions"; Decawork (S26): cites a Replit agent deleting a live DB; machine0 (S26): credential exposure via prompt injection; OneCLI (S26): agent tools lack secret-handling basics | Rule-based risk scanner flags destructive commands, secret-file reads, force pushes, network installs, and permission escalations, with the exact step that triggered each flag |
| G3 | **No consistent cross-harness view of tool / MCP usage and spend** | Codag (S26): companies lack a consistent view of which tools and MCP servers agents use "across harnesses like Claude Code and Codex"; Executor (S26): per-agent auth sprawl, weak permissions | One normalized event schema across Claude Code and Codex; per-receipt tool/MCP inventory and token totals |
| G4 | **Babysitting many agents** — hard to know which finished, which is blocked, what each did | Herdr (F26): track "which agent is blocked, which has finished"; Agent FM (S26): "Babysitting agents is exhausting"; Hoplite (S26): many local agents, worktree chaos | `agent-receipts ls` gives a one-screen digest of recent sessions per repo/worktree: outcome, files touched, risk count, verification verdict |
| G5 | **Debugging AI-written code lacks context** | HyperProbe (S26): logs/traces "weren't built for debugging AI-written code"; agents "guess root causes" | The receipt preserves the agent's stated assumptions and command history next to the diff, so a later incident can be traced back to the session that produced the code |

## 3. Target users

- **Primary — solo devs and small teams (2–30 engineers)** who let Claude Code / Codex open PRs and review them on GitHub.
- **Secondary — tech leads / reviewers** who want a consistent "evidence bar" before merging agent PRs.
- **Tertiary — students and OSS maintainers** receiving agent-generated contributions who want transparency without buying an enterprise platform.

Not targeted: enterprises needing real-time enforcement (that is Decawork/OneCLI/Executor territory).

## 4. User stories

1. As a **reviewer**, I want a PR comment summarising the agent session that produced this diff, so I can decide what to scrutinise in under a minute.
2. As a **reviewer**, I want to know whether tests were run *after the final file edit* and their result, so I don't merge code that was only tested in an earlier state.
3. As a **developer**, I want `agent-receipts scan` to flag risky steps in my last session before I push, so I catch a stray `rm -rf` or `.env` read myself.
4. As a **developer running 4+ agents**, I want `agent-receipts ls` to show each recent session's status and verdict, so I stop tab-switching.
5. As a **tech lead**, I want a repo-level policy file (`.agent-receipts.toml`) defining which commands count as "tests" and which actions are "high risk", so the bar is consistent.
6. As a **privacy-conscious user**, I want secrets and long outputs redacted before anything leaves my machine, so receipts are safe to post publicly.
7. As a **maintainer**, I want the receipt to include the tool/MCP inventory and token usage, so I can see cost and integration sprawl per PR.

## 5. Core features

### MVP (Phases 1–2)
- **Adapters**: parse Claude Code transcripts (`~/.claude/projects/**/*.jsonl`) and Codex CLI rollouts (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` / `codex exec --json` stream) into one normalized `Event` schema.
- **Session matcher**: find the session(s) that touched the current git repo/branch (by `cwd`, timestamps and files changed).
- **Verification verdict**: classify commands as test / lint / build / other using defaults + policy file; compute `VERIFIED`, `STALE` (tests ran before the last edit), `FAILED`, or `UNVERIFIED`.
- **Risk scanner**: ~25 built-in rules (destructive FS, git history rewrite, secret access, network install, DB drop, permission change, CI config edit) with severity.
- **Redactor**: strip tokens/keys (regex + entropy), truncate long outputs, hash home paths.
- **Renderers**: Markdown (PR comment) and JSON (machine-readable) receipt.
- **CLI**: `scan`, `render`, `ls`.

### Later (Phases 3–4)
- GitHub Action that uploads the receipt and posts/updates a sticky PR comment.
- Self-contained HTML receipt with timeline view.
- Receipt signing (hash of redacted receipt + commit SHA) so it can't be silently edited.
- Extra adapters (Gemini CLI, Aider, Cursor exports) via a plugin interface.
- `agent-receipts diff-map`: map each changed hunk back to the agent step that wrote it.

## 6. Non-goals

- Not a real-time permission gate or sandbox (no blocking of agent actions).
- Not an agent runtime, orchestrator or hosting platform.
- Not an LLM-based judge in the MVP — rules are deterministic and explainable. (An optional LLM summary may come later, opt-in only.)
- No hosted backend, accounts or telemetry. Everything runs locally or in the user's own CI.
- Does not upload raw transcripts anywhere.

## 7. Success metrics

| Metric | Target (first 3 months after v0.1) |
|---|---|
| Parse success on real Claude Code + Codex sessions in the test corpus | ≥ 95% of events mapped to a known type |
| Risk-rule precision on labelled fixture set | ≥ 90% (few false alarms) |
| Time for `scan` on a 5,000-event session | < 2 s on a laptop |
| Secrets leaked in rendered receipts (fixture suite) | 0 |
| Reviewer time-to-decision (self-run dogfood, 20 PRs) | measured and reported honestly in README; no target claimed upfront |
| External adoption | 10 repos using the Action, 50 GitHub stars |

## 8. Risks & open questions

- Log formats are undocumented and change between versions → versioned adapters + fixture tests + graceful "unknown event" handling.
- Users may post receipts containing sensitive paths/output → redaction on by default; `--no-redact` requires an explicit flag.
- In CI the session logs are on the developer's machine, not the runner → MVP flow is: dev runs `agent-receipts render --out .agent-receipt.json` and commits/attaches it; Action renders from that artifact.
