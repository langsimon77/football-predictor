"""One table of walk-forward forecasts and benchmarks for 2021/22 to 2025/26.

Used by the weekly run: the drift monitor's normal gaps (test seasons) and the
stack re-weight's backtest pool (all seasons). Writes
data/backtests/baselines_2021_2025.parquet.

    uv run python scripts/backtest_baselines.py
"""

from __future__ import annotations

import sys

import pandas as pd

from fp import ROOT
from fp.evaluate import backtest as bt
from fp.evaluate import drift
from fp.ingest.matches import PROCESSED

BACKTESTS = ROOT / "data" / "backtests"
OUT = BACKTESTS / "baselines_2021_2025.parquet"
SEASONS = [2021, 2022, 2023, 2024, 2025]


def main() -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    base = bt.run(matches, bt.Config(seasons=SEASONS))
    frame = base[["match_id", "league", "season", "as_of_utc", "elo_home", "elo_draw", "elo_away",
                  "dc_home", "dc_draw", "dc_away"]].rename(columns={"as_of_utc": "lock_utc"})
    m = matches.set_index("match_id")
    for col in ("kickoff_utc", "home_goals", "away_goals", "home_corners", "away_corners",
                "home_yellows", "away_yellows"):
        frame[col] = frame["match_id"].map(m[col])
    bdc = pd.read_parquet(BACKTESTS / "dc_bayes_v1_walkforward_2021_2025.parquet").set_index(
        "match_id")
    for ours, theirs in (("p_home", "bdc_home"), ("p_draw", "bdc_draw"), ("p_away", "bdc_away"),
                         ("p_over_2_5", "bdc_over_2_5")):
        frame[ours] = frame["match_id"].map(bdc[theirs])
    corners = pd.read_parquet(BACKTESTS / "corners_total_poisson_walkforward_2021_2025.parquet")
    cards = pd.read_parquet(BACKTESTS / "cards_nb_walkforward_2021_2025.parquet")
    frame["p_corners_over_9_5"] = frame["match_id"].map(corners.set_index("match_id")["p_over_9_5"])
    frame["p_yellows_over_4_5"] = frame["match_id"].map(cards.set_index("match_id")["p_over_4_5"])
    ch = pd.read_parquet(BACKTESTS / "challengers_walkforward_2021_2025.parquet")
    for name, g in ch.groupby("model"):
        g = g.set_index("match_id")
        for k in ("home", "draw", "away"):
            frame[f"{name}_{k}"] = frame["match_id"].map(g[f"p_{k}"])
    frame = frame.merge(drift.base_rates(matches, frame), on="match_id", how="left")
    frame = drift.add_outcomes(frame)
    frame.to_parquet(OUT, index=False)
    test = frame[frame["season"] >= 2023]
    print(f"{len(frame)} matches; normal gaps on the test seasons:")
    for market in drift.MARKETS:
        gap = drift.paired_gap(test, market)
        print(f"  {market}: {gap.mean():+.4f} over {len(gap)} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
