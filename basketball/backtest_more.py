"""Basketball phase B5 backtest: the ACB, the LBA and the ABA, with the B1 models, grids and
checks (data/audit/preregistration_basketball_b5_2026_11.md).

    uv run python basketball/more_leagues.py          # the games table first
    uv run python basketball/backtest_more.py tune    # settings from the tuning season only
    uv run python basketball/backtest_more.py test    # the test seasons, scored once

Writes data/basketball/b5_settings.json (tune) and data/basketball/b5_results.json (test).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

import backtest as b1  # noqa: E402
from models import EloSettings, PointsSettings, elo_ratings  # noqa: E402
from more_leagues import GAMES  # noqa: E402

from fp import ROOT  # noqa: E402

SETTINGS = ROOT / "data" / "basketball" / "b5_settings.json"
RESULTS = ROOT / "data" / "basketball" / "b5_results.json"
ROLES = {lg: {"warmup": [2022], "tuning": [2023], "test": [2024, 2025]}
         for lg in ("ACB", "LBA", "ABA")}


def tune() -> dict:
    out = {}
    for league, roles in ROLES.items():
        out[league] = b1.tune_league(league, roles, GAMES)
        pts = out[league]["points"]
        if league == "ACB":  # the only one with quarter scores
            out[league]["regulation"] = b1.tune_regulation(
                league, PointsSettings(pts["half_life"], pts["penalty"]), roles, GAMES)
        print(league, {k: v for k, v in out[league].items() if k in ("games", "elo", "points")})
    return out


def cold_start(st: dict) -> dict:
    """ACB: home-win chances on 2026/27 games from Wikipedia-only ratings (2025/26 on, as the
    daily run) against ratings with the API-Basketball seasons too."""
    g = pd.read_parquet(GAMES)
    g = g[(g["league"] == "ACB") & g["played"] & ~g["left_out"]].sort_values(["date", "game_id"])
    g = g.assign(home_pts=g["home_pts"].astype(float), away_pts=g["away_pts"].astype(float))
    e = st["elo"]
    s = EloSettings(e["k"], e["home"], e["carry"], e["mov"])
    now = g[g["season"] == 2026]
    diffs = []
    for day, part in now.groupby("date"):
        before = g[g["date"] < day]
        full = elo_ratings(before, s, season=2026)
        wiki = elo_ratings(before[before["season"] >= 2025], s, season=2026)
        for r in part.itertuples():
            pf = 1 / (1 + 10 ** (-(full.get(r.home_id, 1500) + e["home"]
                                   - full.get(r.away_id, 1500)) / 400))
            pw = 1 / (1 + 10 ** (-(wiki.get(r.home_id, 1500) + e["home"]
                                   - wiki.get(r.away_id, 1500)) / 400))
            diffs.append(abs(pf - pw))
    d = np.array(diffs)
    return {"games": int(len(d)), "mean_abs_diff": float(d.mean()) if len(d) else None,
            "max_abs_diff": float(d.max()) if len(d) else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Basketball B5 backtest")
    parser.add_argument("stage", choices=["tune", "test"])
    args = parser.parse_args(argv)
    if args.stage == "tune":
        SETTINGS.write_text(json.dumps(tune(), indent=1) + "\n", encoding="utf-8")
        print(f"written {SETTINGS.relative_to(ROOT)}")
        return 0
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    results = {lg: b1.test_league(lg, settings[lg], ROLES[lg], GAMES) for lg in ROLES}
    results["ACB"]["cold_start"] = cold_start(settings["ACB"])
    RESULTS.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for league, r in results.items():
        print(league, "games", r["test_games"], "decision:", r["decision"])
        c = r["checks"]
        print("  W1", {k: round(v, 4) for k, v in c["W1"].items() if isinstance(v, float)},
              "K1", round(c["K1"]["slope"], 3), "H1",
              {k: round(v, 3) for k, v in c["H1"].items() if isinstance(v, float)},
              "T1", {k: round(v, 3) for k, v in c["T1"].items() if isinstance(v, float)},
              "K2", {k: round(v, 3) for k, v in c["K2"].items() if isinstance(v, float)})
        print("  accuracy", c["L"]["accuracy"], "favourite", r["favourite_hits"])
    print("ACB cold start:", results["ACB"]["cold_start"])
    print(f"written {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
