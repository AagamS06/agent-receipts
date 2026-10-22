# Phases — agent-receipts

Each phase ends with explicit exit criteria. Don't start the next phase until they're met (small overlap for docs is fine).

---

## Phase 0 — Setup (target: week 1)

**Goal:** a repo anyone can clone, install and run `agent-receipts --version` in under 2 minutes.

- [x] Create public repo with README, LICENSE (MIT) and topics
- [x] Write PRD, Architecture, Rules, Phases, Design and Memory docs
- [ ] `pyproject.toml` with package metadata, deps, ruff and pytest config
- [ ] `src/agent_receipts/` package skeleton matching Architecture.md
- [ ] Hello-world CLI (`agent-receipts --version`, `agent-receipts scan` stub)
- [ ] Smoke test (`tests/test_cli.py`)
- [ ] `.gitignore` covering secrets and local receipts
- [ ] Sample policy file `.agent-receipts.example.toml`
- [ ] GitHub Actions CI: ruff + pytest on 3.11 / 3.12
- [ ] Collect 6+ anonymised real sessions (3 Claude Code, 3 Codex) into `tests/fixtures/`

**Exit criteria:** `pipx install .` works; `pytest` green in CI; fixtures committed and verified free of secrets.

## Phase 1 — Ingest + verification (MVP core, weeks 2–3)

**Goal:** turn any recent session into a normalized timeline and a correct verification verdict.

- [ ] `models.py` — Event, Verdict, Finding, Receipt (pydantic)
- [ ] `adapters/claude_code.py` — tool_use/tool_result pairing, usage, cwd
- [ ] `adapters/codex.py` — `item.*` events, both `type`/`item_type` spellings
- [ ] Adapter auto-detect + "unknown event" counting
- [ ] `discovery.py` — find sessions by git root, `--since`, touched files
- [ ] `classify.py` — default test/lint/build patterns (pytest, npm test, cargo test, go test, ruff, eslint, tsc, make test…)
- [ ] `verify.py` — VERIFIED / STALE / FAILED / UNVERIFIED with reason string
- [ ] `agent-receipts scan` terminal output (Rich)
- [ ] Tests: adapters (4 cases each), verify (≥ 10 timeline cases)

**Exit criteria:** on all fixtures, ≥ 95% events typed; verdict matches hand labels on 100% of verify tests; `scan` < 2 s on 5k events.

## Phase 2 — Risk, redaction, rendering (MVP complete, weeks 4–5)

**Goal:** a receipt that is safe to paste into a public PR.

- [ ] Rule engine + 25 built-in rules (FS, GIT, SEC, NET, DB, CI, PERM)
- [ ] `.agent-receipts.toml` policy: custom test commands, rule severity overrides, allowlist
- [ ] `redact.py` — key patterns, entropy, truncation, home-path masking
- [ ] Markdown renderer (Jinja2) following Design.md receipt layout
- [ ] JSON renderer + exported JSON Schema (`schema/receipt.v1.json`)
- [ ] `usage.py` — tokens per model, tool and MCP inventory
- [ ] Assumption extraction from agent messages
- [ ] `agent-receipts render` and `ls`
- [ ] `mypy --strict` passing
- [ ] Tests: each rule TP + near-miss; redactor leak suite

**Exit criteria:** zero leaks in redaction suite; rule precision ≥ 90% on labelled fixtures; dogfood on 10 of my own agent PRs.

## Phase 3 — Hardening + GitHub Action (weeks 6–7)

**Goal:** reviewers get receipts automatically on PRs.

- [ ] `action/action.yml` composite Action: render from uploaded JSON, sticky comment
- [ ] `agent-receipts publish --pr N` (uses local `gh`)
- [ ] Markdown injection hardening (mentions, HTML, links)
- [ ] Receipt hash + head SHA footer (tamper-evident)
- [ ] Large-file + corrupt-file fuzz tests
- [ ] Dependabot + CodeQL
- [ ] Docs: troubleshooting, "how verdicts work", rule catalogue

**Exit criteria:** Action used on this repo's own PRs for 2 weeks without a false-critical; CI time < 3 min.

## Phase 4 — Launch (week 8)

**Goal:** first external users.

- [ ] v0.1.0 release on PyPI (`pipx install agent-receipts`)
- [ ] HTML receipt with timeline (Design.md)
- [ ] Demo GIF + example receipt in README
- [ ] Write-up post (what I learned parsing agent logs)
- [ ] Share in r/ClaudeAI, r/Python, Hacker News "Show HN", LinkedIn
- [ ] Collect feedback issues; triage into Backlog

**Exit criteria:** 10 repos using the Action or CLI; 3 external issues/PRs; post-launch notes in Memory.md.

## Backlog (post-launch)

- [ ] Adapters: Gemini CLI, Aider, Cursor/Windsurf exports (plugin entry points)
- [ ] `diff-map`: hunk → agent step attribution
- [ ] Opt-in LLM summary (bring-your-own key, off by default)
- [ ] VS Code extension showing receipt for current branch
- [ ] Org-level policy packs
