"""The Question Queue: what to ask, how the Issue reads, and reading ticks back.

Timing. A match locks at the run 24 to 48 hours before kickoff. So each run asks
about matches kicking off 48 to 72 hours ahead: they lock at the next run, and
Lang has about a day to answer (spec S6.4 deadline rule).

Ranking. At most MAX_QUESTIONS a day, ranked by the expected shift in the home,
draw, away forecast that an answer would cause, under ANSWER_PRIOR [A].

Answers. Checkboxes carry hidden markers, `<!-- fp:MATCH:SIDE:OPTION -->`, so the
text around them can change without breaking the parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import numpy as np
import pandas as pd

from fp.models import dixon_coles as dc
from fp.news import impact
from fp.news.impact import TeamNews

TITLE_PREFIX = "Questions for Lang: "
ASK_MIN_HOURS, ASK_MAX_HOURS = 48, 72
MAX_QUESTIONS = 10
JUBA = "Africa/Juba"
# [A] How often a club has 0, 1, 2, or 3+ regular starters out, and its top
# scorer out. Used only to rank questions, never to adjust a forecast.
ANSWER_PRIOR = {0: 0.35, 1: 0.35, 2: 0.2, 3: 0.1}
THREAT_PRIOR = 0.15
COUNT_OPTIONS = ("0", "1", "2", "3")
MARKER = re.compile(r"^\s*[-*]\s+\[([ xX])\].*<!--\s*fp:([^\s>]+)\s*-->")


@dataclass
class TeamNewsQuestion:
    match_id: str
    league: str
    kickoff_utc: pd.Timestamp
    home_id: str
    away_id: str
    shift: float  # expected change in the home, draw, away forecast, 0 to 1


@dataclass
class ManagerQuestion:
    team_id: str
    new_manager: str
    old_manager: str
    first_seen_utc: pd.Timestamp


def to_ask(fixtures: pd.DataFrame, now: pd.Timestamp, already: set[str]) -> pd.DataFrame:
    """Matches with a confirmed kickoff 48 to 72 hours ahead, not asked before."""
    lo, hi = now + pd.Timedelta(hours=ASK_MIN_HOURS), now + pd.Timedelta(hours=ASK_MAX_HOURS)
    window = fixtures[fixtures["time_confirmed"] & (fixtures["kickoff_utc"] > lo)
                      & (fixtures["kickoff_utc"] <= hi)]
    return window[~window["match_id"].isin(already)]


def _one_x_two(lam: float, nu: float, rho: float) -> np.ndarray:
    m = dc.score_matrix(lam, nu, rho)
    return np.array([np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()])


def expected_shift(lam: float, nu: float, rho: float) -> float:
    """Expected total-variation change of the 1X2 forecast from one answer about
    each club, under ANSWER_PRIOR."""
    base = _one_x_two(lam, nu, rho)
    total = 0.0
    for side in ("home", "away"):
        for n, pn in ANSWER_PRIOR.items():
            for threat, pt in ((True, THREAT_PRIOR), (False, 1 - THREAT_PRIOR)):
                news = TeamNews("answered", max(n, int(threat)), threat)
                hs, as_, _ = (impact.scales(news, None) if side == "home"
                              else impact.scales(None, news))
                p = _one_x_two(lam * hs, nu * as_, rho)
                total += pn * pt * 0.5 * float(np.abs(p - base).sum())
    return total


def rank(window: pd.DataFrame, fits: dict[str, dc.DCFit]) -> list[TeamNewsQuestion]:
    out = []
    for match_id, league, kickoff, home, away in zip(
            window["match_id"], window["league"], window["kickoff_utc"], window["home_id"],
            window["away_id"], strict=True):
        fit = fits[str(league)]
        lam, nu = fit.rates(str(home), str(away))
        out.append(TeamNewsQuestion(str(match_id), str(league), kickoff, str(home), str(away),
                                    expected_shift(lam, nu, fit.rho)))
    return sorted(out, key=lambda q: -q.shift)


def news_link(name: str, league: str) -> str:
    words = "bajas lesionados convocatoria" if league == "LaLiga" else "team news injuries"
    return "https://www.google.com/search?q=" + quote_plus(f"{name} {words}")


def render(team_qs: list[TeamNewsQuestion], manager_qs: list[ManagerQuestion],
           names: dict[str, str], now: pd.Timestamp) -> tuple[str, str]:
    """Issue title and body. Manager checks come first, then matches by rank."""
    title = f"{TITLE_PREFIX}{now.tz_convert(JUBA):%a %d %b %Y}"
    deadline = (now + pd.Timedelta(days=1)).tz_convert(JUBA)
    lines = [
        f"Please tick before the next daily run, {deadline:%a %d %b, %H:%M} Juba time. "
        "An unticked club counts as \"don't know\": its match locks without news and "
        "its tier is capped at Medium.",
        "",
        "Count regular starters who will miss the match (injured, suspended, or left "
        "out). If the main goal threat is out, count that player too and also tick "
        "\"main goal threat is out\".",
        "",
    ]
    for mq in manager_qs:
        club = names.get(mq.team_id, mq.team_id)
        lines += [
            f"### Manager check: {club}",
            f"Wikipedia now lists **{mq.new_manager}** as {club}'s manager. We last saw "
            f"**{mq.old_manager}**. Is {mq.new_manager} in charge now?",
            f"- [ ] yes <!-- fp:manager:{mq.team_id}:yes -->",
            f"- [ ] no <!-- fp:manager:{mq.team_id}:no -->",
            "",
        ]
    for i, q in enumerate(team_qs, 1):
        home, away = names.get(q.home_id, q.home_id), names.get(q.away_id, q.away_id)
        kick = q.kickoff_utc.tz_convert(JUBA)
        league = "La Liga" if q.league == "LaLiga" else q.league
        lines += [
            f"### {i}. {home} v {away} ({league}), {kick:%a %d %b, %H:%M} Juba "
            f"({q.kickoff_utc:%H:%M} UTC)",
            f"Your answer could move this forecast by about {q.shift * 100:.1f} points. "
            f"Team news: [{home}]({news_link(home, q.league)}), "
            f"[{away}]({news_link(away, q.league)}).",
            "",
        ]
        for side, club in (("home", home), ("away", away)):
            lines.append(f"**{club}**, regular starters out:")
            lines += [f"- [ ] {'3 or more' if opt == '3' else opt} "
                      f"<!-- fp:{q.match_id}:{side}:{opt} -->" for opt in COUNT_OPTIONS]
            lines += [f"- [ ] main goal threat is out <!-- fp:{q.match_id}:{side}:threat -->",
                      f"- [ ] don't know <!-- fp:{q.match_id}:{side}:unknown -->", ""]
    lines.append("Generated by the daily run. Only ticks in this Issue count; "
                 "comments are not read.")
    return title, "\n".join(lines)


def ticks(body: str) -> tuple[dict[str, set[str]], set[str]]:
    """Ticked options per question key, and every question key present."""
    ticked: dict[str, set[str]] = {}
    present: set[str] = set()
    for line in body.splitlines():
        m = MARKER.match(line)
        if not m:
            continue
        key, _, option = m.group(2).rpartition(":")
        present.add(key)
        if m.group(1) in "xX":
            ticked.setdefault(key, set()).add(option)
    return ticked, present


def team_news(options: set[str] | None) -> TeamNews:
    """One club's ticks to an answer. Contradictory ticks count as don't know."""
    if not options:
        return TeamNews("unanswered")
    counts = options & set(COUNT_OPTIONS)
    if "unknown" in options or len(counts) > 1:
        return TeamNews("dont_know")
    threat = "threat" in options
    n = int(next(iter(counts))) if counts else 0
    return TeamNews("answered", max(n, int(threat)), threat)


def answers(body: str) -> tuple[dict[str, dict[str, TeamNews]], dict[str, str]]:
    """Team news per match and side, and manager answers (yes or no) per club."""
    ticked, present = ticks(body)
    news: dict[str, dict[str, TeamNews]] = {}
    managers: dict[str, str] = {}
    for key in sorted(present):
        head, _, side = key.rpartition(":")
        if head == "manager":
            got = ticked.get(key, set())
            if len(got) == 1:
                managers[side] = next(iter(got))
            continue
        news.setdefault(head, {})[side] = team_news(ticked.get(key))
    return news, managers
