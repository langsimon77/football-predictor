"""The news loop inside the daily run.

Before locking (`gather`): read ticks from the open question Issues that pass the
trust rule, read managers from Wikipedia for clubs playing in the next 72 hours,
and apply Lang's manager answers.

After locking (`after_lock`): record the answers used, ask about matches that
lock at the next run (one Issue a day, at most 10 questions), and close Issues
whose matches have all locked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from fp import ROOT
from fp.models import dixon_coles as dc
from fp.news import github, managers, queue
from fp.news.impact import TeamNews

log = logging.getLogger(__name__)

NEWS_LIVE = False  # switched on only after Lang approves Phase 5
ANSWERS = ROOT / "data" / "manual" / "answers.yaml"
UNANSWERED = TeamNews("unanswered")


@dataclass
class MatchNews:
    home: TeamNews
    away: TeamNews
    source: str

    def unanswered(self, match_id: str) -> list[str]:
        return [f"{match_id}:{side}" for side, news in (("home", self.home),
                                                         ("away", self.away))
                if not news.usable]


@dataclass
class NewsState:
    by_match: dict[str, MatchNews] = field(default_factory=dict)
    manager_flags: set[str] = field(default_factory=set)
    manager_changes: list[tuple[str, str, str]] = field(default_factory=list)
    manager_log: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=managers.COLUMNS))
    issues: list[dict] = field(default_factory=list)  # trusted open question Issues
    asked: set[str] = field(default_factory=set)


def gather(fixtures: pd.DataFrame, now: pd.Timestamp, use_github: bool,
           use_wikipedia: bool = True) -> NewsState:
    state = NewsState()
    manager_answers: dict[str, str] = {}
    if use_github:
        try:
            for issue in github.open_issues(queue.TITLE_PREFIX):
                number = int(issue["number"])
                author = str(issue["user"]["login"])
                if not github.trusted(author, github.editors(number), github.owner()):
                    log.warning("Issue #%d fails the trust rule; its ticks are ignored", number)
                    continue
                news, mgr = queue.answers(str(issue.get("body") or ""))
                for match_id, sides in news.items():
                    state.asked.add(match_id)
                    state.by_match[match_id] = MatchNews(
                        sides.get("home", UNANSWERED), sides.get("away", UNANSWERED),
                        f"Issue #{number}")
                manager_answers.update(mgr)
                state.issues.append(issue)
        except Exception:
            log.exception("could not read question Issues; locking without news")
    frame = managers.apply_answers(managers.load(), manager_answers)
    if use_wikipedia:
        soon = fixtures[(fixtures["kickoff_utc"] > now)
                        & (fixtures["kickoff_utc"] <= now + pd.Timedelta(hours=72))]
        teams = sorted(set(soon["home_id"]) | set(soon["away_id"]))
        titles = managers.titles()
        seen = {t: name for t in teams if t in titles
                and (name := managers.current(t, titles[t])) is not None}
        frame, state.manager_changes = managers.observe(frame, seen, now)
    state.manager_log = frame
    state.manager_flags = managers.recent_changes(frame, now)
    return state


def record_answers(state: NewsState, locked_ids: list[str], now: pd.Timestamp,
                   path: Path = ANSWERS) -> None:
    """Append the answers used by this run's locks to data/manual/answers.yaml."""
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    rows = rows or []
    for match_id in locked_ids:
        news = state.by_match.get(match_id)
        if news is None:
            continue
        for side, answer in (("home", news.home), ("away", news.away)):
            rows.append({"question": f"{match_id}:{side}", "status": answer.status,
                         "starters_out": answer.starters_out, "threat_out": answer.threat_out,
                         "source": news.source, "used_at_utc": f"{now:%Y-%m-%dT%H:%MZ}"})
    path.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")


def after_lock(state: NewsState, fixtures: pd.DataFrame, locked_ids: list[str],
               ledger_ids: set[str], fits: dict[str, dc.DCFit], names: dict[str, str],
               now: pd.Timestamp, dry_run: bool, use_github: bool) -> str | None:
    """Ask tomorrow's questions and tidy up. Returns the Issue body it would post."""
    manager_qs = [queue.ManagerQuestion(t, new, old, now)
                  for t, old, new in state.manager_changes]
    window = queue.to_ask(fixtures, now, state.asked)
    team_qs = queue.rank(window, fits)[:max(queue.MAX_QUESTIONS - len(manager_qs), 0)]
    body = None
    if team_qs or manager_qs:
        title, body = queue.render(team_qs, manager_qs, names, now)
        if dry_run or not use_github:
            log.info("would open %r with %d match and %d manager questions", title,
                     len(team_qs), len(manager_qs))
        else:
            number = github.create_issue(title, body)
            log.info("opened Issue #%d: %s", number, title)
    if dry_run:
        return body
    record_answers(state, locked_ids, now)
    managers.save(state.manager_log)
    if use_github:
        done = ledger_ids | set(locked_ids)
        for issue in state.issues:
            news, _ = queue.answers(str(issue.get("body") or ""))
            created = pd.Timestamp(issue["created_at"])
            if (news and set(news) <= done) or (not news
                                                and created < now - pd.Timedelta(days=7)):
                github.close_issue(int(issue["number"]),
                                   f"All matches in this Issue locked by the run at "
                                   f"{now:%Y-%m-%d %H:%M} UTC. Answers used are in "
                                   "`data/manual/answers.yaml`.")
    return body
