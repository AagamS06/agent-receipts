"""Post a receipt as one sticky pull-request comment through the GitHub CLI (``gh``).

This is the only network path in agent-receipts. It runs only when the user calls
``publish``, sends nothing but the already-redacted Markdown receipt, and uses the
user's own ``gh`` login (or ``GH_TOKEN`` in GitHub Actions). No extra dependencies.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from agent_receipts.render import MARKER

#: GitHub rejects comment bodies longer than 65,536 characters.
MAX_BODY = 65_000
#: The login GitHub Actions' ``GITHUB_TOKEN`` comments as.
ACTIONS_BOT = "github-actions[bot]"
#: ``gh api`` fills these placeholders from the current repo (or ``GH_REPO``).
CURRENT_REPO = "{owner}/{repo}"


@dataclass
class GhResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str], str | None], GhResult]


class PublishError(Exception):
    """Posting failed (gh missing, not logged in, no access, PR not found…)."""


def run_gh(args: list[str], stdin: str | None = None) -> GhResult:
    """Run ``gh`` with an argument list (never a shell string)."""
    exe = shutil.which("gh")
    if exe is None:
        raise PublishError(
            "GitHub CLI (gh) not found. Install it from https://cli.github.com, "
            "then run `gh auth login`."
        )
    try:
        p = subprocess.run(
            [exe, *args], input=stdin, capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublishError(f"could not run gh: {exc}") from exc
    return GhResult(p.returncode, p.stdout, p.stderr)


@dataclass
class Publisher:
    """Create or update the single agent-receipts comment on a pull request."""

    repo: str = CURRENT_REPO
    run: Runner = run_gh

    def _api(self, args: list[str], stdin: str | None = None) -> str:
        res = self.run(["api", *args], stdin)
        if res.returncode != 0:
            first = (res.stderr.strip() or res.stdout.strip() or "unknown error").splitlines()[0]
            where = next((a for a in args if a.startswith("repos/")), "")
            raise PublishError(f"gh api {where} failed: {first}")
        return res.stdout

    def whoami(self) -> str:
        """The login comments are posted as: the gh user, or the Actions bot for GITHUB_TOKEN."""
        res = self.run(["api", "user", "--jq", ".login"], None)
        login = res.stdout.strip()
        return login if res.returncode == 0 and login else ACTIONS_BOT

    def find_comment(self, pr: int, login: str) -> int | None:
        """Id of the newest receipt comment on ``pr`` written by ``login``, if any.

        Comments by other people that merely start with the marker are ignored, so a
        crafted comment can't redirect the update.
        """
        out = self._api(
            [
                "--paginate",
                f"repos/{self.repo}/issues/{pr}/comments",
                "--jq",
                ".[] | [.id, .user.login, (.body | startswith(" + json.dumps(MARKER) + "))] | @tsv",
            ]
        )
        found: int | None = None
        for line in out.splitlines():
            cid, user, is_receipt = (line.split("\t") + ["", "", ""])[:3]
            if is_receipt == "true" and user == login and cid.isdigit():
                found = int(cid)
        return found

    def upsert(self, pr: int, body: str) -> tuple[str, str]:
        """Post ``body`` on PR ``pr``. Returns (``"created"`` | ``"updated"``, comment URL)."""
        if not body.startswith(MARKER):
            raise PublishError("refusing to post: body is not an agent-receipts receipt")
        if len(body) > MAX_BODY:
            raise PublishError(f"receipt is {len(body):,} characters; GitHub allows {MAX_BODY:,}")
        payload = json.dumps({"body": body})
        existing = self.find_comment(pr, self.whoami())
        if existing is not None:
            url = self._api(
                [
                    "-X",
                    "PATCH",
                    f"repos/{self.repo}/issues/comments/{existing}",
                    "--input",
                    "-",
                    "--jq",
                    ".html_url",
                ],
                payload,
            )
            return "updated", url.strip()
        url = self._api(
            [
                "-X",
                "POST",
                f"repos/{self.repo}/issues/{pr}/comments",
                "--input",
                "-",
                "--jq",
                ".html_url",
            ],
            payload,
        )
        return "created", url.strip()
