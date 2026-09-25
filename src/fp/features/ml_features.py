"""Feature table for the machine-learning challengers (spec S5.5, Phase 4).

One row per match, every column as of that match's lock time:
- Fast Dixon-Coles outputs (home, draw, away probabilities; expected goals),
  refitted at every lock. They stand in for "Dixon-Coles posterior means":
  the Bayesian model has walk-forward outputs only from 2021/22, while the
  challengers train from 2017/18.
- Elo gap at lock.
- Rolling team averages (shots, corners, fouls, yellows) from fp.features.rolling.
- Schedule: rest days since each club's previous league match and league matches
  in the 14 days before lock. League games only: free cup and European fixture
  data is not available for past seasons (PRD item 17).
- Season context: league games played this season, promoted flag, derby, late-season
  importance.
Excluded on purpose: bookmaker odds (spec S5.5), team news (PRD item 6), manager
tenure (no verified history yet, PRD item 18).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fp.evaluate import backtest as bt
from fp.features import rolling
from fp.models.priors import season_teams
from fp.validate.leakage import check_features

FIRST_SEASON = 2017  # 2016/17 is burn-in for Elo and the rolling averages
REST_CAP_DAYS = 14

FEATURES = [
    "dc_home", "dc_draw", "dc_away", "dc_exp_goals_home", "dc_exp_goals_away", "elo_gap",
    "home_shots_for", "home_shots_against", "away_shots_for", "away_shots_against",
    "home_corners_for", "home_corners_against", "away_corners_for", "away_corners_against",
    "home_fouls", "away_fouls", "home_yellows", "away_yellows",
    "rest_home", "rest_away", "busy_home", "busy_away", "played_home", "played_away",
    "promoted_home", "promoted_away", "derby", "important",
]


def schedule(matches: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Rest days, recent load, and games played, from kickoffs strictly before lock."""
    games = pd.concat([
        matches[["match_id", "season", "kickoff_utc"]].assign(team=matches["home_id"]),
        matches[["match_id", "season", "kickoff_utc"]].assign(team=matches["away_id"]),
    ]).sort_values("kickoff_utc")
    by_team = {t: g for t, g in games.groupby("team")}
    out = {}
    cols = zip(frame["match_id"], frame["season"], frame["home_id"], frame["away_id"],
               frame["kickoff_utc"], frame["lock_utc"], strict=True)
    for match_id, season, home_id, away_id, kickoff, lock in cols:
        row: dict[str, float] = {}
        for side, team in (("home", home_id), ("away", away_id)):
            g = by_team.get(team)
            before = g[g["kickoff_utc"] < lock] if g is not None else games.iloc[0:0]
            last = before["kickoff_utc"].max() if len(before) else pd.NaT
            rest = (kickoff - last).total_seconds() / 86400 if pd.notna(last) else np.nan
            row[f"rest_{side}"] = min(rest, REST_CAP_DAYS) if np.isfinite(rest) else REST_CAP_DAYS
            row[f"busy_{side}"] = int((before["kickoff_utc"] >= lock - pd.Timedelta(days=14)).sum())
            row[f"played_{side}"] = int((before["season"] == season).sum())
        out[match_id] = row
    return pd.DataFrame.from_dict(out, orient="index")


def promoted_teams(matches: pd.DataFrame) -> dict[tuple[str, int], int]:
    """1 for a club in its first top-flight season after promotion, else 0."""
    promoted: dict[tuple[str, int], int] = {}
    for league in ("EPL", "LaLiga"):
        tbs = season_teams(matches, league)
        for season, teams in tbs.items():
            for team in teams:
                promoted[(team, season)] = int(team not in tbs.get(season - 1, teams))
    return promoted


def build(matches: pd.DataFrame) -> pd.DataFrame:
    frame = rolling.match_features(matches)
    frame = frame[frame["season"] >= FIRST_SEASON].copy()
    fast = bt.run(matches, bt.Config(seasons=sorted(frame["season"].unique())))
    fast = fast.set_index("match_id")
    for col in ("dc_home", "dc_draw", "dc_away", "dc_exp_goals_home", "dc_exp_goals_away"):
        frame[col] = frame["match_id"].map(fast[col])
    frame = frame.join(schedule(matches, frame), on="match_id")
    promoted = promoted_teams(matches)
    frame["promoted_home"] = [promoted.get((t, s), 0)
                              for t, s in zip(frame["home_id"], frame["season"], strict=True)]
    frame["promoted_away"] = [promoted.get((t, s), 0)
                              for t, s in zip(frame["away_id"], frame["season"], strict=True)]
    m = matches.set_index("match_id")
    frame["outcome"] = np.where(frame["match_id"].map(m["home_goals"]) >
                                frame["match_id"].map(m["away_goals"]), 0,
                                np.where(frame["match_id"].map(m["home_goals"]) ==
                                         frame["match_id"].map(m["away_goals"]), 1, 2))
    frame["result_available_utc"] = frame["match_id"].map(m["result_available_utc"])
    # The fast Dixon-Coles columns come from fits made at lock time; the rolling
    # columns carry their own source times. check_features covers the latter.
    check_features(frame)
    return frame.reset_index(drop=True)
