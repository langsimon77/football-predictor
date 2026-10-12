"""football-data.org API v4, free plan: fixtures for PL, PD, and the Champions League.

Free plan facts [V: football-data.org/pricing, 23 Sep 2026]: 10 calls a minute,
fixtures, scores and tables only, no referees or cards. Used for Champions League
dates (rest days), as a cross-check on the openfootball calendar, and since
12 Oct 2026 for fast final scores (fp.ingest.results_feed).

The token comes from FOOTBALL_DATA_ORG_TOKEN (see fp.config). Never log it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from fp import leagues
from fp.config import MissingSecretError, secret
from fp.ingest.football_data_csv import CURRENT_SEASON
from fp.ingest.http import fetch

SOURCE = "football_data_org"
BASE_URL = "https://api.football-data.org/v4"
COMPETITIONS = {"PL": "EPL", "PD": "LaLiga", "CL": "UCL"}
# Probed in CI only, so the mapping tests can check their club names.
TRIAL_COMPETITIONS = {lg.fdorg: lg.code for lg in leagues.TRIAL}


def download_matches(code: str, season: int = CURRENT_SEASON, refresh: bool = True) -> Path:
    return fetch(
        f"{BASE_URL}/competitions/{code}/matches?season={season}",
        SOURCE,
        f"{code}_{season}.json",
        refresh=refresh,
        headers={"X-Auth-Token": secret("FOOTBALL_DATA_ORG_TOKEN")},
    )


def _goals(score: dict | None, part: str, side: str) -> float:
    value = ((score or {}).get(part) or {}).get(side)
    return float(value) if value is not None else float("nan")


def read_matches(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        {
            "fdorg_id": m["id"],
            "competition": data["competition"]["code"],
            "kickoff_utc": pd.Timestamp(m["utcDate"]),
            "status": m["status"],
            "home_name": m["homeTeam"]["name"],
            "away_name": m["awayTeam"]["name"],
            "home_goals": _goals(m.get("score"), "fullTime", "home"),
            "away_goals": _goals(m.get("score"), "fullTime", "away"),
            "ht_home_goals": _goals(m.get("score"), "halfTime", "home"),
            "ht_away_goals": _goals(m.get("score"), "halfTime", "away"),
            "last_updated": m.get("lastUpdated"),
        }
        for m in data["matches"]
    ]
    columns = ["fdorg_id", "competition", "kickoff_utc", "status", "home_name", "away_name",
               "home_goals", "away_goals", "ht_home_goals", "ht_away_goals", "last_updated"]
    return pd.DataFrame(rows, columns=columns)


def probe() -> int:
    """Check the API from wherever this runs. Prints no secrets."""
    try:
        secret("FOOTBALL_DATA_ORG_TOKEN")
    except MissingSecretError:
        print("football-data.org: no token set; skipping probe")
        return 0
    for code in [*COMPETITIONS, *TRIAL_COMPETITIONS]:
        try:
            frame = read_matches(download_matches(code))
        except Exception as error:  # report every failure, keep going
            print(f"football-data.org {code}: FAILED ({type(error).__name__}: {error})")
            continue
        names = sorted(set(frame["home_name"]) | set(frame["away_name"]))
        print(f"football-data.org {code}: {len(frame)} matches, {len(names)} teams")
        if code != "CL":
            print("  team names:", "; ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(probe())
