"""Drift monitor (spec S5.6 step 5, with PRD item 11's fix).

For each market, the published model is compared with a simple benchmark on the
same matches (paired), so match-to-match noise cancels:

| Market | Published forecast | Benchmark |
|---|---|---|
| Home, draw, away | dc_bayes_v1 (RPS) | Elo (RPS) |
| Over 2.5 goals | dc_bayes_v1 (log loss) | league base rate at lock |
| Over 9.5 corners | corners_total_poisson_v1 (log loss) | league base rate at lock |
| Over 4.5 yellows | cards_nb_v1 (log loss) | league base rate at lock |

The backtest test seasons give the normal gap. Over the last four gameweeks, if the
live gap is worse than normal by a margin unlikely to be chance (one-sided test,
Holm-corrected across the four markets, 5% level), the market is flagged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast

import numpy as np
import pandas as pd
from scipy.stats import norm

from fp.evaluate import metrics
from fp.validate.leakage import known_as_of

BASE_WINDOW_DAYS = 1100
ROUNDS = 4
MIN_MATCHES = 30
LEVEL = 0.05
MARKETS = {  # name: (primary column, benchmark column, outcome column, score)
    "1x2": (("p_home", "p_draw", "p_away"), ("elo_home", "elo_draw", "elo_away"), "outcome",
            "rps"),
    "over_2_5": ("p_over_2_5", "base_over_2_5", "goals_over_2_5", "log_loss"),
    "corners_over_9_5": ("p_corners_over_9_5", "base_corners_over_9_5", "corners_over_9_5",
                         "log_loss"),
    "yellows_over_4_5": ("p_yellows_over_4_5", "base_yellows_over_4_5", "yellows_over_4_5",
                         "log_loss"),
}


def base_rates(matches: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """League base rates known at each row's lock: home, draw, away shares and the
    share of matches over each line, from the previous 1,100 days."""
    out = []
    for key, group in frame.groupby(["league", "lock_utc"]):
        league, lock_key = cast(tuple, key)
        lock = cast(pd.Timestamp, lock_key)
        known = known_as_of(matches[matches["league"] == league], lock)
        recent = known[known["kickoff_utc"] >= lock - pd.Timedelta(days=BASE_WINDOW_DAYS)]
        y = metrics.outcome_1x2(recent["home_goals"].to_numpy(), recent["away_goals"].to_numpy())
        share = np.bincount(y, minlength=3) / max(len(y), 1)
        goals = recent["home_goals"] + recent["away_goals"]
        corners = recent["home_corners"] + recent["away_corners"]
        yellows = recent["home_yellows"] + recent["away_yellows"]
        out.append(pd.DataFrame({
            "match_id": group["match_id"].to_numpy(), "base_home": share[0],
            "base_draw": share[1], "base_away": share[2],
            "base_over_2_5": float((goals > 2.5).mean()),
            "base_corners_over_9_5": float((corners.dropna() > 9.5).mean()),
            "base_yellows_over_4_5": float((yellows.dropna() > 4.5).mean())}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def add_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["outcome"] = metrics.outcome_1x2(frame["home_goals"].to_numpy(dtype=int),
                                           frame["away_goals"].to_numpy(dtype=int))
    frame["goals_over_2_5"] = (frame["home_goals"] + frame["away_goals"]) > 2.5
    corners = frame["home_corners"] + frame["away_corners"]
    yellows = frame["home_yellows"] + frame["away_yellows"]
    frame["corners_over_9_5"] = (corners > 9.5).where(corners.notna())
    frame["yellows_over_4_5"] = (yellows > 4.5).where(yellows.notna())
    return frame


def paired_gap(frame: pd.DataFrame, market: str) -> np.ndarray:
    """Per match: published score minus benchmark score (lower is better, so a
    positive value means the published model did worse on that match)."""
    primary, bench, outcome, score = MARKETS[market]
    if score == "rps":
        cols_p, cols_b = list(primary), list(bench)
        f = frame.dropna(subset=cols_p + cols_b + [outcome])
        y = f[outcome].to_numpy(dtype=int)
        return (metrics.rps(f[cols_p].to_numpy(float), y)
                - metrics.rps(f[cols_b].to_numpy(float), y))
    f = frame.dropna(subset=[primary, bench, outcome])
    happened = f[outcome].astype(bool).to_numpy()
    return (metrics.binary_log_loss(f[primary].to_numpy(float), happened)
            - metrics.binary_log_loss(f[bench].to_numpy(float), happened))


@dataclass
class DriftResult:
    market: str
    n: int
    live_gap: float
    baseline_gap: float
    z: float
    p_value: float
    p_holm: float
    flagged: bool
    note: str


def check(live: pd.DataFrame, baseline: pd.DataFrame) -> list[DriftResult]:
    """live and baseline: one row per scored match with the columns in MARKETS."""
    rows = []
    for market in MARKETS:
        base = paired_gap(baseline, market)
        gap = paired_gap(live, market)
        if len(gap) < MIN_MATCHES:
            rows.append(DriftResult(market, len(gap), float(np.mean(gap)) if len(gap) else np.nan,
                                    float(base.mean()), np.nan, np.nan, np.nan, False,
                                    f"fewer than {MIN_MATCHES} scored matches"))
            continue
        se = float(np.std(gap, ddof=1) / np.sqrt(len(gap)))
        z = (float(gap.mean()) - float(base.mean())) / se if se > 0 else 0.0
        rows.append(DriftResult(market, len(gap), float(gap.mean()), float(base.mean()), z,
                                float(1 - norm.cdf(z)), np.nan, False, ""))
    tested = sorted((r for r in rows if np.isfinite(r.p_value)), key=lambda r: r.p_value)
    m = len(tested)
    running = 0.0
    for i, r in enumerate(tested):  # Holm step-down, monotone adjusted p-values
        running = max(running, min(1.0, (m - i) * r.p_value))
        r.p_holm = running
        r.flagged = running < LEVEL
        r.note = "worse than the backtest norm" if r.flagged else "within the backtest norm"
    return rows


def last_rounds(frame: pd.DataFrame, rounds: int = ROUNDS) -> pd.DataFrame:
    """Each league's last `rounds` gameweeks with scored matches."""
    parts = []
    for _, g in frame.groupby("league"):
        order = g.groupby("round")["kickoff_utc"].max().sort_values().index[-rounds:]
        parts.append(g[g["round"].isin(order)])
    return pd.concat(parts) if parts else frame.iloc[0:0]


def as_records(results: list[DriftResult]) -> list[dict]:
    return [{k: (None if isinstance(v, float) and not np.isfinite(v) else v)
             for k, v in asdict(r).items()} for r in results]
