"""As-of features for the corners and cards models (spec S5.5, PRD item 7).

Every value is what was knowable at the match's lock time, never later:
- Rolling team averages (shots, corners, fouls, yellows): exponentially weighted
  over the team's previous matches, updated only when each result became known.
- Elo gap at lock time: a stand-in for "expected goal supremacy" and "match
  closeness". Taking it from a model fitted later would leak future results.
- League table at lock time, for the late-season importance flag.
- Derby flag from data/manual/derbies.csv.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from fp import ROOT
from fp.models import elo
from fp.models.priors import season_teams
from fp.validate.leakage import check_features, lock_time

DERBIES_CSV = ROOT / "data" / "manual" / "derbies.csv"
HALFLIFE_MATCHES = 8  # recent form: a match 8 games ago counts half as much
LATE_SEASON_PLAYED = 28  # 10 or fewer games left
RACE_POINTS = 3
DROP_PLACE = 18  # first relegation place in a 20-team league

ROLLING = {  # feature name -> (home column, away column), from the team's point of view
    "shots_for": ("home_shots", "away_shots"),
    "shots_against": ("away_shots", "home_shots"),
    "corners_for": ("home_corners", "away_corners"),
    "corners_against": ("away_corners", "home_corners"),
    "fouls": ("home_fouls", "away_fouls"),
    "yellows": ("home_yellows", "away_yellows"),
}


def team_rows(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match, from that team's point of view."""
    parts = []
    for side, other in (("home", "away"), ("away", "home")):
        part = pd.DataFrame({
            "match_id": matches["match_id"], "league": matches["league"],
            "season": matches["season"], "team": matches[f"{side}_id"],
            "opponent": matches[f"{other}_id"], "is_home": side == "home",
            "kickoff_utc": matches["kickoff_utc"],
            "result_available_utc": matches["result_available_utc"],
        })
        for name, (h, a) in ROLLING.items():
            part[name] = (matches[h] if side == "home" else matches[a]).astype(float)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def rolling_state(matches: pd.DataFrame) -> pd.DataFrame:
    """Each team's exponentially weighted averages after each of its matches,
    stamped with the time that match's result became known."""
    rows = team_rows(matches).sort_values(["team", "result_available_utc"])
    state = rows[["team", "result_available_utc"]].copy()
    for name in ROLLING:
        state[f"ewm_{name}"] = rows.groupby("team")[name].transform(
            lambda s: s.ewm(halflife=HALFLIFE_MATCHES, min_periods=1).mean())
    return state.sort_values("result_available_utc")


def rolling_at(targets: pd.DataFrame, state: pd.DataFrame, team_col: str,
               prefix: str) -> pd.DataFrame:
    """Latest rolling averages for targets[team_col] known at targets['lock_utc']."""
    left = targets[["match_id", team_col, "lock_utc"]].rename(columns={team_col: "team"})
    left = left.sort_values("lock_utc")
    merged = pd.merge_asof(left, state, left_on="lock_utc", right_on="result_available_utc",
                           by="team", direction="backward", allow_exact_matches=True)
    cols = [c for c in state.columns if c.startswith("ewm_")]
    out = merged[["match_id", *cols, "result_available_utc"]].rename(
        columns={**{c: f"{prefix}{c[4:]}" for c in cols},
                 "result_available_utc": f"{prefix}source_utc"})
    return out.set_index("match_id")


def elo_gap_at_lock(matches: pd.DataFrame, league: str) -> pd.Series:
    """Home Elo minus away Elo, plus home edge, as it stood at each match's lock."""
    lg = matches[matches["league"] == league].copy()
    lg["lock_utc"] = lock_time(lg["kickoff_utc"])
    tracker = elo.EloTracker(lg, season_teams(matches, league))
    gaps = {}
    for lock, group in lg.sort_values("lock_utc").groupby("lock_utc", sort=True):
        tracker.advance_to(cast(pd.Timestamp, lock))
        tracker.ensure_season(int(group["season"].iloc[0]))
        for r in group.itertuples():
            gaps[r.match_id] = tracker.gap(str(r.home_id), str(r.away_id))
    return pd.Series(gaps, name="elo_gap")


def derby_pairs() -> set[frozenset[str]]:
    table = pd.read_csv(DERBIES_CSV)
    return {frozenset((a, b)) for a, b in zip(table["team_a"], table["team_b"], strict=True)}


def standings_at(season_matches: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """League table from results known at as_of: points, goal difference, games played."""
    known = season_matches[season_matches["result_available_utc"] <= as_of]
    rows = []
    for h, a, hg, ag in zip(known["home_id"], known["away_id"],
                            known["home_goals"].astype(int), known["away_goals"].astype(int),
                            strict=True):
        hp, ap = (3, 0) if hg > ag else (1, 1) if hg == ag else (0, 3)
        rows.append((h, hp, hg - ag))
        rows.append((a, ap, ag - hg))
    teams = sorted(set(season_matches["home_id"]))
    table = pd.DataFrame(rows, columns=["team", "points", "gd"])
    agg = table.groupby("team").agg(points=("points", "sum"), gd=("gd", "sum"),
                                    played=("points", "size"))
    agg = agg.reindex(teams, fill_value=0).sort_values(["points", "gd"], ascending=False)
    agg["position"] = np.arange(1, len(agg) + 1)
    return agg


def importance_at_lock(matches: pd.DataFrame, league: str) -> pd.Series:
    """1 when, late in the season, either club is within 3 points of the title or of
    the relegation line in the table as it stood at lock time."""
    lg = matches[matches["league"] == league].copy()
    lg["lock_utc"] = lock_time(lg["kickoff_utc"])
    flags = {}
    for (season, lock), group in lg.groupby(["season", "lock_utc"], sort=True):
        table = standings_at(lg[lg["season"] == season], cast(pd.Timestamp, lock))
        top = table["points"].iloc[0]
        line = table["points"].iloc[DROP_PLACE - 2]  # 17th: the last safe place
        for r in group.itertuples():
            important = False
            for team in (r.home_id, r.away_id):
                row = table.loc[team]
                if row["played"] < LATE_SEASON_PLAYED:
                    continue
                title = top - row["points"] <= RACE_POINTS
                drop = abs(row["points"] - line) <= RACE_POINTS
                important = important or title or drop
            flags[r.match_id] = int(important)
    return pd.Series(flags, name="important")


def match_features(matches: pd.DataFrame) -> pd.DataFrame:
    """Per-match features for every top-flight match, all as of its lock time."""
    frame = matches[["match_id", "league", "season", "home_id", "away_id",
                     "kickoff_utc"]].copy()
    frame["lock_utc"] = lock_time(frame["kickoff_utc"])
    state = rolling_state(matches)
    frame = frame.join(rolling_at(frame, state, "home_id", "home_"), on="match_id")
    frame = frame.join(rolling_at(frame, state, "away_id", "away_"), on="match_id")
    gaps = pd.concat([elo_gap_at_lock(matches, lg) for lg in ("EPL", "LaLiga")])
    imp = pd.concat([importance_at_lock(matches, lg) for lg in ("EPL", "LaLiga")])
    frame["elo_gap"] = frame["match_id"].map(gaps)
    frame["important"] = frame["match_id"].map(imp).fillna(0).astype(int)
    pairs = derby_pairs()
    frame["derby"] = [int(frozenset((h, a)) in pairs)
                      for h, a in zip(frame["home_id"], frame["away_id"], strict=True)]
    # Leakage check (spec S4): the newest result behind any rolling average must be
    # known at lock time. Elo and the table are built by advancing only to lock time.
    frame["as_of_utc"] = frame["lock_utc"]
    frame["source_max_utc"] = frame[["home_source_utc", "away_source_utc"]].max(axis=1)
    frame["source_max_utc"] = frame["source_max_utc"].fillna(frame["lock_utc"])
    check_features(frame)
    return frame
