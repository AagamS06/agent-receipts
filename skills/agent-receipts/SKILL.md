---
name: agent-receipts
description: Turn a Claude Code or Codex CLI session log into a reviewable "receipt" for the code that agent wrote — did tests or lint run after the last edit (VERIFIED / STALE / FAILED / UNVERIFIED), which risky actions happened (rm -rf, force push, .env reads, curl | sh, DROP TABLE, CI edits), what the agent assumed, which files changed, and tools / MCP / tokens used — using the offline agent-receipts CLI. Use it when someone asks "what did the agent actually do?", "did the agent run the tests?", "is this AI-written PR safe to merge?", "make a receipt / summary of my Claude Code or Codex session", or wants a Markdown PR comment or JSON summary of an agent session, or asks to "post the receipt on my PR" / set up the agent-receipts GitHub Action. It reads local logs only; the only thing it can send is the redacted receipt, to a PR, when asked.
---

# agent-receipts

Reads coding-agent session logs (Claude Code `~/.claude/projects/**/*.jsonl`, Codex `~/.codex/sessions/**/rollout-*.jsonl` or `codex exec --json` output) and writes a receipt. Deterministic rules, no LLM. No network, except `publish`, which posts the redacted receipt to a GitHub PR through the user's `gh` login.

## 1. Install

Python 3.11+.

```bash
pip install "git+https://github.com/AagamS06/agent-receipts.git@v0.2.0"
agent-receipts --version      # agent-receipts 0.2.0
```

## 2. Inputs

- **Nothing**: run inside the repo the agent worked in; `render` picks the latest session that ran inside it or edited a file inside it (`--since 24h` window).
- **A branch / PR**: `--changed-since origin/main` keeps only sessions that edited a file changed since that git ref (committed, uncommitted or untracked); add `--all` to combine them. `--touching FILE` (repeatable) does the same for named files.
- **A session file**: pass the `.jsonl` path. The harness is auto-detected.
- **Several sessions**: `--all --since 2h` combines every matching session.
- **A saved receipt**: one `.json` written with `render -f json` (for `render` or `publish`).
- **A PR number** (for `publish`): `--pr N`; the repo comes from `gh` in the current folder, or `--gh-repo OWNER/NAME`. Needs the GitHub CLI logged in (`gh auth login`).
- **Policy (optional)**: `.agent-receipts.toml` in the repo root (copy `.agent-receipts.example.toml`): extra test/lint commands, `fail_on`, severity overrides, project rules (`path_glob` or `command_regex`), redaction patterns.

Example sessions in the repo: `examples/claude-code-session.jsonl`, `examples/codex-rollout.jsonl`.

## 3. Run

```bash
agent-receipts scan --since 24h [--repo .]           # table: harness, time, verdict, findings, edits in repo, folder
agent-receipts render                                # Markdown receipt for the latest session in this repo
agent-receipts render path/to/session.jsonl -o receipt.md
agent-receipts render --all --since 2h -f json -o receipt.json
agent-receipts render --all --changed-since origin/main -o receipt.md   # all agent work behind this branch
agent-receipts render receipt.json                   # re-render a saved JSON receipt as Markdown
agent-receipts publish --pr 12 --all --changed-since origin/main --dry-run   # preview the PR comment
agent-receipts publish --pr 12 --all --changed-since origin/main             # post / update it
agent-receipts schema [-o receipt.v1.json]           # JSON Schema of the -f json output
agent-receipts rules                                 # list built-in rule ids
```

Exit codes for `render` and `publish`: `0` clean · `1` FAILED verdict (or STALE when `stale_is_failure = true`) or a finding at/above `fail_on` (default `high`) · `2` bad input (incl. an unknown `--changed-since` ref or not a git repo) · `3` no session found (or no session edited the selected files) · `4` (`publish`) could not post (gh missing, not logged in, no access). `publish --no-fail` exits 0 after posting.

Real output for `examples/claude-code-session.jsonl` (exit 1 because of the high finding):

```markdown
### 🧾 Agent receipt — ✔ VERIFIED
`pytest -q && ruff check .` ran at step 14 after the final edit (step 12) and passed.

| Files | Commands | Findings | Tokens |
|---|---|---|---|
| 2 | 3 | 1 high | 12k |

> [!WARNING]
> **GIT002 · high** — Force push: `git push --force origin fix/rate-limit` (step 16)
```

`publish` keeps one comment per PR: it creates it the first time and edits the same comment afterwards (only a receipt comment by the same account).

GitHub Action for CI (the user commits `.agent-receipts/receipt.json` made with `render --all --changed-since origin/main -f json -o .agent-receipts/receipt.json`): copy `examples/agent-receipts-workflow.yml` from the repo to `.github/workflows/`. It uses `AagamS06/agent-receipts/action@v0.2.0` with inputs `receipt`, `pr`, `require-receipt`, `fail-on-findings`, needs `permissions: pull-requests: write`, and can't comment on PRs from forks (read-only token).

JSON (`-f json`) follows schema version 1: `verdict{status, reason, checks, last_edit_idx, last_check_idx}`, `findings[{rule_id, severity, title, evidence, event_idx}]`, `files_changed`, `assumptions`, `usage{tokens_by_model, total_tokens, tool_counts, mcp_servers, commands_run}`, `sessions`, `repo`, `branch`, `head_sha`. The full JSON Schema (draft 2020-12) is `schema/receipt.v1.json` in the repo, or `agent-receipts schema`.

## 4. Explain the result

| Verdict | Meaning |
|---|---|
| VERIFIED | a test/lint command ran after the last file edit and everything after it passed |
| FAILED | a check after the last edit exited non-zero (and wasn't re-run green) |
| STALE | checks passed, but files were edited again afterwards |
| UNVERIFIED | no test or lint command ran |

| Rule ids | Area |
|---|---|
| FS001–FS002 | recursive force delete, `find -delete` / `shred` |
| GIT001–GIT005 | push, force push, hard reset/clean, history rewrite, `--no-verify` |
| SEC001–SEC003 | secrets files (`.env`, keys), secret-looking tokens in commands, printing env |
| NET001–NET002 | `curl … \| sh`, package installs |
| PERM001–PERM002 | `sudo`, world-writable `chmod` |
| DB001–DB002 | destructive SQL, migration edits |
| CI001–CI003 | CI config edits, dependency manifests, skipped tests |

`step N` = position in the merged event timeline. Lead with the verdict and the high/critical findings; quote the evidence, and say plainly when a check's exit code wasn't recorded.

## 5. Boundaries

- Run it locally; don't upload raw session logs or paste them into chat. Share the receipt (it is redacted: API keys, tokens, private keys, home paths, long output).
- It reports what the log shows. It doesn't judge code quality and can't see commands run outside the agent session.
- Log formats are undocumented and can change; unrecognised records are counted under "unrecognised records" — mention them if present.
- Don't post the receipt to a PR or anywhere else unless the user asks; when they do, show the `--dry-run` output first if they haven't seen the receipt.
- Agent text in the Markdown receipt is neutralised (no @mentions, links, raw HTML or injected Markdown), but the receipt is still public once posted on a public repo.
- Roadmap (not in v0.2.0): tamper-evident receipt hash check, HTML timeline, receipts from CI artifacts, more adapters (Gemini CLI, Aider).
