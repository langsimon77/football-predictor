"""Fast results (approved by Lang on 12 Oct 2026).

football-data.co.uk carries every statistic the models use (shots, corners, cards),
but it can lag days behind: on 12 Oct 2026 its 2026/27 files still ended on 20 Sep,
two days after a full round. Until its row arrives, a finished match's result
comes from, in this order:

1. Lang's own entry, data/manual/results_manual.csv (goals, and corners and cards
   if given);
2. the football-data.org API, matches marked FINISHED (goals only);
3. openfootball (goals only).

Such a score-only row feeds the goals models (the Bayesian model, the fast
Dixon-Coles model and Elo) and the scoring of locked forecasts. The corners and
cards models, and the machine-learning challengers, keep waiting for the full row,
because they need shots, fouls and corners history. When the full row arrives it
replaces the score-only row, and any difference with an earlier source is reported.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ingest import football_data_api as api
from fp.ingest.matches import RESULT_DELAY
from fp.teams import to_team_id

log = logging.getLogger(__name__)

MANUAL = ROOT / "data" / "manual" / "results_manual.csv"
GOALS = ["home_goals", "away_goals"]
STATS = ["home_corners", "away_corners", "home_yellows", "away_yellows", "home_reds",
         "away_reds"]
MANUAL_COLUMNS = ["match_id", *GOALS, *STATS, "entered_utc", "note"]
COMPETITIONS = {"PL": "EPL", "PD": "LaLiga"}
SOURCES = ("manual", "football_data_org", "openfootball")


def manual_scores(path: Path = MANUAL) -> pd.DataFrame:
    """Lang's entries. Rows without both goal numbers are ignored."""
    if not path.exists():
        return pd.DataFrame(columns=["match_id", *GOALS, *STATS, "source"])
    d = pd.read_csv(path, dtype={"match_id": str})
    d = d.dropna(subset=GOALS)
    for c in [*GOALS, *STATS]:
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d else np.nan
    d = d[(d[GOALS] >= 0).all(axis=1)]
    return d[["match_id", *GOALS, *STATS]].drop_duplicates("match_id", keep="last").assign(
        source="manual")


def api_scores(fixtures: pd.DataFrame, offline: bool = False,
               competitions: dict[str, str] = COMPETITIONS) -> pd.DataFrame:
    """Final scores of FINISHED matches (default: Premier League and La Liga)."""
    season = int(fixtures["season"].max())
    keyed = fixtures.set_index(["league", "home_id", "away_id"])["match_id"]
    rows = []
    for code, league in competitions.items():
        frame = api.read_matches(api.download_matches(code, season, refresh=not offline))
        frame = frame[(frame["status"] == "FINISHED") & frame["home_goals"].notna()]
        for r in frame.itertuples():
            try:
                h = to_team_id(str(r.home_name), api.SOURCE)
                a = to_team_id(str(r.away_name), api.SOURCE)
            except Exception:
                log.warning("football-data.org: unknown club in %s v %s", r.home_name,
                            r.away_name)
                continue
            mid = keyed.get((league, h, a))
            if mid is None:
                continue
            rows.append({"match_id": mid, "home_goals": r.home_goals, "away_goals": r.away_goals,
                         "ht_home_goals": r.ht_home_goals, "ht_away_goals": r.ht_away_goals})
    out = pd.DataFrame(rows, columns=["match_id", *GOALS, "ht_home_goals", "ht_away_goals"])
    return out.assign(source="football_data_org")


def openfootball_scores(fixtures: pd.DataFrame) -> pd.DataFrame:
    s = fixtures[fixtures["home_goals"].notna()]
    return s[["match_id", *GOALS]].assign(source="openfootball")


def collect(fixtures: pd.DataFrame, offline: bool = False,
            competitions: dict[str, str] = COMPETITIONS) -> list[pd.DataFrame]:
    """Every fast source, best first. A source that fails is skipped and logged."""
    out = [manual_scores()]
    try:
        out.append(api_scores(fixtures, offline, competitions))
    except Exception as error:  # the run goes on with the other sources
        log.warning("football-data.org scores unavailable (%s)", type(error).__name__)
    out.append(openfootball_scores(fixtures))
    return [f for f in out if len(f)]


def score_only_rows(matches: pd.DataFrame, fixtures: pd.DataFrame,
                    sources: list[pd.DataFrame]) -> pd.DataFrame:
    """Rows shaped like the matches table for finished matches it does not have yet.
    Statistics are empty unless Lang entered them. The result counts as known three
    hours after kickoff, the same rule as football-data.co.uk results."""
    have = set(matches["match_id"])
    best = (pd.concat(sources, ignore_index=True).drop_duplicates("match_id", keep="first")
            if sources else pd.DataFrame(columns=["match_id"]))
    best = best[~best["match_id"].isin(have)]
    fx = fixtures.set_index("match_id")
    best = best[best["match_id"].isin(fx.index)]
    if best.empty:
        return pd.DataFrame(columns=[*matches.columns, "result_source"])
    info = fx.loc[best["match_id"], ["league", "season", "home_id", "away_id", "kickoff_utc",
                                     "round"]].reset_index()
    rows = info.merge(best, on="match_id")
    rows = rows[rows["kickoff_utc"].notna()]
    rows["result_available_utc"] = rows["kickoff_utc"] + RESULT_DELAY
    rows["match_date"] = rows["kickoff_utc"].dt.tz_convert("Europe/London").dt.date
    rows["kickoff_source"] = "fixtures"
    rows["division"] = rows["league"].map({"EPL": "E0", "LaLiga": "SP1"})
    rows = rows.rename(columns={"source": "result_source"})
    out = rows.reindex(columns=[*matches.columns, "result_source"])
    for c in [*GOALS, *STATS]:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def with_scores(matches: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """The matches table plus score-only rows, for the goals models."""
    if extra.empty:
        return matches
    full = matches.assign(result_source="football_data_co_uk")
    for c in [*GOALS, *STATS]:  # the counts are nullable integers in the full table
        if c in full:
            full[c] = full[c].astype("Float64")
            extra[c] = extra[c].astype("Float64")
    return pd.concat([full, extra], ignore_index=True)


def cross_check(matches: pd.DataFrame, sources: list[pd.DataFrame]) -> list[str]:
    """Differences between the full football-data.co.uk row and earlier sources."""
    full = matches.set_index("match_id")
    out = []
    for src in sources:
        both = src[src["match_id"].isin(full.index)]
        for r in both.itertuples():
            for c in [*GOALS, *STATS]:
                mine = pd.to_numeric(getattr(r, c, np.nan), errors="coerce")
                theirs = pd.to_numeric(full.at[r.match_id, c], errors="coerce") \
                    if c in full else np.nan
                if pd.notna(mine) and pd.notna(theirs) and float(mine) != float(theirs):
                    out.append(f"{r.match_id}: {c} is {float(theirs):.0f} in football-data.co.uk "
                               f"but {float(mine):.0f} in {r.source}")
    return out


def still_missing(fixtures: pd.DataFrame, goal_matches: pd.DataFrame,
                  now: pd.Timestamp) -> list[str]:
    """Matches that kicked off more than three hours ago and have no result from any
    source yet. Normal for a few hours; worth a look if it lasts a day."""
    done = set(goal_matches["match_id"])
    past = fixtures[fixtures["kickoff_utc"].notna()
                    & (fixtures["kickoff_utc"] + RESULT_DELAY <= now)
                    & (fixtures["season"] == fixtures["season"].max())]
    return sorted(set(past["match_id"]) - done)
