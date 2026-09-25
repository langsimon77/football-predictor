"""Phase 4 report: stacked ensemble, calibration revisited, confidence tiers.

Inputs, all walk-forward predictions for 2021/22 to 2025/26:
- data/backtests/dc_bayes_v1_walkforward_2021_2025.parquet (primary model)
- data/backtests/challengers_walkforward_2021_2025.parquet (ordered logit,
  multinomial, Random Forest, XGBoost)
- data/backtests/{corners_total_poisson,cards_nb}_walkforward_2021_2025.parquet
- Elo, fast Dixon-Coles, and base rates, recomputed at every lock.
- Bookmaker odds: benchmark only.

Protocol: the tuning seasons (2021/22, 2022/23) set every weight, map, and cut
point. The test seasons (2023/24 to 2025/26) are scored once.

    uv run python scripts/backtest_phase4.py [--challengers PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fp import ROOT  # noqa: E402
from fp.ensemble import calibration as cal  # noqa: E402
from fp.ensemble import stacking, tiers  # noqa: E402
from fp.evaluate import backtest as bt  # noqa: E402
from fp.evaluate import metrics  # noqa: E402
from fp.features import ml_features  # noqa: E402
from fp.ingest.matches import PROCESSED  # noqa: E402
from fp.models import dixon_coles as dc  # noqa: E402

BACKTESTS = ROOT / "data" / "backtests"
TUNE, TEST = (2021, 2022), (2023, 2024, 2025)
OUTCOMES = ("home", "draw", "away")
LEAKAGE_ALARM = 0.60
OUT_MD = ROOT / "reports" / "backtest_phase4.md"
OUT_FIG = ROOT / "reports" / "figures" / "phase4_reliability.png"
OUT_STACK = ROOT / "data" / "stacking" / "stack_1x2.json"
OUT_CAL = ROOT / "data" / "calibration" / "stack_1x2.json"
OUT_TIERS = ROOT / "data" / "tiers" / "thresholds.json"
COUNT_MARKETS = {  # file stem, outcome columns, lines
    "corners": ("corners_total_poisson", ("home_corners", "away_corners"),
                (8.5, 9.5, 10.5, 11.5)),
    "cards": ("cards_nb", ("home_yellows", "away_yellows"), (3.5, 4.5, 5.5)),
}


# ---------------------------------------------------------------- helpers

def table(rows: list[dict] | pd.DataFrame) -> str:
    frame = pd.DataFrame(rows)
    head = "| " + " | ".join(map(str, frame.columns)) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                                       for v in r) + " |" for r in frame.itertuples(index=False))
    return head + "\n" + body


def probs(frame: pd.DataFrame, prefix: str) -> np.ndarray:
    return frame[[f"{prefix}_{k}" for k in OUTCOMES]].to_numpy(dtype=float)


def put(frame: pd.DataFrame, prefix: str, p: np.ndarray, rows: np.ndarray | None = None) -> None:
    cols = [f"{prefix}_{k}" for k in OUTCOMES]
    if rows is None:
        frame[cols] = p
    else:
        for c in cols:
            if c not in frame:
                frame[c] = np.nan
        frame.loc[rows, cols] = p


def group_ci(values: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval for a mean."""
    if len(values) == 0:
        return float("nan"), float("nan")
    return bt.paired_ci(np.asarray(values, dtype=float), n_boot=n_boot, seed=seed)


def gap_ci(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval for mean(a) minus mean(b), two separate groups."""
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, len(a), (n_boot, len(a)))
    ib = rng.integers(0, len(b), (n_boot, len(b)))
    d = a[ia].mean(1) - b[ib].mean(1)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def slope(p: np.ndarray, y: np.ndarray) -> float:
    return cal.calibration_slope(p[:, 0], (y == 0).astype(float))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over all three outcomes: forecasts are grouped into
    ten equal-width bands; the gap between forecast and frequency is averaged,
    weighted by the number of forecasts in each band."""
    f = p.ravel()
    o = np.eye(3)[y].ravel()
    band = np.minimum((f * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        sel = band == b
        if sel.any():
            total += sel.sum() * abs(f[sel].mean() - o[sel].mean())
    return total / len(f)


def scores(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    return {"rps": float(metrics.rps(p, y).mean()),
            "log_loss": float(metrics.log_loss(p, y).mean()),
            "brier": float(metrics.brier(p, y).mean()),
            "top_pick": float((p.argmax(1) == y).mean()),
            "slope": slope(p, y), "ece": ece(p, y)}


def diff_row(name: str, a: np.ndarray, b: np.ndarray, y: np.ndarray) -> list[dict]:
    rows = []
    for metric, fn in (("rps", metrics.rps), ("log_loss", metrics.log_loss)):
        d = fn(a, y) - fn(b, y)
        lo, hi = bt.paired_ci(d)
        rows.append({"comparison": name, "metric": metric, "mean_diff": float(d.mean()),
                     "ci_low": lo, "ci_high": hi})
    return rows


# ---------------------------------------------------------------- data

def load(challenger_path: Path) -> tuple[pd.DataFrame, list[str]]:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    base = bt.run(matches, bt.Config(seasons=[*TUNE, *TEST]))
    s = bt.attach_outcomes_and_market(base, matches)
    s["lock_utc"] = s["as_of_utc"]
    m = matches.set_index("match_id")
    for col in ("home_id", "away_id", "kickoff_utc", "result_available_utc",
                "home_corners", "away_corners", "home_yellows", "away_yellows"):
        s[col] = s["match_id"].map(m[col])

    bdc = pd.read_parquet(BACKTESTS / "dc_bayes_v1_walkforward_2021_2025.parquet")
    bdc = bdc.set_index("match_id")
    for k in (*OUTCOMES, "over_2_5", "btts", "intervals", "matrix"):
        s[f"bdc_{k}"] = s["match_id"].map(bdc[f"bdc_{k}"])

    ch = pd.read_parquet(challenger_path)
    challengers = sorted(ch["model"].unique())
    for name, g in ch.groupby("model"):
        g = g.set_index("match_id")
        for k in OUTCOMES:
            s[f"{name}_{k}"] = s["match_id"].map(g[f"p_{k}"])

    # Data-quality flag available in the backtest: a promoted club with fewer than
    # six league games this season at lock (spec S7). Counted once per match.
    sched = ml_features.schedule(matches, s)
    promoted = ml_features.promoted_teams(matches)
    early = np.zeros(len(s), dtype=bool)
    for side in ("home", "away"):
        is_promoted = np.array([promoted.get((t, int(se)), 0) == 1
                                for t, se in zip(s[f"{side}_id"], s["season"], strict=True)])
        played = s["match_id"].map(sched[f"played_{side}"]).to_numpy()
        early |= is_promoted & (played < 6)
    s["flag_promoted"] = early
    return s.reset_index(drop=True), challengers


def count_markets(s: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for market, (stem, (h, a), _) in COUNT_MARKETS.items():
        preds = pd.read_parquet(BACKTESTS / f"{stem}_walkforward_2021_2025.parquet")
        keep = s[["match_id", "season", "league", "flag_promoted", h, a]]
        frame = preds.drop(columns=["season", "league"]).merge(keep, on="match_id")
        frame["total"] = frame[h] + frame[a]
        out[market] = frame
    return out


# ---------------------------------------------------------------- stacking

def cross_fit_tuning(s: pd.DataFrame, models: list[str]) -> np.ndarray:
    """Stacked forecasts for the tuning seasons that never saw their own season:
    weights fitted on 2021/22 score 2022/23, and the other way round."""
    out = np.full((len(s), 3), np.nan)
    for fit_on, apply_to in ((TUNE[0], TUNE[1]), (TUNE[1], TUNE[0])):
        a, b = (s["season"] == fit_on).to_numpy(), (s["season"] == apply_to).to_numpy()
        st = stacking.fit({m: probs(s[a], m) for m in models}, s["outcome"].to_numpy()[a])
        out[b] = st.combine({m: probs(s[b], m) for m in models})
    return out


def weekly_replay(s: pd.DataFrame, models: list[str],
                  start: stacking.Stack) -> tuple[np.ndarray, pd.DataFrame]:
    """The live weekly re-weight (spec S5.6, Phase 7 design), replayed over the test
    seasons. Every Monday 00:00 UTC the target weights are refitted on every scored
    prediction so far (tuning pool plus test matches with known results). The weights
    then move towards the target under the guardrails: 5% floor, 10 points a week,
    no move before 60 scored live predictions."""
    p_all = {m: probs(s, m) for m in models}
    y = s["outcome"].to_numpy()
    is_test = s["season"].isin(TEST).to_numpy()
    week = (s["lock_utc"].dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
            .dt.tz_localize("UTC"))
    out = np.full((len(s), 3), np.nan)
    w = start.weights.copy()
    history = []
    for wk in sorted(week[is_test].unique()):
        known = (s["result_available_utc"] <= wk).to_numpy()
        n_live = int((known & is_test).sum())
        if n_live >= stacking.MIN_LIVE_PREDICTIONS:
            target = stacking.fit({m: p[known] for m, p in p_all.items()}, y[known]).weights
            w = stacking.guarded_update(w, target, n_live)
        rows = is_test & (week == wk).to_numpy()
        out[rows] = sum(wi * p_all[m][rows] for m, wi in zip(models, w, strict=True))
        history.append({"week": wk, "n_live": n_live, **dict(zip(models, w, strict=True))})
    return out, pd.DataFrame(history)


# ---------------------------------------------------------------- calibration

def calibration_candidates(p: np.ndarray, y: np.ndarray) -> dict[str, cal.Calibrator]:
    out: dict[str, cal.Calibrator] = {"identity": cal.Identity(),
                                      "power": cal.PowerCalibration.fit(p, y)}
    for pen in (0.001, 0.01, 0.1):
        out[f"dirichlet_{pen}"] = cal.DirichletCalibration.fit(p, y, penalty=pen)
    return out


def monthly_power(pool: pd.DataFrame, col: str, test_mask: np.ndarray) -> np.ndarray:
    """Walk-forward monthly power map, trailing 760 scored forecasts (Phase 3a design)."""
    p = probs(pool, col)
    y = pool["outcome"].to_numpy()
    out = p.copy()
    month = pool["lock_utc"].dt.tz_convert(None).dt.to_period("M")
    for period in sorted(set(month[test_mask])):
        start = period.start_time.tz_localize("UTC")
        past = np.flatnonzero((pool["result_available_utc"] <= start).to_numpy())
        past = past[np.argsort(pool["lock_utc"].to_numpy()[past])][-760:]
        now = test_mask & (month == period).to_numpy()
        out[now] = cal.PowerCalibration.fit(p[past], y[past]).apply(p[now])
    return out[test_mask]


# ---------------------------------------------------------------- tiers

def tier_rows(label: str, tier: np.ndarray, fav: np.ndarray, hit: np.ndarray,
              surprise: np.ndarray, excess: np.ndarray) -> list[dict]:
    """Per tier: size, mean favoured probability, hit rate (with interval), the gap
    between them, log loss, and excess surprise (log loss minus the log loss the
    forecast itself expected; 0 is honest, above 0 is worse than promised)."""
    rows = []
    hit = hit.astype(float)
    for t in ("High", "Medium", "Low"):
        sel = tier == t
        if not sel.any():
            continue
        lo, hi = group_ci(hit[sel])
        g_lo, g_hi = group_ci(hit[sel] - fav[sel])
        rows.append({"market": label, "tier": t, "n": int(sel.sum()),
                     "share": float(sel.mean()), "mean_favoured": float(fav[sel].mean()),
                     "hit_rate": float(hit[sel].mean()), "hit_ci_low": lo, "hit_ci_high": hi,
                     "gap": float((hit[sel] - fav[sel]).mean()), "gap_ci_low": g_lo,
                     "gap_ci_high": g_hi, "log_loss": float(surprise[sel].mean()),
                     "excess_surprise": float(excess[sel].mean())})
    return rows


def separated(rows: list[dict]) -> bool:
    """Adjacent tiers' hit-rate intervals do not overlap."""
    by = {r["tier"]: r for r in rows}
    pairs = [("High", "Medium"), ("Medium", "Low")]
    return all(by[a]["hit_ci_low"] > by[b]["hit_ci_high"] for a, b in pairs
               if a in by and b in by)


def evidence_row(label: str, stage: str, mask: np.ndarray, excess: np.ndarray) -> dict:
    """Do the flagged (or demoted) forecasts do worse than they promised?"""
    a, b = excess[mask], excess[~mask]
    lo, hi = gap_ci(a, b) if len(a) > 1 else (float("nan"), float("nan"))
    return {"input": label, "stage": stage, "n_flagged": int(mask.sum()),
            "excess_flagged": float(a.mean()) if len(a) else float("nan"),
            "excess_rest": float(b.mean()), "gap": float(a.mean() - b.mean()) if len(a) else
            float("nan"), "ci_low": lo, "ci_high": hi}


def binary_parts(p_over: np.ndarray, happened: np.ndarray) -> tuple[np.ndarray, ...]:
    fav = np.maximum(p_over, 1 - p_over)
    hit = np.where(p_over >= 0.5, happened, ~happened)
    surprise = metrics.binary_log_loss(p_over, happened)
    q = np.clip(p_over, 1e-12, 1 - 1e-12)
    entropy = -(q * np.log(q) + (1 - q) * np.log(1 - q))
    return fav, hit, surprise, surprise - entropy


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--challengers", type=Path,
                    default=BACKTESTS / "challengers_walkforward_2021_2025.parquet")
    args = ap.parse_args(argv)
    start_time = time.time()

    s, challengers = load(args.challengers)
    components = ["elo", "dc", "bdc", *challengers]
    missing = [c for m in components for c in (f"{m}_{k}" for k in OUTCOMES) if s[c].isna().any()]
    assert not missing, f"missing component predictions: {missing[:5]}"
    y_all = s["outcome"].to_numpy()
    tune = s["season"].isin(TUNE).to_numpy()
    test = s["season"].isin(TEST).to_numpy()

    # 1. Stack weights from the tuning seasons.
    st = stacking.fit({m: probs(s[tune], m) for m in components}, y_all[tune])
    put(s, "stack", st.combine({m: probs(s, m) for m in components}))
    put(s, "stack_cf", cross_fit_tuning(s, components)[tune], rows=np.flatnonzero(tune))
    s.loc[test, [f"stack_cf_{k}" for k in OUTCOMES]] = probs(s[test], "stack")
    per_season_w = []
    for yr in TUNE:
        r = (s["season"] == yr).to_numpy()
        w = stacking.fit({m: probs(s[r], m) for m in components}, y_all[r]).weights
        per_season_w.append({"fitted_on": f"{yr}/{(yr + 1) % 100:02d}",
                             **{m: float(x) for m, x in zip(components, w, strict=True)}})
    put(s, "equal", np.mean([probs(s, m) for m in components], axis=0))
    cf_rows = []
    for name, col in (("stack, cross-fitted", "stack_cf"), ("equal weights", "equal"),
                      ("bdc", "bdc"), ("multinomial", "multinomial")):
        row: dict[str, object] = {"forecast": name}
        for yr in TUNE:
            r = (s["season"] == yr).to_numpy()
            row[f"{yr}/{(yr + 1) % 100:02d}"] = float(
                metrics.log_loss(probs(s[r], col), y_all[r]).mean())
        cf_rows.append(row)
    weekly, history = weekly_replay(s, components, st)
    put(s, "stack_weekly", weekly[test], rows=np.flatnonzero(test))
    stacking_json = {"models": st.models, "weights": [round(float(w), 4) for w in st.weights],
                     "floor": st.floor, "fitted_on": "2021/22 and 2022/23 walk-forward predictions",
                     "n_matches": int(tune.sum()), "use": False}
    OUT_STACK.parent.mkdir(parents=True, exist_ok=True)
    OUT_STACK.write_text(json.dumps(stacking_json, indent=2) + "\n", encoding="utf-8")

    # 2. Leakage alarm: top-pick accuracy of every forecast, every season.
    forecasts = ["base", *components, "stack"]
    alarm_rows = [{"model": m, "tuning": float((probs(s[tune], m).argmax(1) == y_all[tune]).mean()),
                   "test": float((probs(s[test], m).argmax(1) == y_all[test]).mean())}
                  for m in forecasts]
    alarm = any(max(r["tuning"], r["test"]) > LEAKAGE_ALARM for r in alarm_rows)

    # 3. Test seasons, once: every forecast against the market.
    t = s[test].copy()
    yt = t["outcome"].to_numpy()
    markets = ["mkt_avg_pre", "mkt_sharp"]
    board = [*forecasts, "stack_weekly", *markets]
    common = t.dropna(subset=[f"{m}_{k}" for m in board for k in OUTCOMES])
    yc = common["outcome"].to_numpy()
    overall = [{"forecast": m, "n": len(common), **scores(probs(common, m), yc)} for m in board]
    per_league = []
    for lg, g in common.groupby("league"):
        yg = g["outcome"].to_numpy()
        per_league += [{"league": lg, "forecast": m, **scores(probs(g, m), yg)}
                       for m in ("elo", "bdc", "stack", "mkt_avg_pre", "mkt_sharp")]
    best_ch = min(challengers, key=lambda m: float(metrics.log_loss(probs(common, m), yc).mean()))
    diffs = []
    for other in ("bdc", "elo", best_ch, "mkt_avg_pre", "mkt_sharp"):
        diffs += diff_row(f"stack minus {other}", probs(common, "stack"), probs(common, other), yc)
    diffs += diff_row(f"{best_ch} minus bdc", probs(common, best_ch), probs(common, "bdc"), yc)
    diffs += diff_row("stack_weekly minus stack", probs(common, "stack_weekly"),
                      probs(common, "stack"), yc)
    second_look = diff_row("equal weights minus bdc", probs(common, "equal"),
                           probs(common, "bdc"), yc)

    # 4. Calibration on the stack: method chosen on the cross-fitted tuning forecasts.
    first, second = (s["season"] == TUNE[0]).to_numpy(), (s["season"] == TUNE[1]).to_numpy()
    choice = []
    for name, c in calibration_candidates(probs(s[first], "stack_cf"), y_all[first]).items():
        choice.append({"method": name, **scores(c.apply(probs(s[second], "stack_cf")),
                                                y_all[second])})
    best_method = min(choice, key=lambda r: r["log_loss"])["method"]
    chosen = calibration_candidates(probs(s[tune], "stack_cf"), y_all[tune])[best_method]
    raw_t = probs(t, "stack")
    fixed_t = chosen.apply(raw_t)
    monthly_t = monthly_power(s, "stack_cf", test)
    cal_rows = [{"forecast": "stack, raw", **scores(raw_t, yt)},
                {"forecast": f"stack, fixed map ({best_method})", **scores(fixed_t, yt)},
                {"forecast": "stack, monthly power map", **scores(monthly_t, yt)}]
    cal_diffs = (diff_row(f"fixed map ({best_method}) minus raw", fixed_t, raw_t, yt)
                 + diff_row("monthly power map minus raw", monthly_t, raw_t, yt))
    fixed_ok = cal_diffs[1]["ci_high"] < 0
    monthly_ok = cal_diffs[3]["ci_high"] < 0
    cal.save(chosen, OUT_CAL, fitted_on="cross-fitted stack forecasts, 2021/22 and 2022/23",
             n_matches=int(tune.sum()), chosen_on="fit 2021/22, validate 2022/23",
             test_log_loss_change=cal_diffs[1]["mean_diff"], use=bool(fixed_ok))
    final_t = fixed_t if fixed_ok else raw_t

    # 5. Goals markets kept coherent with the stack: rescale each Bayesian scoreline
    # table so its home, draw, away regions match the stack (PRD item 22).
    over_raw, over_res, btts_raw, btts_res = [], [], [], []
    for flat, q in zip(t["bdc_matrix"], final_t, strict=True):
        mat = np.asarray(flat, dtype=float).reshape(11, 11)
        a, b = dc.markets(mat), dc.markets(cal.rescale_matrix(mat, q))
        over_raw.append(a["p_over_2_5"])
        over_res.append(b["p_over_2_5"])
        btts_raw.append(a["p_btts"])
        btts_res.append(b["p_btts"])
    goals_total = (t["home_goals"] + t["away_goals"]).to_numpy()
    btts_hit = ((t["home_goals"] > 0) & (t["away_goals"] > 0)).to_numpy()
    goal_rows = []
    for label, raw, res, happened in (("over 2.5", over_raw, over_res, goals_total > 2.5),
                                      ("both teams score", btts_raw, btts_res, btts_hit)):
        a = metrics.binary_log_loss(np.array(raw), happened)
        b = metrics.binary_log_loss(np.array(res), happened)
        lo, hi = bt.paired_ci(b - a)
        goal_rows.append({"market": label, "bdc_log_loss": float(a.mean()),
                          "rescaled_log_loss": float(b.mean()), "diff": float((b - a).mean()),
                          "ci_low": lo, "ci_high": hi})
    ou = t.assign(res=over_res).dropna(subset=["mkt_sharp_over_2_5", "mkt_avg_pre_over_2_5"])
    ou_y = (ou["home_goals"] + ou["away_goals"]).to_numpy() > 2.5
    ou_rows = [{"forecast": name, "n": len(ou),
                "log_loss": float(metrics.binary_log_loss(ou[col].to_numpy(), ou_y).mean()),
                "brier": float(metrics.binary_brier(ou[col].to_numpy(), ou_y).mean())}
               for name, col in (("base", "base_over_2_5"), ("dc", "dc_over_2_5"),
                                 ("bdc", "bdc_over_2_5"), ("bdc rescaled to stack", "res"),
                                 ("mkt_avg_pre", "mkt_avg_pre_over_2_5"),
                                 ("mkt_sharp", "mkt_sharp_over_2_5"))]

    # 6. Tiers for home, draw, away, for both candidate published forecasts: the
    # Bayesian primary (bdc) and the stack. Disagreement is always stack against
    # Bayesian; the interval is the Bayesian 80% interval on the favoured outcome.
    names = np.array(["p_home", "p_draw", "p_away"])
    stack_tu = probs(s[tune], "stack_cf")
    if fixed_ok:
        stack_tu = chosen.apply(stack_tu)
    candidates = {"bdc": (probs(s[tune], "bdc"), probs(t, "bdc")),
                  "stack": (stack_tu, final_t)}
    all_thresholds = []
    tiers_1x2: dict[str, dict[str, list[dict]]] = {}
    evidence = []
    for fc, (p_tu, p_te) in candidates.items():
        parts = {}
        for stage, frame, p, other in (("tuning", s[tune], p_tu, stack_tu),
                                       ("test", t, p_te, final_t)):
            top = p.argmax(1)
            iv = frame["bdc_intervals"].map(json.loads)
            width = np.array([d[n][1] - d[n][0] for d, n in zip(iv, names[top], strict=True)])
            dis = 0.5 * np.abs(other - probs(frame, "bdc")).sum(1)
            y = frame["outcome"].to_numpy()
            surprise = metrics.log_loss(p, y)
            entropy = -(np.clip(p, 1e-12, 1) * np.log(np.clip(p, 1e-12, 1))).sum(1)
            parts[stage] = (p.max(1), width, dis, top == y, surprise, surprise - entropy,
                            frame["flag_promoted"].to_numpy())
        fav, width, dis = parts["tuning"][:3]
        th = tiers.fit(f"1x2_{fc}", fav, width, dis,
                       basis=f"{fc} forecasts, 2021/22 and 2022/23"
                             + (" (stack cross-fitted)" if fc == "stack" else ""))
        assert th.width_max is not None and th.disagree_max is not None
        all_thresholds.append(th)
        tiers_1x2[fc] = {}
        for stage, (fav, width, dis, hit, sur, exc, flag) in parts.items():
            tier = tiers.assign(th, fav, flag.astype(int), width=width, disagree=dis)
            tiers_1x2[fc][stage] = tier_rows(f"1X2 {fc}", tier, fav, hit, sur, exc)
            evidence += [evidence_row(f"{fc}: wide interval", stage, width > th.width_max, exc),
                         evidence_row(f"{fc}: stack and Bayesian disagree", stage,
                                      dis > th.disagree_max, exc),
                         evidence_row(f"{fc}: promoted club, under 6 games", stage, flag, exc)]
    th_by = {th.market: th for th in all_thresholds}

    # 7. Tiers for over/under lines.
    ou_tier_rows: dict[str, list[dict]] = {"tuning": [], "test": []}
    ou_evidence = []
    goals_parts = {}
    for stage, mask in (("tuning", tune), ("test", test)):
        frame = s[mask]
        happened = (frame["home_goals"] + frame["away_goals"]).to_numpy() > 2.5
        iv = frame["bdc_intervals"].map(json.loads)
        width = np.array([d["p_over_2_5"][1] - d["p_over_2_5"][0] for d in iv])
        goals_parts[stage] = (*binary_parts(frame["bdc_over_2_5"].to_numpy(), happened), width,
                              frame["flag_promoted"].to_numpy().astype(int))
    th_goals = tiers.fit("goals_over_2_5", goals_parts["tuning"][0], goals_parts["tuning"][4],
                         basis="dc_bayes_v1, 2021/22 and 2022/23")
    all_thresholds.append(th_goals)
    for stage, (fav, hit, sur, exc, width, flags) in goals_parts.items():
        tier = tiers.assign(th_goals, fav, flags, width=width)
        ou_tier_rows[stage] += tier_rows("goals over 2.5", tier, fav, hit, sur, exc)
        if stage == "test":
            ou_evidence.append(evidence_row("goals over 2.5: promoted club, under 6 games",
                                            stage, flags.astype(bool), exc))
    counts = count_markets(s)
    for market, frame in counts.items():
        is_tune = frame["season"].isin(TUNE).to_numpy()
        for line in COUNT_MARKETS[market][2]:
            col = f"p_over_{str(line).replace('.', '_')}"
            fav, hit, sur, exc = binary_parts(frame[col].to_numpy(),
                                              frame["total"].to_numpy() > line)
            flags = frame["flag_promoted"].to_numpy().astype(int)
            if market == "cards":
                flags = flags + (~frame["referee_known"].to_numpy().astype(bool)).astype(int)
            th = tiers.fit(f"{market}_over_{line}", fav[is_tune],
                           basis=f"{COUNT_MARKETS[market][0]}_v1, 2021/22 and 2022/23")
            all_thresholds.append(th)
            for stage, sel in (("tuning", is_tune), ("test", ~is_tune)):
                tier = tiers.assign(th, fav[sel], flags[sel])
                ou_tier_rows[stage] += tier_rows(f"{market} over {line}", tier, fav[sel],
                                                 hit[sel], sur[sel], exc[sel])
            ou_evidence.append(evidence_row(f"{market} over {line}: promoted club, under 6 games",
                                            "test", frame["flag_promoted"].to_numpy()[~is_tune],
                                            exc[~is_tune]))
            if market == "cards":
                epl_test = (~is_tune) & (frame["league"] == "EPL").to_numpy()
                unknown = ~frame["referee_known"].to_numpy().astype(bool)
                ou_evidence.append(evidence_row(f"cards over {line}: EPL referee unknown",
                                                "test", unknown[epl_test], exc[epl_test]))
    tiers.save(all_thresholds, OUT_TIERS, use=False,
               rule="favoured probability sets the start; wide interval or disagreement drops "
                    "one tier; one flag caps at Medium; two or more force Low")

    # 8. Figure: reliability of the stack and of each 1X2 tier, test seasons.
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for label, p, colour in (("Bayesian (bdc)", probs(t, "bdc"), "#D55E00"),
                             ("stack", final_t, "#0072B2")):
        f, o = p.ravel(), np.eye(3)[yt].ravel()
        order = np.argsort(f)
        groups = np.array_split(order, 15)
        axes[0].plot([f[g].mean() for g in groups], [o[g].mean() for g in groups], "o-",
                     color=colour, label=label, ms=4)
    axes[0].plot([0, 1], [0, 1], "k:", lw=1)
    axes[0].set(xlabel="forecast probability", ylabel="observed frequency",
                title="Home, draw, away: all outcomes, test seasons")
    axes[0].legend()
    colours = {"High": "#009E73", "Medium": "#E69F00", "Low": "#CC79A7"}
    for fc, marker in (("bdc", "s"), ("stack", "o")):
        for r in tiers_1x2[fc]["test"]:
            axes[1].errorbar(r["mean_favoured"], r["hit_rate"],
                             yerr=[[r["hit_rate"] - r["hit_ci_low"]],
                                   [r["hit_ci_high"] - r["hit_rate"]]],
                             fmt=marker, color=colours[r["tier"]], capsize=4,
                             label=f"{fc} {r['tier']} ({r['n']})")
    axes[1].plot([0.3, 0.9], [0.3, 0.9], "k:", lw=1)
    axes[1].set(xlabel="mean favoured probability", ylabel="favourite's hit rate",
                title="1X2 tiers, test seasons (95% intervals)")
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=120)
    plt.close(fig)

    # 9. Report.
    weights_rows = [{"model": m, "weight": float(w)} for m, w in zip(st.models, st.weights,
                                                                    strict=True)]
    last_weights = history.iloc[-1]
    replay_rows = [{"model": m, "start": float(w), "end_of_2025_26": float(last_weights[m]),
                    "min": float(history[m].min()), "max": float(history[m].max())}
                   for m, w in zip(st.models, st.weights, strict=True)]
    sep = {fc: separated(v["test"]) for fc, v in tiers_1x2.items()}
    ou_sep = [{"market": m, "separated_on_test": separated(
        [r for r in ou_tier_rows["test"] if r["market"] == m])}
        for m in dict.fromkeys(r["market"] for r in ou_tier_rows["test"])]
    ll = {r["forecast"]: r["log_loss"] for r in overall}
    vs = {r["comparison"]: r for r in diffs if r["metric"] == "log_loss"}
    n_ou_sep = sum(r["separated_on_test"] for r in ou_sep)
    accept = [
        {"check": "Full backtest against the closing market",
         "result": f"Test log loss: stack {ll['stack']:.4f}, Bayesian {ll['bdc']:.4f}, "
                   f"Friday market {ll['mkt_avg_pre']:.4f}, closing market {ll['mkt_sharp']:.4f}. "
                   f"Stack minus closing {vs['stack minus mkt_sharp']['mean_diff']:+.4f} "
                   f"(interval {vs['stack minus mkt_sharp']['ci_low']:+.4f} to "
                   f"{vs['stack minus mkt_sharp']['ci_high']:+.4f})."},
        {"check": "Tier hit rates clearly separated",
         "result": f"1X2: Bayesian {'yes' if sep['bdc'] else 'no'}, stack "
                   f"{'yes' if sep['stack'] else 'no'}. Over/under: {n_ou_sep} of {len(ou_sep)} "
                   "lines."},
        {"check": "Leakage red flag (top pick above 60%)",
         "result": "ALARM" if alarm else "Passed"},
    ]
    text = f"""# Phase 4 backtest: challengers, stacking, calibration, tiers

Generated by `scripts/backtest_phase4.py` in {time.time() - start_time:.0f} s.
Walk-forward predictions only. Tuning seasons 2021/22 and 2022/23 set every weight,
map, and cut point; test seasons 2023/24 to 2025/26 are scored once. Lower scores
are better. `slope`: observed home-win rate against forecast over five groups
(1 is honest; above 1 is too timid). `ece`: expected calibration error over all
three outcomes. Markets: `mkt_avg_pre` = market average at the Friday or Tuesday
snapshot, closest to our lock; `mkt_sharp` = Pinnacle closing (Betfair Exchange
closing after Pinnacle's data ends in Jan 2026). Odds are a benchmark, never an input.

## Acceptance checks (spec section 11, Phase 4)

{table(accept)}

## 1. Leakage alarm (spec S8: top pick above 60%)

{table(alarm_rows)}

**{'ALARM: stop and hunt for leakage.' if alarm else 'Passed: no forecast above 60%.'}**

## 2. Stack weights, fitted on the tuning seasons

Linear pool, each model at least 5%. Challengers: {', '.join(challengers)}.

{table(weights_rows)}

### Are the weights stable? Fitted on each tuning season alone

{table(per_season_w)}

### Cross-fitted log loss on the tuning seasons (weights from the other season)

{table(cf_rows)}

## 3. Test seasons: home, draw, away against the market

{table(overall)}

### Paired differences, 95% bootstrap intervals (negative = first forecast better)

{table(diffs)}

Second look, added after the table above was seen, so it cannot choose anything
on its own: equal weights on all seven models.

{table(second_look)}

### By league

{table(per_league)}

### Weekly re-weight replay (Phase 7 design)

`stack_weekly` starts from the tuning weights, then each Monday moves towards
weights refitted on every scored forecast so far: at most 10 points a week, 5%
floor, no move before 60 scored test matches.

{table(replay_rows)}

## 4. Calibration of the stack, revisited

Method chosen on cross-fitted tuning forecasts (weights from the other season):
fit on 2021/22, validate on 2022/23.

{table(choice)}

Chosen: **{best_method}**. Test seasons:

{table(cal_rows)}

{table(cal_diffs)}

Strict rule (spec S5.6; decision of 25 Sep 2026): apply only if the whole 95%
interval of the log-loss change is below zero. Fixed map: **{'apply' if fixed_ok
else 'do not apply'}**. Monthly map: **{'clear improvement' if monthly_ok else
'no clear improvement'}**.

## 5. Goals markets kept coherent with the stack

Each Bayesian scoreline table is rescaled so its home-win, draw, and away-win
regions match the {'calibrated ' if fixed_ok else ''}stack. Difference = rescaled
minus Bayesian.

{table(goal_rows)}

Over/under 2.5 against the market (test seasons, matches with odds):

{table(ou_rows)}

## 6. Confidence tiers: home, draw, away

Two candidate published forecasts: the Bayesian primary (`bdc`, live now) and the
stack. Each gets its own cut points from the tuning seasons:

{table([asdict(th_by[k]) for k in ("1x2_bdc", "1x2_stack")])}

`high` and `low`: top quarter and bottom third of tuning favoured probabilities.
`width_max` and `disagree_max`: widest or most disputed tenth of tuning forecasts;
above either drops one tier. A promoted club with fewer than 6 league games caps
the tier at Medium. Other flags (manager change, unanswered question, source
failure) have no history and apply live only.

`gap` = hit rate minus mean favoured probability (0 is honest; above 0 means the
favourite won more often than promised). `excess_surprise` = log loss minus the
log loss the forecast expected of itself.

### Test seasons

{table(tiers_1x2['bdc']['test'] + tiers_1x2['stack']['test'])}

Hit rates clearly separated on the test seasons (adjacent 95% intervals do not
overlap): bdc **{'yes' if sep['bdc'] else 'no'}**, stack **{'yes' if sep['stack'] else 'no'}**.

### Tuning seasons

{table(tiers_1x2['bdc']['tuning'] + tiers_1x2['stack']['tuning'])}

### Do the uncertainty inputs and flags pick out worse-than-promised forecasts?

The real test of a tier input (PRD item 13). `gap` = excess surprise of the
flagged forecasts minus the rest; above 0 means the input finds forecasts that do
worse than promised.

{table(evidence)}

![Reliability](figures/phase4_reliability.png)

## 7. Confidence tiers: over/under lines

Favoured probability = the likelier side of the line. Cut points per line from
the tuning seasons, same quantiles as above. Goals also use the 80% interval
width. Cards count an unknown referee as a flag (all La Liga matches, most EPL
Friday and Saturday matches), so with a promoted club early in the season a
cards forecast has two flags and is Low.

### Hit rates clearly separated on the test seasons?

{table(ou_sep)}

### Test seasons

{table(ou_tier_rows['test'])}

### Do the flags pick out worse-than-promised forecasts? Test seasons

Unknown referee is checked in the EPL only (La Liga never has one at lock).

{table(ou_evidence)}

### Tuning seasons

{table(ou_tier_rows['tuning'])}
"""
    OUT_MD.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
