"""Basketball phase B1 backtest, in two stages, as pre-registered in
data/audit/preregistration_basketball_b1_2026_10.md.

    uv run python basketball/backtest.py tune   # settings from the tuning seasons only
    uv run python basketball/backtest.py test   # the test seasons, scored once

`tune` never reads a test-season game: it uses the seasons before the first test season.
It writes data/basketball/b1_settings.json, which is committed before `test` runs.
`test` reads those settings, walks forward through the test seasons and applies the checks
(W1, W2, H1, H2, T1, K1, K2, L), writing data/basketball/b1_results.json.

Input: data/processed/basketball/games.parquet from basketball/data.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from itertools import product

import numpy as np
import pandas as pd
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
    naive_total_mean,
    p_above,
    points_run,
    spread_from,
)

from data import GAMES
from fp import ROOT

SETTINGS = ROOT / "data" / "basketball" / "b1_settings.json"
RESULTS = ROOT / "data" / "basketball" / "b1_results.json"

# Plan, section 4 (seasons by their starting year: 2017 is 2017/18).
ROLES = {
    "EuroLeague": {"warmup": [2016], "tuning": [2017, 2018, 2019, 2020, 2021],
                   "test": [2022, 2023, 2024, 2025]},
    "NBL": {"warmup": [2016], "tuning": [2017, 2022], "test": [2023, 2024, 2025]},
}
# Plan, section 5.
ELO_GRID = [EloSettings(k, h, c, m) for k, h, c, m in product(
    (10, 15, 20, 25, 30), (50, 75, 100, 125), (0.5, 0.75, 1.0), (True, False))]
POINTS_GRID = [PointsSettings(hl, pen) for hl, pen in product(
    (30, 60, 120, 240, 480), (0.3, 1, 3, 10, 30))]
# Plan, section 6.
ACCURACY_ALARM = 0.78
SLOPE_RANGE = (0.8, 1.2)
COVERAGE_RANGE = (0.86, 0.94)


def season_name(year: int) -> str:
    return f"{year}/{(year + 1) % 100:02d}"


def league_games(league: str, last_season: int, regulation: bool = False) -> pd.DataFrame:
    """Played, kept, regular-season games up to `last_season`, sorted by date. With
    `regulation`, scores are the sum of the four quarters (games with quarters only)."""
    g = pd.read_parquet(GAMES)
    g = g[(g["league"] == league) & g["played"] & ~g["left_out"] & (g["season"] <= last_season)]
    if regulation:
        g = g[g["home_reg"].notna() & g["away_reg"].notna()].copy()
        g["home_pts"], g["away_pts"] = g["home_reg"], g["away_reg"]
    g = g.sort_values(["date", "game_id"]).reset_index(drop=True)
    g["home_pts"] = g["home_pts"].astype(float)
    g["away_pts"] = g["away_pts"].astype(float)
    return g


# ---------------------------------------------------------------- stage 1: tune


def tune_league(league: str) -> dict:
    roles = ROLES[league]
    g = league_games(league, min(roles["test"]) - 1)  # never a test-season game
    tune = g["season"].isin(roles["tuning"]).to_numpy()
    y = (g["home_pts"] > g["away_pts"]).to_numpy(float)
    margin = (g["home_pts"] - g["away_pts"]).to_numpy()
    total = (g["home_pts"] + g["away_pts"]).to_numpy()

    elo_scores = []
    for s in ELO_GRID:
        p = elo_run(g, s)["p_home"].to_numpy()
        elo_scores.append((float(log_loss(p[tune], y[tune]).mean()), s))
    best_elo_ll, elo = min(elo_scores, key=lambda t: t[0])  # ties: first in grid order
    diff = elo_run(g, elo)["elo_diff"].to_numpy()
    b = float((diff[tune] * margin[tune]).sum() / (diff[tune] ** 2).sum())
    elo_sd = float(np.sqrt(((margin[tune] - b * diff[tune]) ** 2).mean()))

    pts_scores = []
    for s in POINTS_GRID:
        pred = points_run(g, s)
        spread = spread_from(g[tune], pred[tune])
        mh, ma = pred["m_home"].to_numpy(), pred["m_away"].to_numpy()
        cm = crps_normal(margin[tune], (mh - ma)[tune], spread.sd_margin).mean()
        ct = crps_normal(total[tune], (mh + ma)[tune], spread.sd_total).mean()
        pts_scores.append((float(cm + ct), float(cm), float(ct), s, spread))
    best = min(pts_scores, key=lambda t: t[0])

    naive_mean = naive_total_mean(g)
    return {
        "games": {"tuning": int(tune.sum()), "before_test": int(len(g))},
        "elo": {**asdict(elo), "tuning_log_loss": best_elo_ll, "margin_scale_b": b,
                "margin_sd": elo_sd},
        "points": {**asdict(best[3]), "tuning_margin_crps": best[1], "tuning_total_crps": best[2],
                   **asdict(best[4])},
        "naive": {"home_win_rate": float(y[tune].mean()),
                  "margin_mean": float(margin[tune].mean()),
                  "margin_sd": float(margin[tune].std()),
                  "total_sd": float(np.nanstd(total[tune] - naive_mean[tune]))},
        "elo_grid_top5": [{"log_loss": round(ll, 5), **asdict(s)}
                          for ll, s in sorted(elo_scores, key=lambda t: t[0])[:5]],
        "points_grid": [{"crps_sum": round(t[0], 4), **asdict(t[3])} for t in pts_scores],
    }


def tune_regulation(league: str, points: PointsSettings) -> dict:
    """Widths and naive values for the regulation-time version (reported, not judged)."""
    roles = ROLES[league]
    g = league_games(league, min(roles["test"]) - 1, regulation=True)
    tune = g["season"].isin(roles["tuning"]).to_numpy()
    pred = points_run(g, points)
    spread = spread_from(g[tune], pred[tune])
    margin = (g["home_pts"] - g["away_pts"]).to_numpy()
    total = (g["home_pts"] + g["away_pts"]).to_numpy()
    decided = tune & (margin != 0)
    naive_mean = naive_total_mean(g)
    return {**asdict(spread),
            "naive": {"home_win_rate": float((margin[decided] > 0).mean()),
                      "margin_mean": float(margin[tune].mean()),
                      "margin_sd": float(margin[tune].std()),
                      "total_sd": float(np.nanstd(total[tune] - naive_mean[tune]))}}


# ---------------------------------------------------------------- stage 2: test


def interval(diff: np.ndarray, day: np.ndarray) -> dict:
    mean, lo, hi = bootstrap_mean(diff, day)
    return {"mean": mean, "low": lo, "high": hi}


def test_league(league: str, st: dict) -> dict:
    roles = ROLES[league]
    g = league_games(league, max(roles["test"]))
    test = g["season"].isin(roles["test"]).to_numpy()
    day = g["date"].astype(str).to_numpy()[test]
    y = (g["home_pts"] > g["away_pts"]).to_numpy(float)[test]
    margin = (g["home_pts"] - g["away_pts"]).to_numpy()[test]
    total = (g["home_pts"] + g["away_pts"]).to_numpy()[test]

    e = st["elo"]
    elo = elo_run(g, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))
    p_elo = elo["p_home"].to_numpy()[test]
    m_elo = e["margin_scale_b"] * elo["elo_diff"].to_numpy()[test]

    pt = st["points"]
    pred = points_run(g, PointsSettings(pt["half_life"], pt["penalty"]))
    spread = Spread(pt["sd_home"], pt["sd_away"], pt["rho"])
    m_pts = (pred["m_home"] - pred["m_away"]).to_numpy()[test]
    t_pts = (pred["m_home"] + pred["m_away"]).to_numpy()[test]
    p_pts = p_above(m_pts, spread.sd_margin)

    nv = st["naive"]
    p_naive = np.full(len(y), nv["home_win_rate"])
    t_naive = naive_total_mean(g)[test]

    ll = {"elo": log_loss(p_elo, y), "points": log_loss(p_pts, y), "naive": log_loss(p_naive, y)}
    cm = {"elo": crps_normal(margin, m_elo, e["margin_sd"]),
          "points": crps_normal(margin, m_pts, spread.sd_margin),
          "naive": crps_normal(margin, nv["margin_mean"], nv["margin_sd"])}
    ct = {"points": crps_normal(total, t_pts, spread.sd_total),
          "naive": crps_normal(total, t_naive, nv["total_sd"])}

    w2 = interval(ll["points"] - ll["elo"], day)
    winner_model = "points" if w2["high"] < 0 else "elo"
    w1 = interval(ll[winner_model] - ll["naive"], day)
    h2 = interval(cm["points"] - cm["elo"], day)
    margin_model = "points" if h2["high"] < 0 else "elo"
    h1 = interval(cm[margin_model] - cm["naive"], day)
    t1 = interval(ct["points"] - ct["naive"], day)
    p_chosen = {"elo": p_elo, "points": p_pts}[winner_model]
    slope = calibration_slope(p_chosen, y)
    m_chosen, sd_chosen = ((m_pts, spread.sd_margin) if margin_model == "points"
                           else (m_elo, e["margin_sd"]))
    cover_margin = float(inside_90(margin, m_chosen, sd_chosen).mean())
    cover_total = float(inside_90(total, t_pts, spread.sd_total).mean())
    accuracy = {k: float(((p > 0.5) == (y == 1)).mean())
                for k, p in (("elo", p_elo), ("points", p_pts), ("naive", p_naive))}

    checks = {
        "W1": {**w1, "pass": w1["high"] < 0, "model": winner_model},
        "W2": {**w2, "chosen": winner_model},
        "H1": {**h1, "pass": h1["high"] < 0, "model": margin_model},
        "H2": {**h2, "chosen": margin_model},
        "T1": {**t1, "pass": t1["high"] < 0},
        "K1": {"slope": slope, "pass": SLOPE_RANGE[0] <= slope <= SLOPE_RANGE[1]},
        "K2": {"margin": cover_margin, "total": cover_total,
               "pass_margin": COVERAGE_RANGE[0] <= cover_margin <= COVERAGE_RANGE[1],
               "pass_total": COVERAGE_RANGE[0] <= cover_total <= COVERAGE_RANGE[1]},
        "L": {"accuracy": accuracy, "alarm": max(accuracy.values()) > ACCURACY_ALARM},
    }
    k2 = checks["K2"]
    decision = {
        "winner": bool(checks["W1"]["pass"] and checks["K1"]["pass"]),
        "handicap": bool(checks["H1"]["pass"] and k2["pass_margin"]),
        "total_points": bool(checks["T1"]["pass"] and k2["pass_total"]),
    }
    seasons = g["season"].to_numpy()[test]
    by_season = {season_name(int(s)): {
        "games": int((seasons == s).sum()),
        "winner_log_loss": {k: float(v[seasons == s].mean()) for k, v in ll.items()},
        "margin_crps": {k: float(v[seasons == s].mean()) for k, v in cm.items()},
        "total_crps": {k: float(v[seasons == s].mean()) for k, v in ct.items()},
    } for s in sorted(set(seasons))}
    return {
        "test_games": int(test.sum()),
        "means": {"winner_log_loss": {k: float(v.mean()) for k, v in ll.items()},
                  "margin_crps": {k: float(v.mean()) for k, v in cm.items()},
                  "total_crps": {k: float(v.mean()) for k, v in ct.items()},
                  "margin_mean_abs_error": {"elo": float(np.abs(margin - m_elo).mean()),
                                            "points": float(np.abs(margin - m_pts).mean())},
                  "total_mean_abs_error": {"points": float(np.abs(total - t_pts).mean()),
                                           "naive": float(np.abs(total - t_naive).mean())},
                  "home_win_share": float(y.mean())},
        "checks": checks, "decision": decision, "by_season": by_season,
        "regulation_time": test_regulation(league, st),
    }


def test_regulation(league: str, st: dict) -> dict:
    """The points model on regulation-time scores (sum of the four quarters): reported, not
    judged. Ties after four quarters are left out of the winner score."""
    roles, rt = ROLES[league], st["regulation"]
    g = league_games(league, max(roles["test"]), regulation=True)
    test = g["season"].isin(roles["test"]).to_numpy()
    day = g["date"].astype(str).to_numpy()[test]
    pt = st["points"]
    pred = points_run(g, PointsSettings(pt["half_life"], pt["penalty"]))
    spread = Spread(rt["sd_home"], rt["sd_away"], rt["rho"])
    margin = (g["home_pts"] - g["away_pts"]).to_numpy()[test]
    total = (g["home_pts"] + g["away_pts"]).to_numpy()[test]
    m_pts = (pred["m_home"] - pred["m_away"]).to_numpy()[test]
    t_pts = (pred["m_home"] + pred["m_away"]).to_numpy()[test]
    nv = rt["naive"]
    decided = margin != 0
    yd = (margin[decided] > 0).astype(float)
    ll_p = log_loss(p_above(m_pts[decided], spread.sd_margin), yd)
    ll_n = log_loss(np.full(decided.sum(), nv["home_win_rate"]), yd)
    cm_p = crps_normal(margin, m_pts, spread.sd_margin)
    cm_n = crps_normal(margin, nv["margin_mean"], nv["margin_sd"])
    ct_p = crps_normal(total, t_pts, spread.sd_total)
    ct_n = crps_normal(total, naive_total_mean(g)[test], nv["total_sd"])
    return {"games": int(test.sum()), "tied_after_four_quarters": int((~decided).sum()),
            "winner_points_minus_naive": interval(ll_p - ll_n, day[decided]),
            "margin_points_minus_naive": interval(cm_p - cm_n, day),
            "total_points_minus_naive": interval(ct_p - ct_n, day),
            "coverage_margin": float(inside_90(margin, m_pts, spread.sd_margin).mean()),
            "coverage_total": float(inside_90(total, t_pts, spread.sd_total).mean())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Basketball B1 backtest")
    parser.add_argument("stage", choices=["tune", "test"])
    args = parser.parse_args(argv)
    if args.stage == "tune":
        out = {}
        for league in ROLES:
            out[league] = tune_league(league)
            pts = out[league]["points"]
            out[league]["regulation"] = tune_regulation(
                league, PointsSettings(pts["half_life"], pts["penalty"]))
            print(league, {k: v for k, v in out[league].items() if k in ("games", "elo", "points")})
        SETTINGS.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"written {SETTINGS.relative_to(ROOT)}")
        return 0
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    results = {league: test_league(league, settings[league]) for league in ROLES}
    RESULTS.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for league, r in results.items():
        print(league, "decision:", r["decision"])
        print("  checks:", json.dumps(r["checks"], default=float)[:900])
    print(f"written {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
