"""UEFA club competition results from openfootball/champions-league (public domain).

Lang approved building Champions League forecasts for the goals markets on 14 Oct
2026 (corners and cards left out: no source has them). The files are in the
football.txt text format, one per competition and season:
cl.txt (Champions League), el.txt (Europa League), conf.txt (Conference League),
and from 2024/25 the qualifiers clq.txt, elq.txt, confq.txt.

Lines look like
    ▪ League, Matchday 1                 (round; older files: "▪ Group A")
      Tue Sep 17 2024                    (date; the year is often left out)
        18:45  BSC Young Boys (SUI)  v Aston Villa FC (ENG)  0-3 (0-2)
               Club A (ESP) v Club B (ENG)  4-3 pen. 1-1 a.e.t. (1-1, 0-1)
The goals models use the score after 90 minutes: for a match that went to extra
time it is the first score in brackets. Kickoff times are Central European.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from fp.ingest.http import fetch

SOURCE = "openfootball_uefa"
BASE_URL = "https://raw.githubusercontent.com/openfootball/champions-league/master"
COMPETITIONS = {"cl": "UCL", "el": "UEL", "conf": "UECL",
                "clq": "UCL qualifying", "elq": "UEL qualifying", "confq": "UECL qualifying"}
TIME_ZONE = "Europe/Paris"
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

ROUND = re.compile(r"^\s*▪\s*(.+?)\s*$")
DATE = re.compile(r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})"
                  r"(?:\s+(\d{4}))?\s*$")
TEAM = r"(.+?)\s+\(([A-Z]{2,3})\)"
MATCH = re.compile(r"^\s+(?:(\d{1,2}:\d{2})\s+)?" + TEAM + r"\s+v\s+" + TEAM
                   + r"(?:\s+(.*?))?\s*(?:@.*)?$")
SCORE = re.compile(r"^(\d+)-(\d+)")
BRACKET = re.compile(r"\((\d+)-(\d+)(?:,\s*(\d+)-(\d+))?\)")


@dataclass
class Score:
    home: int
    away: int
    ht_home: int | None
    ht_away: int | None
    extra_time: bool
    penalties: bool


def parse_score(text: str) -> Score | None:
    """The 90-minute score and half-time score, or None if the match has no result."""
    text = text.strip()
    if not SCORE.match(text):
        return None
    pens = " pen." in text
    aet = "a.e.t." in text
    bracket = BRACKET.search(text)
    if aet:
        if bracket is None:
            raise ValueError(f"extra-time score without the 90-minute score: {text!r}")
        h, a = int(bracket.group(1)), int(bracket.group(2))
        ht = (int(bracket.group(3)), int(bracket.group(4))) if bracket.group(3) else (None, None)
    else:
        first = SCORE.match(text)
        assert first is not None
        h, a = int(first.group(1)), int(first.group(2))
        ht = (int(bracket.group(1)), int(bracket.group(2))) if bracket else (None, None)
        if h == 0 and a == 0 and ht == (None, None):
            ht = (0, 0)  # a 0-0 is written without its half-time score
    return Score(h, a, ht[0], ht[1], aet, pens)


def parse(text: str, season: int, competition: str) -> pd.DataFrame:
    """One row per match in a football.txt file; matches without a result are kept
    with empty goals, so the file's fixtures are visible too."""
    rows: list[dict] = []
    round_name: str | None = None
    day: date | None = None
    last_time: str | None = None  # a time line carries over to the lines below it
    last_year: int | None = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith(("#", "=", "(")):
            continue
        if m := ROUND.match(line):
            round_name = m.group(1)
            continue
        if m := DATE.match(line):
            month, dom = MONTHS[m.group(1)], int(m.group(2))
            qualifying = competition.endswith("q")
            if m.group(3):
                year = int(m.group(3))
            elif qualifying:
                year = season  # qualifiers run from June to August
            elif month <= 6:
                year = season + 1  # main competitions: spring knockouts and the final
            else:
                # Autumn, unless the file has already reached the next year: 2019/20
                # finished in August 2020.
                year = season + 1 if last_year == season + 1 else season
            last_year = year
            day = date(year, month, dom)
            last_time = None
            continue
        if m := MATCH.match(line):
            if day is None:
                raise ValueError(f"line {number}: match before any date")
            if m.group(1):
                last_time = m.group(1)
            score = parse_score(m.group(6) or "")
            kickoff = (pd.Timestamp(f"{day} {last_time}").tz_localize(TIME_ZONE).tz_convert("UTC")
                       if last_time else pd.NaT)
            rows.append({
                "competition": COMPETITIONS[competition], "season": season,
                "round": round_name, "date": day, "kickoff_utc": kickoff,
                "home_name": m.group(2).strip(), "home_country": m.group(3),
                "away_name": m.group(4).strip(), "away_country": m.group(5),
                "home_goals": score.home if score else None,
                "away_goals": score.away if score else None,
                "ht_home_goals": score.ht_home if score else None,
                "ht_away_goals": score.ht_away if score else None,
                "extra_time": bool(score and score.extra_time),
                "penalties": bool(score and score.penalties),
                "neutral": is_neutral(round_name, season, competition),
            })
            continue
        if " v " in line:
            raise ValueError(f"line {number}: could not read {line.strip()!r}")
    out = pd.DataFrame(rows)
    for c in ("home_goals", "away_goals", "ht_home_goals", "ht_away_goals"):
        if c in out:
            out[c] = out[c].astype("Int64")
    return out


def is_neutral(round_name: str | None, season: int, competition: str) -> bool:
    """Finals are at a neutral ground; so was every 2019/20 knockout match after the
    round of 16 (played in Lisbon, Cologne and Germany's other host cities because of
    COVID-19). Other COVID-era relocations are not recorded in the files [A]."""
    r = (round_name or "").lower()
    if r.endswith("final") and "semi" not in r and "quarter" not in r:
        return True
    return season == 2019 and any(k in r for k in ("quarter", "semi"))


# Which files openfootball has, by competition: first and last season start year
# (repository listing checked 20 Oct 2026). Asking for a file that does not exist made
# the downloader wait on GitHub for hours, so only these are fetched.
AVAILABLE = {"cl": (2011, 2025), "el": (2020, 2024), "conf": (2021, 2024),
             "clq": (2024, 2025), "elq": (2024, 2025), "confq": (2024, 2025)}


def download(season: int, competition: str, current_season: int) -> Path | None:
    first, last = AVAILABLE.get(competition, (0, 9999))
    if not first <= season <= last:
        return None
    folder = f"{season}-{(season + 1) % 100:02d}"
    try:
        return fetch(f"{BASE_URL}/{folder}/{competition}.txt", SOURCE,
                     f"{folder}_{competition}.txt", refresh=season == current_season)
    except Exception:  # not every competition exists every season (qualifiers from 2024/25)
        return None


def load(seasons: range | list[int], current_season: int,
         competitions: tuple[str, ...] = tuple(COMPETITIONS)) -> pd.DataFrame:
    frames = []
    for season in seasons:
        for comp in competitions:
            path = download(season, comp, current_season)
            if path is not None:
                frames.append(parse(path.read_text(encoding="utf-8"), season, comp))
    return pd.concat(frames, ignore_index=True)
