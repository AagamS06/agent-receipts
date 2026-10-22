from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_receipts import __version__
from agent_receipts.cli import app
from agent_receipts.discovery import parse_since

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


@pytest.mark.parametrize(("text", "seconds"), [("30m", 1800), ("24h", 86400), ("7d", 604800)])
def test_parse_since(text: str, seconds: int) -> None:
    assert parse_since(text) == seconds


def test_parse_since_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_since("soon")


def test_scan_no_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    result = runner.invoke(app, ["scan", "--since", "1h"])
    assert result.exit_code == 3


def test_scan_finds_codex_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    day = tmp_path / ".codex" / "sessions" / "2026" / "10" / "22"
    day.mkdir(parents=True)
    (day / "rollout-2026-10-22T10-00-00-abc.jsonl").write_text('{"type":"thread.started"}\n')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    result = runner.invoke(app, ["scan", "--since", "1h"])
    assert result.exit_code == 0
    assert "codex" in result.stdout
