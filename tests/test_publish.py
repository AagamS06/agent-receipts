"""`publish --pr`: sticky comment create/update through a fake `gh`, never the network."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_receipts import cli
from agent_receipts.github import ACTIONS_BOT, GhResult, Publisher, PublishError
from agent_receipts.render import MARKER

runner = CliRunner()
FIX = Path(__file__).parent / "fixtures"
BODY = MARKER + "\n### receipt"


class FakeGh:
    """Records gh calls and answers like the GitHub API would."""

    def __init__(self, comments: list[tuple[int, str, str]], login: str | None = "aagam") -> None:
        self.comments = comments
        self.login = login
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, args: list[str], stdin: str | None) -> GhResult:
        self.calls.append((args, stdin))
        if args[:2] == ["api", "user"]:
            if self.login is None:
                return GhResult(1, "", "HTTP 403: Resource not accessible by integration")
            return GhResult(0, self.login + "\n", "")
        if "--paginate" in args:
            rows = [
                f"{cid}\t{user}\t{'true' if body.startswith(MARKER) else 'false'}"
                for cid, user, body in self.comments
            ]
            return GhResult(0, "\n".join(rows) + "\n", "")
        if "PATCH" in args:
            cid = args[args.index("PATCH") + 1].rsplit("/", 1)[1]
            return GhResult(0, f"https://github.com/o/r/pull/7#issuecomment-{cid}\n", "")
        if "POST" in args:
            return GhResult(0, "https://github.com/o/r/pull/7#issuecomment-999\n", "")
        return GhResult(1, "", "unexpected call")


def test_creates_comment_when_none_exists() -> None:
    gh = FakeGh([(1, "someone", "LGTM")])
    action, url = Publisher("o/r", gh).upsert(7, BODY)
    assert action == "created" and url.endswith("issuecomment-999")
    args, stdin = gh.calls[-1]
    assert "repos/o/r/issues/7/comments" in args and json.loads(stdin or "")["body"] == BODY


def test_updates_own_comment_in_place() -> None:
    gh = FakeGh([(5, "aagam", BODY + " old"), (6, "aagam", "unrelated")])
    action, url = Publisher("o/r", gh).upsert(7, BODY)
    assert action == "updated" and url.endswith("issuecomment-5")
    assert "repos/o/r/issues/comments/5" in gh.calls[-1][0]


def test_ignores_receipt_lookalikes_from_other_users() -> None:
    gh = FakeGh([(5, "mallory", BODY)])
    action, _ = Publisher("o/r", gh).upsert(7, BODY)
    assert action == "created"


def test_actions_token_matches_bot_comments() -> None:
    gh = FakeGh([(8, ACTIONS_BOT, BODY), (9, "aagam", BODY)], login=None)
    action, url = Publisher("o/r", gh).upsert(7, BODY)
    assert action == "updated" and url.endswith("issuecomment-8")


def test_refuses_non_receipt_and_oversized_bodies() -> None:
    gh = FakeGh([])
    with pytest.raises(PublishError):
        Publisher("o/r", gh).upsert(7, "hello")
    with pytest.raises(PublishError):
        Publisher("o/r", gh).upsert(7, BODY + "x" * 70_000)
    assert gh.calls == []


def test_api_errors_become_publish_errors() -> None:
    def broken(args: list[str], stdin: str | None) -> GhResult:
        return GhResult(1, "", "HTTP 404: Not Found (https://api.github.com/...)\nmore")

    with pytest.raises(PublishError, match="404"):
        Publisher("o/r", broken).upsert(7, BODY)


def test_cli_dry_run_never_calls_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise AssertionError("network used in dry run")

    monkeypatch.setattr(cli.Publisher, "upsert", boom)
    res = runner.invoke(
        cli.app,
        ["publish", str(FIX / "codex_rollout_failed.jsonl"), "--pr", "3", "--dry-run"],
    )
    assert res.exit_code == 1  # FAILED verdict keeps render's exit code
    assert "[dry run]" in res.stdout and MARKER in res.stdout
    res = runner.invoke(
        cli.app,
        [
            "publish",
            str(FIX / "codex_rollout_failed.jsonl"),
            "--pr",
            "3",
            "--dry-run",
            "--no-fail",
        ],
    )
    assert res.exit_code == 0


def test_cli_publish_from_saved_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "nested" / "receipt.json"
    res = runner.invoke(
        cli.app, ["render", str(FIX / "claude_code_stale.jsonl"), "-f", "json", "-o", str(out)]
    )
    assert out.is_file(), res.stdout
    seen: dict[str, object] = {}

    def fake_upsert(self: Publisher, pr: int, body: str) -> tuple[str, str]:
        seen.update(repo=self.repo, pr=pr, body=body)
        return "created", "https://github.com/o/r/pull/9#issuecomment-1"

    monkeypatch.setattr(cli.Publisher, "upsert", fake_upsert)
    res = runner.invoke(
        cli.app, ["publish", str(out), "--pr", "9", "--gh-repo", "o/r", "--no-fail"]
    )
    assert res.exit_code == 0, res.stdout
    assert seen["repo"] == "o/r" and seen["pr"] == 9
    assert str(seen["body"]).startswith(MARKER) and "STALE" in str(seen["body"])
    assert "Created receipt comment on PR #9" in res.stdout


def test_cli_publish_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fix = str(FIX / "claude_code_stale.jsonl")
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a receipt"}')
    assert runner.invoke(cli.app, ["publish", str(bad), "--pr", "1"]).exit_code == 2
    assert runner.invoke(cli.app, ["publish", fix, "--pr", "1", "--gh-repo", "x"]).exit_code == 2
    assert runner.invoke(cli.app, ["publish", fix, "--pr", "0"]).exit_code == 2
    assert runner.invoke(cli.app, ["publish", fix, str(bad), "--pr", "1"]).exit_code == 2

    def fail(self: Publisher, pr: int, body: str) -> tuple[str, str]:
        raise PublishError("gh not found")

    monkeypatch.setattr(cli.Publisher, "upsert", fail)
    res = runner.invoke(cli.app, ["publish", fix, "--pr", "1"])
    assert res.exit_code == 4 and "gh not found" in res.stdout


def test_render_accepts_saved_json(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    runner.invoke(
        cli.app, ["render", str(FIX / "codex_rollout_failed.jsonl"), "-f", "json", "-o", str(out)]
    )
    res = runner.invoke(cli.app, ["render", str(out)])
    assert res.exit_code == 1 and "FAILED" in res.stdout and res.stdout.startswith(MARKER)
