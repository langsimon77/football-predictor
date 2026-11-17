"""Basketball upgrade step 3 (Lang: "Approved all", 17 Nov 2026): player availability.

No league offers a free, machine-readable injury feed whose terms allow automated use
(EuroLeague official data is barred by B0-D4; the NBL's list and basketball.com.au's tracker
are news pages with unchecked terms). So availability is typed into
data/manual/basketball_availability.csv, one row per missing player, and every live run reads it.

Columns: league, date (game date, YYYY-MM-DD), club (as on the Model Lab card), player,
role (star | starter | rotation), status (out | doubtful), source (link or "Lang").

Effect on the forecast, all [A] until tested (pre-registration B6, section 6):
- points a missing player costs his team's margin: star 3.0, starter 1.5, rotation 0.5;
- doubtful counts half; a team's total effect is capped at 6.0 points;
- half of each team's loss comes off the expected total points.
Only the shadow forecast uses it; the main ledger is unchanged until the test passes.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fp import ROOT

PATH = ROOT / "data" / "manual" / "basketball_availability.csv"
COLUMNS = ["league", "date", "club", "player", "role", "status", "source"]
ROLE_POINTS = {"star": 3.0, "starter": 1.5, "rotation": 0.5}
STATUS_WEIGHT = {"out": 1.0, "doubtful": 0.5}
TEAM_CAP = 6.0
TOTAL_SHARE = 0.5


def load(path: Path = PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    bad_role = ~df["role"].str.lower().isin(ROLE_POINTS)
    bad_status = ~df["status"].str.lower().isin(STATUS_WEIGHT)
    if (bad_role | bad_status).any():
        rows = (df.index[bad_role | bad_status] + 2).tolist()
        raise ValueError(f"{path.name}: unknown role or status on line(s) {rows}")
    return df


def team_loss(av: pd.DataFrame, league: str, date: str, club: str) -> float:
    m = av[(av["league"] == league) & (av["date"] == str(date))
           & (av["club"].str.casefold() == str(club).casefold())]
    pts = sum(ROLE_POINTS[r.lower()] * STATUS_WEIGHT[s.lower()]
              for r, s in zip(m["role"], m["status"], strict=True))
    return min(pts, TEAM_CAP)


def adjust(league: str, date: str, home: str, away: str,
           av: pd.DataFrame) -> tuple[float, float, int]:
    """(margin shift for the home side, total shift, players counted)."""
    h, a = team_loss(av, league, date, home), team_loss(av, league, date, away)
    n = int(((av["league"] == league) & (av["date"] == str(date))
             & av["club"].str.casefold().isin([home.casefold(), away.casefold()])).sum())
    return a - h, -TOTAL_SHARE * (h + a), n
