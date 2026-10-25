"""Basketball phase B2 backtest, in two stages, as pre-registered in
data/audit/preregistration_basketball_b2_2026_10.md.

    DYLD_LIBRARY_PATH=.venv/lib/python3.12/site-packages/sklearn/.dylibs \\
        .venv/bin/python basketball/backtest_b2.py tune     # tuning seasons only
    ... basketball/backtest_b2.py test                      # the test seasons, scored once

(On macOS, XGBoost needs scikit-learn's OpenMP library on that path; GitHub needs nothing.)

`tune` never reads a test-season game. It writes data/basketball/b2_settings.json, committed
before `test` runs. `test` compares each challenger with the B1 model for each market (Elo for
the winner and handicap, the points model for the total) with checks A1, A2, A3 and L, and
reports the NBL width idea (section 5), writing data/basketball/b2_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np
import pandas as pd
from backtest import ROLES, league_games
from challengers import GRIDS, MARKETS, ML, NAMES, ml_predict, score_predict, targets
from features import build_features
from models import (
    EloSettings,
    PointsSettings,
    Spread,
    bootstrap_mean,
    calibration_slope,
    crps_normal,
    elo_run,
    inside_90,
    log_loss,
    p_above,
    points_run,
)

from fp import ROOT

B1 = ROOT / "data" / "basketball" / "b1_settings.json"
SETTINGS = ROOT / "data" / "basketball" / "b2_settings.json"
RESULTS = ROOT / "data" / "basketball" / "b2_results.json"
SEED = 2027
LEVEL = 0.99
SEASONS_NEEDED = {"EuroLeague": 3, "NBL": 2}  # A2: of 4 and of 3 test seasons
ACCURACY_ALARM = 0.78
SLOPE_RANGE = (0.8, 1.2)
COVERAGE_RANGE = (0.86, 0.94)
WIDTH_DAYS, WIDTH_MIN_GAMES = 365, 100


def forecasts(cid: str, market: str, p: dict, g: pd.DataFrame, X: pd.DataFrame,
              rows: np.ndarray, b1: dict) -> np.ndarray:
    """A challenger's value for each of `rows`: the home-win chance (winner) or the expected
    margin or total. C6 and C7 give expected scores; their winner chance needs a width, so it
    is returned as the expected margin and turned into a chance by the caller."""
    if cid in ML:
        return ml_predict(cid, market, p, g, X, rows)[rows]
    s = score_predict(cid, p, g, b1)
    mh, ma = s["m_home"].to_numpy()[rows], s["m_away"].to_numpy()[rows]
    return mh + ma if market == "total" else mh - ma


def score_rows(cid: str, market: str, value: np.ndarray, y: np.ndarray, sd: float) -> np.ndarray:
    """Per-game scores: winner log loss, or the bell curve's CRPS."""
    if market == "winner":
        p = value if cid in ML else p_above(value, sd)
        return log_loss(p, y)
    return crps_normal(y, value, sd)


# ---------------------------------------------------------------- stage 1: tune


def tune_league(league: str, b1: dict) -> dict:
    roles = ROLES[league]
    g = league_games(league, min(roles["test"]) - 1)  # never a test-season game
    X = build_features(g, b1)
    rows = np.flatnonzero(g["season"].isin(roles["tuning"]).to_numpy())
    ys = targets(g)
    margin_y = ys["margin"][rows]
    out: dict = {}
    for cid in GRIDS:
        out[cid] = {}
        trials = {m: [] for m in MARKETS}
        for p in GRIDS[cid]:
            for market in MARKETS:
                v = forecasts(cid, market, p, g, X, rows, b1)
                if market == "winner" and cid not in ML:
                    sd = float(np.std(margin_y - v))  # the margin bell curve's width
                elif market == "winner":
                    sd = float("nan")
                else:
                    sd = float(np.std(ys[market][rows] - v))
                s = float(score_rows(cid, market, v, ys[market][rows], sd).mean())
                trials[market].append((s, p, sd))
        for market in MARKETS:
            best = min(trials[market], key=lambda t: t[0])  # ties: first in grid order
            out[cid][market] = {"params": best[1], "tuning_score": best[0], "sd": best[2],
                                "grid": [{"score": round(t[0], 5), **t[1]} for t in trials[market]]}
        print(league, cid, {m: (out[cid][m]["params"], round(out[cid][m]["tuning_score"], 4))
                            for m in MARKETS}, flush=True)
    return {"tuning_games": int(len(rows)), "challengers": out}


# ---------------------------------------------------------------- stage 2: test


def check(diff: np.ndarray, day: np.ndarray, seasons: np.ndarray, league: str) -> dict:
    mean, lo, hi = bootstrap_mean(diff, day, seed=SEED, level=LEVEL)
    _, lo95, hi95 = bootstrap_mean(diff, day, seed=SEED)
    per = {str(int(s)): float(diff[seasons == s].mean()) for s in sorted(set(seasons))}
    better = sum(v < 0 for v in per.values())
    return {"mean": mean, "low99": lo, "high99": hi, "low95": lo95, "high95": hi95,
            "by_season": per, "seasons_better": better,
            "A1": hi < 0, "A2": better >= SEASONS_NEEDED[league]}


def rolling_width(errors: np.ndarray, ordinal: np.ndarray, fallback: float) -> np.ndarray:
    """Section 5: the width for each game from the model's own errors in the previous 365 days
    (earlier days only), or the tuning width with fewer than 100 such games."""
    out = np.full(len(errors), fallback)
    for i, day in enumerate(ordinal):
        past = (ordinal < day) & (ordinal >= day - WIDTH_DAYS) & np.isfinite(errors)
        if past.sum() >= WIDTH_MIN_GAMES:
            out[i] = float(np.std(errors[past]))
    return out


def width_idea(league: str, b1: dict) -> dict:
    """Reported, not judged on the test seasons; the 2026/27 games so far are listed for the
    prospective check (judged once 100 NBL games are played)."""
    g = league_games(league, 2026)
    e, pt = b1["elo"], b1["points"]
    elo = elo_run(g, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))
    pts = points_run(g, PointsSettings(pt["half_life"], pt["penalty"]))
    spread = Spread(pt["sd_home"], pt["sd_away"], pt["rho"])
    ys = targets(g)
    ordinal = np.array([d.toordinal() for d in g["date"]])
    seasons = g["season"].to_numpy()
    out = {}
    for market, value, fixed in (
            ("margin", e["margin_scale_b"] * elo["elo_diff"].to_numpy(), e["margin_sd"]),
            ("total", (pts["m_home"] + pts["m_away"]).to_numpy(), spread.sd_total)):
        err = ys[market] - value
        sd = rolling_width(err, ordinal, fixed)
        res = {}
        for label, mask in (("test seasons", np.isin(seasons, ROLES[league]["test"])),
                            ("2026/27 so far", seasons == 2026)):
            if not mask.any():
                continue
            yv, vv = ys[market][mask], value[mask]
            res[label] = {
                "games": int(mask.sum()),
                "inside_90_fixed": float(inside_90(yv, vv, fixed).mean()),
                "inside_90_rolling": float(inside_90(yv, vv, sd[mask]).mean()),
                "crps_fixed": float(crps_normal(yv, vv, fixed).mean()),
                "crps_rolling": float(crps_normal(yv, vv, sd[mask]).mean()),
            }
        out[market] = res
    return out


def test_league(league: str, b1: dict, st: dict) -> dict:
    roles = ROLES[league]
    g = league_games(league, max(roles["test"]))
    X = build_features(g, b1)
    rows = np.flatnonzero(g["season"].isin(roles["test"]).to_numpy())
    day = g["date"].astype(str).to_numpy()[rows]
    seasons = g["season"].to_numpy()[rows]
    ys = {m: v[rows] for m, v in targets(g).items()}

    e, pt = b1["elo"], b1["points"]
    elo = elo_run(g, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))
    pts = points_run(g, PointsSettings(pt["half_life"], pt["penalty"]))
    spread = Spread(pt["sd_home"], pt["sd_away"], pt["rho"])
    base = {
        "winner": log_loss(elo["p_home"].to_numpy()[rows], ys["winner"]),
        "margin": crps_normal(ys["margin"], e["margin_scale_b"] * elo["elo_diff"].to_numpy()[rows],
                              e["margin_sd"]),
        "total": crps_normal(ys["total"], (pts["m_home"] + pts["m_away"]).to_numpy()[rows],
                             spread.sd_total),
    }
    out: dict = {"test_games": int(len(rows)),
                 "baseline_means": {m: float(v.mean()) for m, v in base.items()},
                 "challengers": {}}
    for cid in GRIDS:
        out["challengers"][cid] = {"name": NAMES[cid]}
        for market in MARKETS:
            chosen = st["challengers"][cid][market]
            t = time.time()
            v = forecasts(cid, market, chosen["params"], g, X, rows, b1)
            scores = score_rows(cid, market, v, ys[market], chosen["sd"])
            res = check(scores - base[market], day, seasons, league)
            if market == "winner":
                p = v if cid in ML else p_above(v, chosen["sd"])
                slope = calibration_slope(p, ys["winner"])
                accuracy = float(((p > 0.5) == (ys["winner"] == 1)).mean())
                res.update({"slope": slope, "A3": SLOPE_RANGE[0] <= slope <= SLOPE_RANGE[1],
                            "accuracy": accuracy, "L_alarm": accuracy > ACCURACY_ALARM})
            else:
                cover = float(inside_90(ys[market], v, chosen["sd"]).mean())
                res.update({"inside_90": cover,
                            "A3": COVERAGE_RANGE[0] <= cover <= COVERAGE_RANGE[1]})
            res["mean_score"] = float(scores.mean())
            res["passes"] = bool(res["A1"] and res["A2"] and res["A3"])
            out["challengers"][cid][market] = res
            print(league, cid, market, f"{res['mean']:+.4f} ({res['low99']:+.4f} to "
                  f"{res['high99']:+.4f}) passes={res['passes']} {time.time() - t:.0f}s",
                  flush=True)
    out["elo_accuracy"] = float(((elo["p_home"].to_numpy()[rows] > 0.5)
                                 == (ys["winner"] == 1)).mean())
    out["width_idea"] = width_idea(league, b1)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Basketball B2 backtest")
    parser.add_argument("stage", choices=["tune", "test"])
    args = parser.parse_args(argv)
    b1 = json.loads(B1.read_text(encoding="utf-8"))
    if args.stage == "tune":
        out = {league: tune_league(league, b1[league]) for league in ROLES}
        SETTINGS.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"written {SETTINGS.relative_to(ROOT)}")
        return 0
    st = json.loads(SETTINGS.read_text(encoding="utf-8"))
    results = {league: test_league(league, b1[league], st[league]) for league in ROLES}
    RESULTS.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print(f"written {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
