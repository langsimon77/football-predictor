"""Basketball B6: adaptive range widths, as pre-registered in
data/audit/preregistration_basketball_b6_width_2026_11.md.

    uv run python basketball/backtest_width.py tune   # choice from the B1 tuning seasons only
    uv run python basketball/backtest_width.py seen   # B1 test seasons: descriptive, already seen

`tune` writes data/basketball/b6_settings.json (committed before `seen` runs);
`seen` writes data/basketball/b6_seen.json. Confirmation is on live 2026/27 games (shadow).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest import ROLES, interval, league_games  # noqa: E402
from backtest import SETTINGS as B1_SETTINGS
from models import EloSettings, PointsSettings, Spread, elo_run, points_run  # noqa: E402
from width import GRID, Width, crps, inside_90, rolling_sd  # noqa: E402

from fp import ROOT  # noqa: E402

B6_SETTINGS = ROOT / "data" / "basketball" / "b6_settings.json"
B6_SEEN = ROOT / "data" / "basketball" / "b6_seen.json"
MARKETS = ("handicap", "total")


def errors_and_means(g, st: dict) -> dict:
    """Per market: expected value, model error and the B1 (W0) width, for every game."""
    e, pt = st["elo"], st["points"]
    diff = elo_run(g, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))["elo_diff"].to_numpy()
    m_mean = e["margin_scale_b"] * diff
    pred = points_run(g, PointsSettings(pt["half_life"], pt["penalty"]))
    t_mean = (pred["m_home"] + pred["m_away"]).to_numpy()
    margin = (g["home_pts"] - g["away_pts"]).to_numpy(float)
    total = (g["home_pts"] + g["away_pts"]).to_numpy(float)
    sd_total = Spread(pt["sd_home"], pt["sd_away"], pt["rho"]).sd_total
    return {"handicap": (margin, m_mean, margin - m_mean, float(e["margin_sd"])),
            "total": (total, t_mean, total - t_mean, float(sd_total))}


def widths(err: np.ndarray, day: np.ndarray, w0: float, w: Width) -> np.ndarray:
    if w.method == "W0":
        return np.full(len(err), w0)
    return rolling_sd(err, day, w.window, start_sd=w0)


def tune() -> dict:
    b1 = json.loads(B1_SETTINGS.read_text())
    out = {}
    for league, roles in ROLES.items():
        g = league_games(league, min(roles["test"]) - 1)  # never a test-season game
        tune_mask = g["season"].isin(roles["tuning"]).to_numpy()
        day = g["date"].astype(str).to_numpy()
        out[league] = {}
        for market, (x, mu, err, w0) in errors_and_means(g, b1[league]).items():
            ok = tune_mask & ~np.isnan(mu)
            scores = []
            for w in GRID:
                sd = widths(err, day, w0, w)
                scores.append((float(crps(x[ok], mu[ok], sd[ok], w).mean()), w))
            best = min(scores, key=lambda t: t[0])  # ties: first in grid order (W0 first)
            out[league][market] = {
                "chosen": {"method": best[1].method, "window": best[1].window, "df": best[1].df,
                           "label": best[1].label()},
                "w0_sd": w0,
                "tuning_games": int(ok.sum()),
                "tuning_crps": {w.label(): round(s, 4) for s, w in scores},
            }
    B6_SETTINGS.write_text(json.dumps(out, indent=2) + "\n")
    return out


def chosen_width(league: str, market: str) -> Width:
    c = json.loads(B6_SETTINGS.read_text())[league][market]["chosen"]
    return Width(c["method"], c["window"], c["df"])


def seen() -> dict:
    b1 = json.loads(B1_SETTINGS.read_text())
    out = {"note": "B1 test seasons, already scored in B1 and seen: descriptive only."}
    for league, roles in ROLES.items():
        g = league_games(league, max(roles["test"]))
        test = g["season"].isin(roles["test"]).to_numpy()
        day = g["date"].astype(str).to_numpy()
        out[league] = {}
        for market, (x, mu, err, w0) in errors_and_means(g, b1[league]).items():
            w = chosen_width(league, market)
            sd_c = widths(err, day, w0, w)
            base = Width("W0")
            c_new = crps(x[test], mu[test], sd_c[test], w)
            c_old = crps(x[test], mu[test], np.full(test.sum(), w0), base)
            cover = float(inside_90(x[test], mu[test], sd_c[test], w).mean())
            cover0 = float(inside_90(x[test], mu[test], np.full(test.sum(), w0), base).mean())
            out[league][market] = {
                "chosen": w.label(), "games": int(test.sum()),
                "coverage_90": {"chosen": round(cover, 4), "W0": round(cover0, 4)},
                "coverage_pass_86_94": 0.86 <= cover <= 0.94,
                "crps": {"chosen": round(float(c_new.mean()), 4),
                         "W0": round(float(c_old.mean()), 4)},
                "crps_chosen_minus_W0": interval(c_new - c_old, day[test]),
                "mean_width": {"chosen": round(float(sd_c[test].mean()), 3), "W0": round(w0, 3)},
            }
    B6_SEEN.write_text(json.dumps(out, indent=2) + "\n")
    return out


def current_sd(league: str, market: str, x, mu, w0: float, day) -> tuple[Width, float]:
    """Width for the next game day, from all earlier errors (live shadow use)."""
    w = chosen_width(league, market)
    err = np.asarray(x, float) - np.asarray(mu, float)
    if w.method == "W0":
        return w, w0
    known = err[~np.isnan(err)]
    if len(known) < 60:
        return w, w0
    tail = known[-w.window:]
    return w, float(np.sqrt((tail ** 2).mean()))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage == "tune":
        print(json.dumps(tune(), indent=2))
    elif stage == "seen":
        print(json.dumps(seen(), indent=2))
    else:
        sys.exit(__doc__)
