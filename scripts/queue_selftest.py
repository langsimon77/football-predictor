"""Round trip of the Question Queue on GitHub: open, tick, read back, close.

Uses a made-up match, so the daily run can never act on it, and closes the Issue
at the end. Run by .github/workflows/queue_selftest.yml with the bot's token,
the same path the daily run uses.

    uv run python scripts/queue_selftest.py
"""

from __future__ import annotations

import sys

import pandas as pd

from fp.news import github, queue
from fp.news.impact import TeamNews

MATCH = "TEST_2627_home_club_away_club"


def main() -> int:
    now = pd.Timestamp.now(tz="UTC")
    q = queue.TeamNewsQuestion(MATCH, "EPL", now + pd.Timedelta(days=2), "home_club",
                               "away_club", 0.04)
    _, body = queue.render([q], [], {"home_club": "Home Club", "away_club": "Away Club"}, now)
    title = f"{queue.TITLE_PREFIX}TEST of the Question Queue, please ignore"
    number = github.create_issue(title, body)
    print(f"opened #{number}")
    ok = False
    try:
        found = [i for i in github.open_issues(queue.TITLE_PREFIX) if i["number"] == number]
        assert found, "new Issue not listed"
        ticked = "\n".join(line.replace("- [ ]", "- [x]")
                           if f"fp:{MATCH}:home:2 -->" in line
                           or f"fp:{MATCH}:away:threat -->" in line else line
                           for line in body.splitlines())
        github._api("-X", "PATCH", f"repos/{github.repo()}/issues/{number}", "-f",
                    f"body={ticked}")
        issue = [i for i in github.open_issues(queue.TITLE_PREFIX) if i["number"] == number][0]
        edits = github.editors(number)
        author = str(issue["user"]["login"])
        print(f"author {author}, edits by {edits}")
        assert github.trusted(author, edits, github.owner()), "trust rule rejected the bot"
        assert not github.trusted("stranger", edits, github.owner())
        news, _ = queue.answers(str(issue["body"]))
        assert news[MATCH]["home"] == TeamNews("answered", 2, False), news
        assert news[MATCH]["away"] == TeamNews("answered", 1, True), news
        ok = True
        print("ticks read back correctly")
    finally:
        github.close_issue(number, "Self-test finished: " + ("passed." if ok else "FAILED."))
        print(f"closed #{number}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
