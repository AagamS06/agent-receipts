from pathlib import Path

from agent_receipts.adapters import detect, load

FIX = Path(__file__).parent / "fixtures"


def test_detect() -> None:
    assert detect(FIX / "claude_code_verified.jsonl") == "claude_code"
    assert detect(FIX / "codex_rollout_failed.jsonl") == "codex"
    assert detect(FIX / "codex_exec_unverified.jsonl") == "codex"


def test_claude_code_pairs_tool_results() -> None:
    s = load(FIX / "claude_code_verified.jsonl")
    assert s.session_id and s.cwd == "/home/dev/acme-api"
    cmds = [e for e in s.events if e.kind == "command"]
    assert [c.exit_code for c in cmds] == [1, 0, 0]
    edits = [e for e in s.events if e.kind == "file_edit"]
    assert edits[0].paths == ["/home/dev/acme-api/src/limiter.py"]
    assert any(e.kind == "usage" and e.model == "claude-sonnet-4-5" for e in s.events)
    assert s.unknown_records == 0


def test_codex_rollout() -> None:
    s = load(FIX / "codex_rollout_failed.jsonl")
    cmds = [e for e in s.events if e.kind == "command"]
    assert [(c.command, c.exit_code) for c in cmds] == [("npm test", 0), ("npm test", 1)]
    edit = next(e for e in s.events if e.kind == "file_edit")
    assert edit.paths == ["src/invoice.ts", "migrations/2026_11_14_add_proration.sql"]
    assert s.cwd == "/home/dev/billing"


def test_codex_exec_stream_accepts_both_spellings_and_counts_unknown() -> None:
    s = load(FIX / "codex_exec_unverified.jsonl")
    kinds = [e.kind for e in s.events]
    assert "file_edit" in kinds and "mcp_call" in kinds
    assert s.unknown_records == 1


def test_garbage_lines_never_crash(tmp_path: Path) -> None:
    p = tmp_path / "rollout-x.jsonl"
    p.write_text('not json\n[1,2]\n{"type":"event_msg","payload":{"type":"weird"}}\n')
    s = load(p)
    assert s.unknown_records == 2 and s.events == []
