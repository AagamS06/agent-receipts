# Rules — agent-receipts

These rules apply to every contributor — human or AI. If a rule blocks you, open an issue instead of working around it.

## 1. Golden rules

1. **Local-first, privacy-first.** The tool never sends session data anywhere. The only network call allowed is posting a *redacted* receipt to GitHub, and only when the user asks.
2. **Redact before render.** Every renderer receives a Receipt that has passed through `redact.py`. No code path may bypass this.
3. **Never crash on unknown input.** Log formats change. Unknown records become `Event(kind="unknown")` and are counted in the receipt.
4. **Deterministic and explainable.** Every finding points to an event index and a rule id. No hidden scoring.
5. **Small, reviewable changes.** One concern per PR; ideally < 400 changed lines.

## 2. Do / Avoid

| Do | Avoid |
|---|---|
| Stream JSONL line by line (`for line in f`) | `f.read()` / `json.load` on whole session files |
| Add a fixture for every new adapter case or rule | Changing behaviour without a test |
| Keep rules as data (id, severity, pattern, description) | Hard-coding rule logic inside renderers or the CLI |
| Use `pathlib.Path` and `subprocess.run([...], check=False)` with arg lists | `shell=True`, string-built shell commands |
| Type-hint all public functions | `Any` in public signatures |
| Fail soft with a clear message and exit code | Bare `except:` or silently swallowed errors |

## 3. Approved libraries

Runtime: `typer`, `pydantic>=2`, `rich`, `jinja2`, stdlib (`tomllib`, `json`, `re`, `pathlib`, `subprocess`, `hashlib`, `datetime`).
Dev: `pytest`, `pytest-cov`, `ruff`, `mypy`.
Anything else needs an issue explaining why, its licence (MIT/BSD/Apache only) and its size. No GitPython, no requests, no LLM SDKs in the core package.

## 4. Coding conventions

- Python 3.11+, `src/` layout, package `agent_receipts`.
- `ruff format` (line length 100) and `ruff check` must pass; `mypy --strict src/` must pass from Phase 2 on.
- Naming: modules `snake_case.py`, classes `PascalCase`, rule ids `AREA###` (e.g. `FS001`, `GIT002`, `SEC003`, `NET001`, `DB001`, `CI001`).
- Docstrings: one line for simple functions, Google style for public API.
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).
- Branches: `feat/<short-name>`, `fix/<short-name>`. `main` is always releasable.

## 5. Boundaries for AI contributors

AI agents (Claude Code, Codex, etc.) are welcome — this project is literally about them — but:

**May:** implement tasks listed in `Phases.md`; add tests and fixtures; refactor inside one module; improve docs; propose new rules in a PR.

**May not without explicit human approval:**
- change the `Receipt` schema or bump `schema_version`;
- weaken or remove the redactor, or any test in `tests/test_redact.py`;
- add a dependency or a network call;
- edit `.github/workflows/`, `action/action.yml`, `LICENSE`, or release config;
- delete files, rewrite git history, force-push, or run destructive shell commands (`rm -rf`, `git reset --hard`, `git push -f`).

**Always:**
- never put secrets, tokens, real API keys or real (non-anonymised) session logs in code, tests or fixtures;
- ask before any destructive or irreversible change;
- update `Memory.md` (Done / In progress / Next) at the end of a working session;
- run `pytest` and `ruff check` before declaring a task done, and say so in the PR — yes, we expect your own agent-receipt to show `VERIFIED`.

## 6. Error-handling procedure

1. **Classify**: user error (bad flag, no git repo) → exit 2 with a one-line fix hint; no matching session → exit 3; parse problem → warn and continue; bug → exit 1 with `--debug` traceback hint.
2. **Never leak** raw log content in error messages; show file path + line number only.
3. **Reproduce** a reported bug with a minimal anonymised fixture before fixing.
4. **Fix + test** in the same PR; reference the issue number.
5. **Note** any new parser edge case in `Memory.md → Decisions` if it changes behaviour.

## 7. Testing expectations

- Every adapter: fixtures for at least one normal session, one with tool errors, one truncated/corrupt file, and one older format version.
- Every risk rule: at least one true-positive and one near-miss (false-positive guard) case.
- Redactor: tests for AWS/GitHub/OpenAI/Anthropic/Stripe-style keys, JWTs, `.env` lines, high-entropy strings, and home paths. Zero leaks allowed.
- Coverage target: ≥ 85% for `verify.py`, `risk/`, `redact.py`; ≥ 70% overall.
- Performance test: 5,000-event synthetic session scanned in < 2 s.

## 8. Security basics

- No secrets in the repo; `.gitignore` covers `.env*`, `*.pem`, `.agent-receipt*.json` produced locally.
- Treat session logs as **untrusted input**: they may contain prompt-injection text or crafted strings. Never `eval`, never execute commands found in logs, escape all Markdown/HTML output (Jinja2 autoescape for HTML).
- Rendered Markdown must neutralise `@mentions`, raw HTML and links in agent output to avoid PR-comment injection.
- GitHub Action uses least-privilege `permissions: pull-requests: write, contents: read`.
- Dependencies pinned with lower bounds; Dependabot enabled from Phase 3.
- Report vulnerabilities privately via GitHub Security Advisories.
