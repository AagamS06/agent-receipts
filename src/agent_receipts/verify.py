"""Verification verdict: did checks run after the agent's last edit, and did they pass?

* VERIFIED   — at least one check ran after the last edit and every check after it passed.
* FAILED     — a check after the last edit failed (non-zero exit).
* STALE      — checks ran and passed, but only before the last edit.
* UNVERIFIED — no tests or lint ran at all (or nothing was edited and nothing checked).
"""

from __future__ import annotations

from agent_receipts.models import Event, Verdict


def _name(e: Event) -> str:
    return " && ".join(e.check_commands) if e.check_commands else (e.command or "")


def verdict(events: list[Event]) -> Verdict:
    edits = [e for e in events if e.kind == "file_edit"]
    checks = [e for e in events if "check" in e.labels]
    last_edit = edits[-1].idx if edits else None
    names = list(dict.fromkeys(c for e in checks for c in (e.check_commands or [e.command or ""])))

    if not checks:
        what = "edited files" if edits else "made no file edits"
        return Verdict(
            status="UNVERIFIED",
            last_edit_idx=last_edit,
            checks=[],
            reason=f"The agent {what} and never ran tests or lint.",
        )

    after = [e for e in checks if last_edit is None or e.idx > last_edit]
    if not after:
        last = checks[-1]
        return Verdict(
            status="STALE",
            last_edit_idx=last_edit,
            last_check_idx=last.idx,
            checks=names,
            reason=f"Checks last ran at step {last.idx} (`{_name(last)}`), "
            f"but files were edited again at step {last_edit}.",
        )

    failed = [e for e in after if e.exit_code not in (0, None)]
    # A later passing run of the same command fixes an earlier failure.
    still_failing = [
        f
        for f in failed
        if not any(p.idx > f.idx and p.command == f.command and p.exit_code == 0 for p in after)
    ]
    last = after[-1]
    if still_failing:
        f = still_failing[-1]
        return Verdict(
            status="FAILED",
            last_edit_idx=last_edit,
            last_check_idx=f.idx,
            checks=names,
            reason=f"`{_name(f)}` exited {f.exit_code} at step {f.idx}, after the final edit.",
        )
    unknown = [e for e in after if e.exit_code is None]
    note = " (exit code not recorded for some runs)" if unknown else ""
    where = (
        f"after the final edit (step {last_edit})"
        if last_edit is not None
        else "and nothing was edited"
    )
    return Verdict(
        status="VERIFIED",
        last_edit_idx=last_edit,
        last_check_idx=last.idx,
        checks=names,
        reason=f"`{_name(last)}` ran at step {last.idx} {where} and passed{note}.",
    )
