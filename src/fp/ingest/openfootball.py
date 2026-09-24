"""Fixture calendar from openfootball/football.json (public domain, CC0).

Each season file lists all 380 matches with date and local kickoff time.
EPL times are UK local time. La Liga times are Spanish local time.
Verified 23 Sep 2026 by matching the first 2026/27 matches against football-data.co.uk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fp.ingest.football_data_csv import CURRENT_SEASON, FIRST_SEASON, season_code
from fp.ingest.http import fetch

SOURCE = "openfootball"
BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
LEAGUES = {"en.1": "Europe/London", "es.1": "Europe/Madrid"}  # file code -> local time zone


def download(code: str, start_year: int) -> Path:
    folder = f"{start_year}-{(start_year + 1) % 100:02d}"
    return fetch(
        f"{BASE_URL}/{folder}/{code}.json",
        SOURCE,
        f"{code}_{season_code(start_year)}.json",
        refresh=start_year == CURRENT_SEASON,
    )


def read(path: Path, code: str) -> pd.DataFrame:
    """One row per match, with kickoff converted to UTC where a time is given.

    Leagues set kickoff times a few weeks ahead. Until then the time is blank,
    time_confirmed is False, and kickoff_utc is empty.
    """
    matches = pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["matches"])
    if "time" not in matches:
        matches["time"] = None
    matches["time_confirmed"] = matches["time"].notna() & (matches["time"] != "")
    local = pd.to_datetime(
        matches["date"] + " " + matches["time"].where(matches["time_confirmed"], "00:00"),
        format="%Y-%m-%d %H:%M",
    )
    utc = local.dt.tz_localize(LEAGUES[code]).dt.tz_convert("UTC")
    matches["kickoff_utc"] = utc.where(matches["time_confirmed"])

    # Scores come as {"ft": [h, a], "ht": [...]}, or as a bare [h, a] when no
    # half-time score was recorded, or are missing for unplayed matches.
    if "score" not in matches:
        matches["score"] = None
    full_time = matches["score"].map(lambda s: s.get("ft") if isinstance(s, dict) else s)
    played = full_time.map(lambda s: isinstance(s, list) and len(s) == 2)
    matches["home_goals"] = full_time.where(played).map(lambda s: s[0], na_action="ignore")
    matches["away_goals"] = full_time.where(played).map(lambda s: s[1], na_action="ignore")
    matches[["home_goals", "away_goals"]] = matches[["home_goals", "away_goals"]].astype("Int64")
    return matches


def download_all() -> dict[tuple[str, int], Path]:
    return {
        (code, year): download(code, year)
        for year in range(FIRST_SEASON, CURRENT_SEASON + 1)
        for code in LEAGUES
    }
