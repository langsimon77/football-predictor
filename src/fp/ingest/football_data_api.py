"""football-data.org API v4, free plan: fixtures for PL, PD, and the Champions League.

Free plan facts [V: football-data.org/pricing, 23 Sep 2026]: 10 calls a minute,
fixtures, scores and tables only, no referees or cards. Used for Champions League
dates (rest days), as a cross-check on the openfootball calendar, since
12 Oct 2026 for fast final scores (fp.ingest.results_feed), and since 24 Oct 2026
for kickoff times that openfootball has not published yet (fp.ingest.matches).

The token comes from FOOTBALL_DATA_ORG_TOKEN (see fp.config). Never log it.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

from fp import leagues
from fp.config import MissingSecretError, secret
from fp.ingest.football_data_csv import CURRENT_SEASON
from fp.ingest.http import fetch
from fp.teams import UnknownTeamError, to_team_id

log = logging.getLogger(__name__)

SOURCE = "football_data_org"
BASE_URL = "https://api.football-data.org/v4"
COMPETITIONS = {"PL": "EPL", "PD": "LaLiga", "CL": "UCL"}
# Probed in CI only, so the mapping tests can check their club names.
TRIAL_COMPETITIONS = {lg.fdorg: lg.code for lg in leagues.TRIAL}
# Statuses whose utcDate is a real kickoff time. A SCHEDULED match has its date
# but a 00:00 placeholder time (all 260 La Liga SCHEDULED rows on 13 Oct 2026);
# POSTPONED, SUSPENDED and CANCELLED keep a date that no longer holds.
TIME_SET = ("TIMED", "IN_PLAY", "PAUSED", "FINISHED")


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
            "stage": m.get("stage"),
            "matchday": m.get("matchday"),
            # After extra time, fullTime includes it; regularTime holds the 90 minutes.
            "regular_home_goals": _goals(m.get("score"), "regularTime", "home"),
            "regular_away_goals": _goals(m.get("score"), "regularTime", "away"),
        }
        for m in data["matches"]
    ]
    columns = ["fdorg_id", "competition", "kickoff_utc", "status", "home_name", "away_name",
               "home_goals", "away_goals", "ht_home_goals", "ht_away_goals", "last_updated",
               "stage", "matchday", "regular_home_goals", "regular_away_goals"]
    return pd.DataFrame(rows, columns=columns)


def download_all(group: tuple[leagues.League, ...] = leagues.LIVE,
                 season: int = CURRENT_SEASON) -> None:
    """Today's season file for each league. The calendar build reads its kickoff
    times, and the fast results step then reuses the same file (no extra calls).
    Without a token, or when the API cannot be reached, the run goes on with
    openfootball's times and any copy cached earlier."""
    for lg in group:
        try:
            download_matches(lg.fdorg, season)
        except MissingSecretError:
            log.info("football-data.org: no token, so kickoff times from openfootball only")
            return
        except (requests.Timeout, requests.ConnectionError) as error:
            log.warning("football-data.org unreachable (%s); kickoff times from openfootball "
                        "and the last cached copy", type(error).__name__)
            return  # the other leagues would time out too
        except Exception as error:  # e.g. an HTTP error for one competition
            log.warning("football-data.org %s: download failed (%s)", lg.fdorg,
                        type(error).__name__)


def set_kickoffs(path: Path) -> pd.DataFrame:
    """Matches whose kickoff time is set (TIME_SET), keyed by our team IDs.
    A club with no alias is logged and skipped."""
    frame = read_matches(path)
    frame = frame[frame["status"].isin(TIME_SET)]
    rows = []
    for r in frame.itertuples():
        try:
            rows.append((to_team_id(str(r.home_name), SOURCE),
                         to_team_id(str(r.away_name), SOURCE), r.kickoff_utc))
        except UnknownTeamError:
            log.warning("football-data.org: unknown club in %s v %s", r.home_name, r.away_name)
    out = pd.DataFrame(rows, columns=["home_id", "away_id", "kickoff_utc"])
    out["kickoff_utc"] = pd.to_datetime(out["kickoff_utc"], utc=True)
    return out


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
        print("  team names:", "; ".join(names))  # CL too: the Champions League model maps them
    return 0


if __name__ == "__main__":
    sys.exit(probe())
