"""Club histories for the sequence models (N2 LSTM, N3 Transformer).

For every forecast, each club's last matches are read oldest first, with eleven numbers per
match (Amendment 1, item 3): goals, shots, shots on target and corners, each for and against;
home or away; rest days before it (at most 14); the opponent's Elo before it. Only matches
whose result was known at the forecast's lock are read, so nothing leaks from the future.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fp import leagues
from fp.models import elo
from fp.models.priors import season_teams

SEQ_COLS = ["goals_for", "goals_against", "shots_for", "shots_against", "sot_for",
            "sot_against", "corners_for", "corners_against", "is_home", "rest_days", "opp_elo"]
MAX_LENGTH = 10  # the grid reads 5 or 10 matches; 5 is the last five of these 10
REST_CAP_DAYS = 14.0
STATS = {"goals": ("home_goals", "away_goals"), "shots": ("home_shots", "away_shots"),
         "sot": ("home_sot", "away_sot"), "corners": ("home_corners", "away_corners")}


def pre_match_elo(matches: pd.DataFrame) -> pd.DataFrame:
    """Each club's Elo rating just before each match, from results known by kickoff."""
    out = []
    for league in leagues.codes_in(matches["league"]):
        lg = matches[matches["league"] == league].sort_values("kickoff_utc")
        tracker = elo.EloTracker(lg, season_teams(matches, league))
        cols = zip(lg["match_id"], lg["kickoff_utc"], lg["season"], lg["home_id"],
                   lg["away_id"], strict=True)
        for match_id, kickoff, season, home, away in cols:
            tracker.advance_to(pd.Timestamp(kickoff))
            tracker.ensure_season(int(season))
            out.append((str(match_id), tracker.ratings[str(home)], tracker.ratings[str(away)]))
    return pd.DataFrame(out, columns=["match_id", "home_elo", "away_elo"]).set_index("match_id")


def club_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per club per match, from that club's side, in the order results became known."""
    ratings = pre_match_elo(matches)
    m = matches.reset_index(drop=True)
    parts = []
    for side, other in (("home", "away"), ("away", "home")):
        part = pd.DataFrame({
            "team": m[f"{side}_id"],
            "kickoff_utc": pd.to_datetime(m["kickoff_utc"], utc=True),
            "result_available_utc": pd.to_datetime(m["result_available_utc"], utc=True),
            "is_home": float(side == "home"),
            "opp_elo": m["match_id"].map(ratings[f"{other}_elo"]).astype(float),
        })
        for name, (h, a) in STATS.items():
            mine, theirs = (h, a) if side == "home" else (a, h)
            part[f"{name}_for"] = pd.to_numeric(m[mine], errors="coerce").astype(float)
            part[f"{name}_against"] = pd.to_numeric(m[theirs], errors="coerce").astype(float)
        parts.append(part)
    rows = pd.concat(parts, ignore_index=True).sort_values(["team", "kickoff_utc"])
    gap = rows.groupby("team")["kickoff_utc"].diff().dt.total_seconds() / 86400
    rows["rest_days"] = gap.fillna(REST_CAP_DAYS).clip(upper=REST_CAP_DAYS)
    return rows.sort_values(["team", "result_available_utc"]).reset_index(drop=True)


def histories(targets: pd.DataFrame, clubs: pd.DataFrame,
              length: int = MAX_LENGTH) -> tuple[np.ndarray, np.ndarray]:
    """Arrays (n, 2, length, 11) and a mask (n, 2, length): for each target row (home club
    first), its last `length` known matches, most recent last; empty slots are zero, mask 0."""
    n = len(targets)
    values = np.zeros((n, 2, length, len(SEQ_COLS)), dtype=np.float32)
    mask = np.zeros((n, 2, length), dtype=np.float32)
    by_team = {t: (g["result_available_utc"].dt.tz_convert(None).to_numpy(
                       dtype="datetime64[ns]"), g[SEQ_COLS].to_numpy(dtype=np.float32))
               for t, g in clubs.groupby("team")}
    locks = pd.to_datetime(targets["lock_utc"], utc=True).dt.tz_convert(None).to_numpy(
        dtype="datetime64[ns]")
    for i, (home, away, lock) in enumerate(zip(targets["home_id"], targets["away_id"], locks,
                                               strict=True)):
        for side, team in enumerate((home, away)):
            if team not in by_team:
                continue
            known, vals = by_team[team]
            end = int(np.searchsorted(known, lock, side="right"))  # results known at the lock
            take = vals[max(0, end - length):end]
            if len(take):
                values[i, side, length - len(take):] = take
                mask[i, side, length - len(take):] = 1.0
    return np.nan_to_num(values), mask
