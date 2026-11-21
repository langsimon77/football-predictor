"""Fit the basketball winner tier cut for the tips (same rule as football tiers_v1).

Usage: python scripts/fit_basketball_tips.py

Elo forecasts are walk-forward by design: each game's chance uses only earlier games.
Settings are the approved ones (data/basketball/b1_settings.json for EuroLeague and NBL,
b5_settings.json for ACB), the leagues whose winner forecasts passed their tests and are
live. High starts at the top quarter of the favourite's chance in the tuning seasons
(pooled over the three leagues); Low below the bottom third. Tested on the test seasons.
Writes data/tips/basketball_tiers.json and prints the test table.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "basketball"))

import backtest as b1  # noqa: E402
import backtest_more as b5  # noqa: E402
from models import EloSettings, elo_run  # noqa: E402
from more_leagues import GAMES as GAMES_MORE  # noqa: E402

HIGH_Q, LOW_Q = 0.75, 1 / 3   # as fp.ensemble.tiers


def walk_forward(league: str, roles: dict, settings: dict, path) -> pd.DataFrame:
    g = b1.league_games(league, max(roles["test"]), path=path)
    e = settings["elo"]
    p = elo_run(g, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))["p_home"].to_numpy()
    fav = np.maximum(p, 1 - p)
    won = np.where(p >= 0.5, g["home_pts"] > g["away_pts"], g["away_pts"] > g["home_pts"])
    role = np.where(g["season"].isin(roles["tuning"]), "tuning",
                    np.where(g["season"].isin(roles["test"]), "test", "other"))
    return pd.DataFrame({"league": league, "season": g["season"].to_numpy(), "fav": fav,
                         "won": won.astype(bool), "role": role})


def wilson(k: int, n: int) -> tuple[float, float]:
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def main() -> None:
    s1 = json.loads((ROOT / "data/basketball/b1_settings.json").read_text())
    s5 = json.loads((ROOT / "data/basketball/b5_settings.json").read_text())
    frames = [walk_forward(lg, b1.ROLES[lg], s1[lg],
                           None) for lg in ("EuroLeague", "NBL")]
    frames.append(walk_forward("ACB", b5.ROLES["ACB"], s5["ACB"], GAMES_MORE))
    df = pd.concat(frames, ignore_index=True)
    tune = df[df.role == "tuning"]
    high = round(float(np.quantile(tune.fav, HIGH_Q)), 2)
    low = round(float(np.quantile(tune.fav, LOW_Q)), 2)
    test = df[df.role == "test"].copy()
    test["tier"] = np.where(test.fav >= high - 1e-9, "High",
                            np.where(test.fav < low - 1e-9, "Low", "Medium"))
    rows = []
    for (lg, tier), g in list(test.groupby(["league", "tier"])) + list(
            test.assign(league="All").groupby(["league", "tier"])):
        k, n = int(g.won.sum()), len(g)
        lo, hi = wilson(k, n)
        rows.append({"league": lg, "tier": tier, "games": n, "promised": round(g.fav.mean(), 3),
                     "won": round(k / n, 3), "won_low": round(lo, 3), "won_high": round(hi, 3)})
    out = {"rule": "bb_tiers_v1", "high": high, "low": low,
           "basis": "Elo walk-forward favourite chance, tuning seasons pooled: EuroLeague "
                    "2017/18 to 2021/22, NBL 2017/18 and 2022/23, ACB 2023/24",
           "tuning_games": int(len(tune)), "test": rows}
    (ROOT / "data/tips/basketball_tiers.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("high", "low", "tuning_games")}))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
