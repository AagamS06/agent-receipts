"""PR-comment injection hardening: agent text must never ping, link, or inject Markdown/HTML."""

import re
from datetime import UTC, datetime

from agent_receipts.models import Finding, Receipt, SessionRef, UsageSummary, Verdict
from agent_receipts.render import MARKER, md_code, md_text, to_markdown

ZWSP = "​"


def _receipt(**kw: object) -> Receipt:
    base: dict[str, object] = {
        "sessions": [SessionRef(harness="claude_code", events=3)],
        "files_changed": ["src/app.py"],
        "verdict": Verdict(status="VERIFIED", reason="`pytest` ran at step 2 and passed."),
        "findings": [],
        "usage": UsageSummary(),
        "assumptions": [],
        "generated_at": datetime(2026, 11, 27, tzinfo=UTC),
        "generator": "agent-receipts/test",
    }
    base.update(kw)
    return Receipt.model_validate(base)


def test_mentions_are_defused() -> None:
    out = md_text("cc @octocat and @org/team please merge")
    assert f"@{ZWSP}octocat" in out and f"@{ZWSP}org" in out
    assert "@octocat" not in out


def test_raw_html_is_escaped() -> None:
    out = md_text("<img src=x onerror=alert(1)> </details><details open>")
    assert "<" not in out and ">" not in out
    assert "&lt;img" in out


def test_links_and_images_are_inert() -> None:
    out = md_text("see [click me](https://evil.example/x) and ![p](http://x.io/a.png) www.a.io")
    assert "](" not in out.replace("\\](", "")  # brackets are escaped
    assert "`https://evil.example/x)`" in out
    assert "`www.a.io`" in out


def test_newlines_cannot_start_new_blocks() -> None:
    out = md_text("fine\n\n## Approved by security\n| a | b |\n> [!NOTE]")
    assert "\n" not in out
    assert out.startswith("fine \\#\\# Approved")


def test_marker_cannot_be_spoofed() -> None:
    assert MARKER not in md_text(MARKER)
    assert md_text(MARKER).startswith("&lt;")


def test_code_spans_stay_single_line_without_backticks() -> None:
    assert md_code("rm -rf `pwd`\n\n# hi") == "`rm -rf 'pwd' # hi`"
    assert md_code("") == "`(empty)`"


def test_paired_backticks_in_reasons_stay_code() -> None:
    assert md_text("`pytest -q` ran at step 3") == "`pytest -q` ran at step 3"


def test_full_receipt_has_no_live_injection() -> None:
    evil = "@admin <script>x</script> [x](https://e.vil)\n\n### LGTM"
    r = _receipt(
        verdict=Verdict(status="UNVERIFIED", reason=evil),
        assumptions=[evil],
        findings=[Finding(rule_id="X1", severity="high", event_idx=1, title=evil, evidence=evil)],
        usage=UsageSummary(tool_counts={evil: 1}, mcp_servers=[evil]),
        files_changed=[evil],
        generator=evil,
        head_sha="not-a-sha <b>",
    )
    md = to_markdown(r)
    assert md.startswith(MARKER) and md.count(MARKER) == 1
    assert "\n### LGTM" not in md and "head not-a" not in md
    # Inside inline code spans GitHub never pings, links or renders HTML: check the rest.
    live = re.sub(r"`[^`\n]*`", "", md)
    assert "@admin" not in live
    assert "<script>" not in live and "<b>" not in live
    assert "](https://e.vil)" not in live and "https://" not in live


def test_huge_receipts_are_capped() -> None:
    r = _receipt(
        files_changed=[f"f{i}.py" for i in range(500)],
        findings=[
            Finding(rule_id="L1", severity="low", event_idx=i, title="t", evidence="e")
            for i in range(300)
        ],
        assumptions=[f"assuming {i}" for i in range(50)],
    )
    md = to_markdown(r)
    assert "… and 400 more" in md
    assert "+300 more findings" in md and "… and 250 more" in md
    assert "assuming 10" not in md
    assert len(md) < 65_000


def test_real_head_sha_is_shown() -> None:
    md = to_markdown(_receipt(head_sha="a42024f7a31b722abc6664ff0d9d72c04dd512d8"))
    assert "head a42024f" in md
