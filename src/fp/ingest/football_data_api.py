"""football-data.org API v4, free plan: fixtures for PL, PD, and the Champions League.

Free plan facts [V: football-data.org/pricing, 23 Sep 2026]: 10 calls a minute,
fixtures and tables only, no referees or cards. We use it for Champions League
dates (rest days) and as a cross-check on the openfootball calendar.

The token comes from FOOTBALL_DATA_ORG_TOKEN (see fp.config). Never log it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from fp.config import MissingSecretError, secret
from fp.ingest.football_data_csv import CURRENT_SEASON
from fp.ingest.http import fetch

SOURCE = "football_data_org"
BASE_URL = "https://api.football-data.org/v4"
COMPETITIONS = {"PL": "EPL", "PD": "LaLiga", "CL": "UCL"}


def download_matches(code: str, season: int = CURRENT_SEASON) -> Path:
    return fetch(
        f"{BASE_URL}/competitions/{code}/matches?season={season}",
        SOURCE,
        f"{code}_{season}.json",
        headers={"X-Auth-Token": secret("FOOTBALL_DATA_ORG_TOKEN")},
    )


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
        }
        for m in data["matches"]
    ]
    return pd.DataFrame(rows)


def probe() -> int:
    """Check the API from wherever this runs. Prints no secrets."""
    try:
        secret("FOOTBALL_DATA_ORG_TOKEN")
    except MissingSecretError:
        print("football-data.org: no token set; skipping probe")
        return 0
    for code in COMPETITIONS:
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
