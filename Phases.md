# Phases — agent-receipts

Each phase ends with explicit exit criteria. Don't start the next phase until they're met (small overlap for docs is fine).

---

## Phase 0 — Setup (target: week 1)

**Goal:** a repo anyone can clone, install and run `agent-receipts --version` in under 2 minutes.

- [x] Create public repo with README, LICENSE (MIT) and topics
- [x] Write PRD, Architecture, Rules, Phases, Design and Memory docs
- [x] `pyproject.toml` with package metadata, deps, ruff and pytest config
- [x] `src/agent_receipts/` package skeleton matching Architecture.md
- [x] Hello-world CLI (`agent-receipts --version`, `agent-receipts scan` stub)
- [x] Smoke test (`tests/test_cli.py`)
- [x] `.gitignore` covering secrets and local receipts
- [x] Sample policy file `.agent-receipts.example.toml`
- [x] GitHub Actions CI: ruff + pytest on 3.11 / 3.12
- [ ] Collect 6+ anonymised real sessions (3 Claude Code, 3 Codex) into `tests/fixtures/` (v0.1.0 ships 4 synthetic fixtures + a dogfood run on a real Claude Code log)

**Exit criteria:** `pipx install .` works; `pytest` green in CI; fixtures committed and verified free of secrets.

## Phase 1 — Ingest + verification (MVP core, weeks 2–3)

**Goal:** turn any recent session into a normalized timeline and a correct verification verdict.

- [x] `models.py` — Event, Verdict, Finding, Receipt (pydantic)
- [x] `adapters/claude_code.py` — tool_use/tool_result pairing, usage, cwd
- [x] `adapters/codex.py` — `item.*` events, both `type`/`item_type` spellings
- [x] Adapter auto-detect + "unknown event" counting
- [x] `discovery.py` — find sessions by git root, `--since`, touched files (`--touching`, `--changed-since`; 0.1.1)
- [x] `classify.py` — default test/lint/build patterns (pytest, npm test, cargo test, go test, ruff, eslint, tsc, make test…)
- [x] `verify.py` — VERIFIED / STALE / FAILED / UNVERIFIED with reason string
- [x] `agent-receipts scan` terminal output (Rich)
- [x] Tests: adapters (4 cases each), verify (≥ 10 timeline cases)

**Exit criteria:** on all fixtures, ≥ 95% events typed; verdict matches hand labels on 100% of verify tests; `scan` < 2 s on 5k events.

## Phase 2 — Risk, redaction, rendering (MVP complete, weeks 4–5)

**Goal:** a receipt that is safe to paste into a public PR.

- [ ] Rule engine + 25 built-in rules (FS, GIT, SEC, NET, DB, CI, PERM) — engine done, 19 rules so far
- [x] `.agent-receipts.toml` policy: custom test commands, rule severity overrides, allowlist
- [x] `redact.py` — key patterns, entropy, truncation, home-path masking
- [x] Markdown renderer (Jinja2) following Design.md receipt layout
- [x] JSON renderer + exported JSON Schema (`schema/receipt.v1.json`, `agent-receipts schema`; 0.1.1)
- [x] `usage.py` — tokens per model, tool and MCP inventory
- [x] Assumption extraction from agent messages
- [ ] `agent-receipts render` and `ls` — `render` done (`scan` covers `ls` for now)
- [x] `mypy --strict` passing (enforced in CI; 0.1.1)
- [x] Tests: each rule TP + near-miss; redactor leak suite

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

### Shipped in v0.1.1 (2026-11-23)
JSON Schema export + `schema` command; session matching by edited files (`--touching`, `--changed-since`, "Edits here" column in `scan`); `mypy --strict` clean and in CI; 72 tests.

### Shipped in v0.1.0 (2026-11-14)
Claude skill (`skills/agent-receipts/SKILL.md`) and release zip; `rules` command; heredoc-aware command parsing (found by dogfooding on a real Claude Code log).

## Backlog (post-launch)

- [ ] Adapters: Gemini CLI, Aider, Cursor/Windsurf exports (plugin entry points)
- [ ] `diff-map`: hunk → agent step attribution
- [ ] Opt-in LLM summary (bring-your-own key, off by default)
- [ ] VS Code extension showing receipt for current branch
- [ ] Org-level policy packs
