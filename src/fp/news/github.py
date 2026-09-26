"""The few GitHub calls the Question Queue needs, through the `gh` command.

Trust rule (PRD Q3): an Issue's ticks count only if the Issue was opened by the
daily run's bot (or the repository owner) and every edit to its text was made by
the bot or the owner. In a public repository anyone can open an Issue, but only
people with write access can edit someone else's Issue text.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fp import ROOT

log = logging.getLogger(__name__)

BOT_LOGINS = {"github-actions[bot]", "github-actions"}  # REST and GraphQL spellings


def _gh() -> str | None:
    return shutil.which("gh") or next(
        (str(p) for p in (Path.home() / ".local" / "bin" / "gh",) if p.exists()), None)


def repo() -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.strip()
    return url.removesuffix(".git").split("github.com")[-1].lstrip(":/")


def owner() -> str:
    return repo().split("/")[0]


def available() -> bool:
    gh = _gh()
    if gh is None:
        return False
    return subprocess.run([gh, "auth", "status"], capture_output=True, check=False,
                          cwd=ROOT).returncode == 0


def _api(*args: str) -> Any:
    gh = _gh()
    assert gh is not None
    out = subprocess.run([gh, "api", *args], capture_output=True, text=True, check=True,
                         cwd=ROOT).stdout
    return json.loads(out) if out.strip() else None


def open_issues(title_prefix: str) -> list[dict]:
    items = _api(f"repos/{repo()}/issues?state=open&per_page=100")
    return [i for i in items if "pull_request" not in i
            and str(i.get("title", "")).startswith(title_prefix)]


def editors(number: int) -> list[str]:
    query = ("query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,"
             "name:$name){issue(number:$number){userContentEdits(first:100){nodes{"
             "editor{login}}}}}}")
    own, name = repo().split("/")
    data = _api("graphql", "-f", f"query={query}", "-F", f"owner={own}", "-F", f"name={name}",
                "-F", f"number={number}")
    nodes = data["data"]["repository"]["issue"]["userContentEdits"]["nodes"]
    return [(n.get("editor") or {}).get("login", "") for n in nodes]


def trusted(author: str, edit_logins: list[str], repo_owner: str) -> bool:
    allowed = BOT_LOGINS | {repo_owner}
    return author in allowed and all(login in allowed for login in edit_logins)


def create_issue(title: str, body: str) -> int:
    issue = _api(f"repos/{repo()}/issues", "-f", f"title={title}", "-f", f"body={body}")
    return int(issue["number"])


def close_issue(number: int, comment: str) -> None:
    _api(f"repos/{repo()}/issues/{number}/comments", "-f", f"body={comment}")
    _api("-X", "PATCH", f"repos/{repo()}/issues/{number}", "-f", "state=closed")
