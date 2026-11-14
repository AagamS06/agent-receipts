import pytest

from agent_receipts.classify import classify, segments
from agent_receipts.models import Event
from agent_receipts.policy import Policy
from agent_receipts.verify import verdict


def ev(i: int, kind: str, cmd: str | None = None, code: int | None = None) -> Event:
    return Event(
        idx=i,
        harness="claude_code",
        kind=kind,
        command=cmd,
        exit_code=code,  # type: ignore[arg-type]
        paths=["a.py"] if kind == "file_edit" else [],
    )


def status(events: list[Event]) -> str:
    classify(events, Policy())
    return verdict(events).status


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        ([ev(0, "file_edit"), ev(1, "command", "pytest -q", 0)], "VERIFIED"),
        ([ev(0, "file_edit"), ev(1, "command", "pytest -q", 1)], "FAILED"),
        ([ev(0, "command", "pytest", 0), ev(1, "file_edit")], "STALE"),
        ([ev(0, "file_edit")], "UNVERIFIED"),
        ([ev(0, "file_edit"), ev(1, "command", "ls", 0)], "UNVERIFIED"),
        (
            [ev(0, "file_edit"), ev(1, "command", "pytest", 1), ev(2, "command", "pytest", 0)],
            "VERIFIED",
        ),
        (
            [
                ev(0, "file_edit"),
                ev(1, "command", "pytest", 0),
                ev(2, "command", "ruff check .", 1),
            ],
            "FAILED",
        ),
        ([ev(0, "file_edit"), ev(1, "command", "cd api && npm test", 0)], "VERIFIED"),
        ([ev(0, "file_edit"), ev(1, "command", "CI=1 pnpm run test", 0)], "VERIFIED"),
        ([ev(0, "file_edit"), ev(1, "command", "cargo test", None)], "VERIFIED"),
        ([ev(0, "command", "go test ./...", 0)], "VERIFIED"),
        ([ev(0, "file_edit"), ev(1, "command", "make test", 2), ev(2, "file_edit")], "STALE"),
    ],
)
def test_verdicts(events: list[Event], expected: str) -> None:
    assert status(events) == expected


def test_segments_strip_prefixes() -> None:
    assert segments("cd web && NODE_ENV=test npm test; echo ok") == [
        "cd web",
        "npm test",
        "echo ok",
    ]


def test_policy_adds_custom_test_command() -> None:
    p = Policy()
    p.tests.append(r"^just check\b")
    events = [ev(0, "file_edit"), ev(1, "command", "just check", 0)]
    classify(events, p)
    assert verdict(events).status == "VERIFIED"


def test_heredoc_bodies_are_not_commands() -> None:
    cmd = "cat > notes.md <<'EOF'\nrm -rf /\nEOF\npytest -q"
    assert segments(cmd) == ["cat > notes.md <<'EOF'", "pytest -q"]


def test_binary_paths_are_normalised() -> None:
    events = [ev(0, "file_edit"), ev(1, "command", "/tmp/venv/bin/pytest -q 2>&1 | tail -3", 0)]
    classify(events, Policy())
    assert verdict(events).status == "VERIFIED"
    assert verdict(events).checks == ["pytest -q 2>&1 | tail -3"]
