import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_receipts.cli import app
from agent_receipts.discovery import belongs_to, changed_files, edited_paths, edits_in, touches
from agent_receipts.models import Event, Session

runner = CliRunner()


def _session(cwd: str | None, *paths: str) -> Session:
    events = [
        Event(idx=i, harness="claude_code", kind="file_edit", tool="Edit", paths=[p])
        for i, p in enumerate(paths)
    ]
    return Session(harness="claude_code", path="s.jsonl", cwd=cwd, events=events)


def test_edited_paths_resolve_relative_to_cwd(tmp_path: Path) -> None:
    s = _session(str(tmp_path / "app"), "src/a.py", str(tmp_path / "lib" / "b.py"), "src/a.py")
    assert edited_paths(s) == [tmp_path / "app" / "src" / "a.py", tmp_path / "lib" / "b.py"]


def test_belongs_by_cwd_or_by_edit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = _session(str(repo / "sub"))
    parent_edit = _session(str(tmp_path), "repo/x.py")  # agent started one folder up
    other = _session(str(tmp_path / "other"), "y.py")
    assert belongs_to(inside, repo)
    assert belongs_to(parent_edit, repo) and edits_in(parent_edit, repo) == [repo / "x.py"]
    assert not belongs_to(other, repo)
    assert not belongs_to(_session(None), repo)


def test_touches_matches_repo_relative_and_absolute(tmp_path: Path) -> None:
    s = _session(str(tmp_path), "src/a.py", "README.md")
    assert touches(s, tmp_path, ["src/a.py", "src/zzz.py"]) == ["src/a.py"]
    assert touches(s, tmp_path, [str(tmp_path / "README.md")]) == [str(tmp_path / "README.md")]
    assert touches(s, tmp_path, ["a.py"]) == []  # no basename guessing


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "a.py").write_text("a = 1\n")
    (r / "b.py").write_text("b = 1\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")
    _git(r, "tag", "base")
    (r / "a.py").write_text("a = 2\n")  # committed change
    _git(r, "commit", "-qam", "change a")
    (r / "b.py").write_text("b = 2\n")  # working-tree change
    (r / "new.py").write_text("n = 1\n")  # untracked
    return r


def test_changed_files_since_ref(repo: Path) -> None:
    assert sorted(changed_files(repo, "base")) == ["a.py", "b.py", "new.py"]


def test_changed_files_bad_ref(repo: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        changed_files(repo, "no-such-ref")
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ValueError):
        changed_files(plain, "HEAD")


def _claude_session(home: Path, name: str, cwd: Path, edited: str) -> None:
    folder = home / ".claude" / "projects" / "p"
    folder.mkdir(parents=True, exist_ok=True)
    recs = [
        {
            "type": "assistant",
            "cwd": str(cwd),
            "sessionId": name,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "e", "name": "Edit", "input": {"file_path": edited}}
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "e", "content": "ok"}],
            },
        },
    ]
    (folder / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_render_picks_session_that_touched_changed_files(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    _claude_session(home, "touches-a", repo, "a.py")
    _claude_session(home, "parent-folder", tmp_path, "repo/new.py")
    _claude_session(home, "unrelated", repo, "docs/notes.md")
    out = tmp_path / "r.json"
    res = runner.invoke(
        app,
        [
            "render",
            "--repo",
            str(repo),
            "--changed-since",
            "base",
            "--all",
            "-f",
            "json",
            "-o",
            str(out),
        ],
    )
    assert res.exit_code in (0, 1), res.stdout
    ids = sorted(s["session_id"] for s in json.loads(out.read_text())["sessions"])
    assert ids == ["parent-folder", "touches-a"]

    res = runner.invoke(
        app, ["render", "--repo", str(repo), "--touching", "zzz.py", "--since", "1h"]
    )
    assert res.exit_code == 3 and "edited the selected files" in res.stdout

    res = runner.invoke(app, ["render", "--repo", str(repo), "--changed-since", "nope"])
    assert res.exit_code == 2


def test_scan_shows_edits_here(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("COLUMNS", "200")
    _claude_session(home, "parent-folder", tmp_path, "repo/new.py")
    res = runner.invoke(app, ["scan", "--repo", str(repo)])
    assert res.exit_code == 0, res.stdout
    assert "Edits here" in res.stdout and "claude_code" in res.stdout
