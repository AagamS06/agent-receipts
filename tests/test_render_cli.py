import json
from pathlib import Path

from typer.testing import CliRunner

from agent_receipts.cli import app

runner = CliRunner()
FIX = Path(__file__).parent / "fixtures"


def test_render_markdown_verified_but_force_push_fails_on_high() -> None:
    res = runner.invoke(app, ["render", str(FIX / "claude_code_verified.jsonl")])
    assert res.exit_code == 1
    assert "### 🧾 Agent receipt — ✔ VERIFIED" in res.stdout
    assert "GIT002" in res.stdout and "<!-- agent-receipts -->" in res.stdout


def test_render_json_failed(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    res = runner.invoke(
        app, ["render", str(FIX / "codex_rollout_failed.jsonl"), "-f", "json", "-o", str(out)]
    )
    assert res.exit_code == 1
    data = json.loads(out.read_text())
    assert data["verdict"]["status"] == "FAILED" and data["schema_version"] == "1"


def test_render_clean_session_exits_zero(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"a","name":"Edit","input":{"file_path":"x.py"}}]}}\n'
        '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"a","content":"ok"}]}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"b","name":"Bash","input":{"command":"pytest"}}]}}\n'
        '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"b","content":"1 passed"}]}}\n'
    )
    res = runner.invoke(app, ["render", str(p)])
    assert res.exit_code == 0, res.stdout
    assert "VERIFIED" in res.stdout


def test_bad_inputs() -> None:
    assert runner.invoke(app, ["render", "nope.jsonl"]).exit_code == 2
    assert (
        runner.invoke(app, ["render", str(FIX / "claude_code_stale.jsonl"), "-f", "html"]).exit_code
        == 2
    )


def test_rules_command() -> None:
    res = runner.invoke(app, ["rules"])
    assert res.exit_code == 0 and "FS001" in res.stdout
