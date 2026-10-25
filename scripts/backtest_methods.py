"""Score the new methods N1 to N7 against the published forecast (pre-registered checks).

Plan: data/audit/preregistration_methods_hda_2026_10.md (sections 3 and 4, Amendment 1).

Inputs:
- the published forecast and the current models' walk-forward forecasts:
  data/backtests/baselines_2021_2025_shape_v1.parquet (published = dc_bayes_v1 with shape_v1)
  and data/backtests/dc_bayes_v1_walkforward_2021_2025.parquet (the Bayesian model without
  the goals fix, a member of the current stack);
- the new methods' walk-forward forecasts, `methods_<name>.parquet` from fp.research.methods;
- optionally the matches table, for the bookmaker benchmark (reported, never judged).

Protocol: 2021/22 and 2022/23 choose N4 and N5's representatives, fit the stacks and choose
the model per league (N6); 2023/24 to 2025/26 are scored once.

    uv run python scripts/backtest_methods.py --preds out/ [--matches PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ensemble import stacking
from fp.evaluate import backtest as bt
from fp.evaluate import metrics

BACKTESTS = ROOT / "data" / "backtests"
BASELINES = BACKTESTS / "baselines_2021_2025_shape_v1.parquet"
BDC = BACKTESTS / "dc_bayes_v1_walkforward_2021_2025.parquet"
REPORT = ROOT / "reports" / "methods_hda_backtest_2026_10.md"
RESULTS = BACKTESTS / "methods_results_2026_10.json"
PREDICTIONS = BACKTESTS / "methods_walkforward_2021_2025.parquet"
TUNE = (2021, 2022)
TEST = (2023, 2024, 2025)
OUTCOMES = ("home", "draw", "away")
CURRENT = ["elo", "dc", "bdc", "multinomial", "ordered_logit", "random_forest", "xgboost"]
SINGLE = {"N1": "lightgbm", "N2": "lstm", "N3": "transformer"}
PAIRS = {"N4": ("arima_multinomial", "arima_lightgbm"),
         "N5": ("prophet_multinomial", "prophet_lightgbm")}
NEW_FILES = [*SINGLE.values(), *[m for pair in PAIRS.values() for m in pair]]
JUDGED = ("N1", "N2", "N3", "N4", "N5", "N6", "N7")
N6_FIXED = ["published", "elo", "dc", "ordered_logit", "multinomial", "random_forest",
            "xgboost", "stack"]
LEVEL_A1, LEVEL_A2 = 0.99, 0.95
N_BOOT, SEED = 4000, 2026
ECE_MARGIN, SLOPE_RANGE, LEAK_ALARM = 0.005, (0.8, 1.25), 0.60


def _phase4():
    """Phase 4's calibration measures (slope over five groups, ECE), reused unchanged."""
    spec = importlib.util.spec_from_file_location("backtest_phase4",
                                                  ROOT / "scripts" / "backtest_phase4.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probs(frame: pd.DataFrame, name: str) -> np.ndarray:
    return frame[[f"{name}_{k}" for k in OUTCOMES]].to_numpy(dtype=float)


def put(frame: pd.DataFrame, name: str, p: np.ndarray, mask: np.ndarray | None = None) -> None:
    cols = [f"{name}_{k}" for k in OUTCOMES]
    for c in cols:
        if c not in frame:
            frame[c] = np.nan
    if mask is None:
        frame[cols] = p
    else:
        frame.loc[mask, cols] = p


def interval(diff: np.ndarray, level: float, n_boot: int = N_BOOT,
             seed: int = SEED) -> tuple[float, float]:
    """Paired bootstrap over matches: the `level` interval of the mean difference."""
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (n_boot, len(diff)))].mean(axis=1)
    tail = (1 - level) / 2 * 100
    return float(np.percentile(means, tail)), float(np.percentile(means, 100 - tail))


def load(preds_dir: Path, matches: pd.DataFrame | None, allow_missing: bool = False
         ) -> pd.DataFrame:
    s = pd.read_parquet(BASELINES)
    s["season"] = s["match_id"].str.split("_").str[1].str[:2].astype(int) + 2000
    s = s.rename(columns={f"p_{k}": f"published_{k}" for k in OUTCOMES})
    s["outcome"] = metrics.outcome_1x2(s["home_goals"].to_numpy(), s["away_goals"].to_numpy())
    bdc = pd.read_parquet(BDC).set_index("match_id")
    for k in OUTCOMES:
        s[f"bdc_{k}"] = s["match_id"].map(bdc[f"bdc_{k}"])
    for name in NEW_FILES:
        path = preds_dir / f"methods_{name}.parquet"
        if not path.exists():
            if allow_missing:
                continue
            raise SystemExit(f"missing {path}")
        g = pd.read_parquet(path).set_index("match_id")
        for k in OUTCOMES:
            s[f"{name}_{k}"] = s["match_id"].map(g[f"p_{k}"])
    if matches is not None:
        mk = bt.attach_outcomes_and_market(s[["match_id"]], matches)
        for name in ("mkt_sharp", "mkt_avg_pre"):
            for k in OUTCOMES:
                s[f"{name}_{k}"] = mk[f"{name}_{k}"].to_numpy()
    return s.reset_index(drop=True)


def log_loss(frame: pd.DataFrame, name: str) -> np.ndarray:
    return metrics.log_loss(probs(frame, name), frame["outcome"].to_numpy())


def stack_pair(s: pd.DataFrame, members: list[str], name: str, tune: np.ndarray) -> None:
    """Weights fitted on both tuning seasons (used on the test seasons), plus cross-fitted
    tuning forecasts (weights from the other season) for choosing (Amendment 1, item 6)."""
    y = s["outcome"].to_numpy()
    st = stacking.fit({m: probs(s[tune], m) for m in members}, y[tune])
    put(s, name, st.combine({m: probs(s, m) for m in members}))
    cf = np.full((len(s), 3), np.nan)
    for fit_on, apply_to in ((TUNE[0], TUNE[1]), (TUNE[1], TUNE[0])):
        a = (s["season"] == fit_on).to_numpy()
        b = (s["season"] == apply_to).to_numpy()
        w = stacking.fit({m: probs(s[a], m) for m in members}, y[a])
        cf[b] = w.combine({m: probs(s[b], m) for m in members})
    put(s, f"{name}_cf", cf)
    s.loc[~tune, [f"{name}_cf_{k}" for k in OUTCOMES]] = probs(s[~tune], name)
    s.attrs[f"{name}_weights"] = {m: float(x) for m, x in zip(members, st.weights, strict=True)}


def build_forecasts(s: pd.DataFrame) -> dict:
    tune = s["season"].isin(TUNE).to_numpy()
    chosen: dict = {"representatives": {}, "n6": {}}
    for code, name in SINGLE.items():
        put(s, code, probs(s, name))
    for code, pair in PAIRS.items():
        losses = {m: float(log_loss(s[tune], m).mean()) for m in pair}
        rep = min(losses, key=lambda m: losses[m])
        chosen["representatives"][code] = {"chosen": rep, "tuning_log_loss": losses}
        put(s, code, probs(s, rep))
    stack_pair(s, CURRENT, "stack", tune)
    stack_pair(s, [*CURRENT, *[f"N{i}" for i in range(1, 6)]], "N7", tune)
    pool = [*N6_FIXED, "N1", "N2", "N3", "N4", "N5"]
    n6 = np.full((len(s), 3), np.nan)
    for league in sorted(s["league"].unique()):
        lg = (s["league"] == league).to_numpy()
        frame = s[lg & tune]
        losses = {m: float(log_loss(frame, f"{m}_cf" if m == "stack" else m).mean())
                  for m in pool}
        best = min(losses, key=lambda m: losses[m])
        chosen["n6"][league] = {"chosen": best, "tuning_log_loss": losses}
        n6[lg] = probs(s[lg], best)
    put(s, "N6", n6)
    chosen["stack_weights"] = s.attrs.get("stack_weights")
    chosen["n7_weights"] = s.attrs.get("N7_weights")
    return chosen


def summary_row(frame: pd.DataFrame, name: str, p4) -> dict:
    p, y = probs(frame, name), frame["outcome"].to_numpy()
    return {"forecast": name, "n": len(frame), "log_loss": float(metrics.log_loss(p, y).mean()),
            "rps": float(metrics.rps(p, y).mean()), "brier": float(metrics.brier(p, y).mean()),
            "top_pick": float((p.argmax(1) == y).mean()), "slope": float(p4.slope(p, y)),
            "ece": float(p4.ece(p, y))}


def checks(s: pd.DataFrame) -> dict:
    p4 = _phase4()
    t = s[s["season"].isin(TEST)].reset_index(drop=True)
    names = ["published", *CURRENT, "stack", *NEW_FILES, *JUDGED]
    missing = [n for n in names if t[[f"{n}_{k}" for k in OUTCOMES]].isna().any().any()]
    if missing:
        raise SystemExit(f"forecasts missing on test matches: {missing}")
    table = [summary_row(t, n, p4) for n in names]
    leak = [r["forecast"] for r in table if r["top_pick"] > LEAK_ALARM]
    out: dict = {"test_matches": len(t), "summary": table, "leakage_alarm": leak}
    if leak:
        return out  # check L: stop, nothing judged until the alarm is explained
    base = next(r for r in table if r["forecast"] == "published")
    published = log_loss(t, "published")
    verdicts = []
    for code in JUDGED:
        diff = log_loss(t, code) - published
        lo, hi = interval(diff, LEVEL_A1)
        row = next(r for r in table if r["forecast"] == code)
        leagues = {}
        for league in sorted(t["league"].unique()):
            lg = (t["league"] == league).to_numpy()
            l_lo, l_hi = interval(diff[lg], LEVEL_A2)
            leagues[league] = {"mean": float(diff[lg].mean()), "low": l_lo, "high": l_hi}
        a1 = hi < 0
        calibrated = (row["ece"] <= base["ece"] + ECE_MARGIN
                      and SLOPE_RANGE[0] <= row["slope"] <= SLOPE_RANGE[1])
        worse_in = [lg for lg, v in leagues.items() if v["mean"] > 0]
        verdicts.append({
            "method": code, "mean_diff": float(diff.mean()), "low_99": lo, "high_99": hi,
            "A1_pass": bool(a1), "A2_by_league": leagues, "C_pass": bool(calibrated),
            "proposed": bool(a1 and calibrated and not worse_in),
            "proposed_for_other_league_only": bool(a1 and calibrated and worse_in),
            "worse_on_average_in": worse_in})
    out["verdicts"] = verdicts
    if "mkt_sharp_home" in t:
        odds = t.dropna(subset=[f"mkt_sharp_{k}" for k in OUTCOMES]
                        + [f"mkt_avg_pre_{k}" for k in OUTCOMES])
        out["markets"] = [summary_row(odds, n, p4) for n in
                          ("published", "stack", *JUDGED, "mkt_avg_pre", "mkt_sharp")]
    out["by_season"] = [{"season": int(se), **{n: float(log_loss(g, n).mean())
                                             for n in ("published", "stack", *JUDGED)}}
                        for se, g in t.groupby("season")]
    return out


def fmt(x: float, nd: int = 4) -> str:
    return f"{x:+.{nd}f}" if abs(x) < 1 else f"{x:.{nd}f}"


def report(chosen: dict, res: dict) -> str:
    lines = ["# New model families for home, draw, away: test results", "",
             "Pre-registered in `data/audit/preregistration_methods_hda_2026_10.md` (with "
             "Amendment 1). Generated by `scripts/backtest_methods.py`. Test seasons 2023/24 to "
             f"2025/26, EPL and La Liga, {res['test_matches']} matches, scored once. Lower is "
             "better for log loss, RPS, Brier and ECE; a calibration slope of 1 is honest.", ""]
    if res["leakage_alarm"]:
        lines += ["**Leakage alarm (check L): top-pick accuracy above 60% for "
                  f"{', '.join(res['leakage_alarm'])}. Nothing is judged until this is "
                  "explained.**", ""]
    lines += ["## Test-season scores", "",
              "| forecast | log loss | RPS | Brier | top pick | slope | ECE |",
              "|---|---|---|---|---|---|---|"]
    for r in res["summary"]:
        lines.append(f"| {r['forecast']} | {r['log_loss']:.4f} | {r['rps']:.4f} | "
                     f"{r['brier']:.4f} | {r['top_pick']:.3f} | {r['slope']:.3f} | "
                     f"{r['ece']:.4f} |")
    if "verdicts" in res:
        lines += ["", "## Checks A1 (99%, pooled), A2 (95%, by league) and C (calibration)", "",
                  "Log loss of the method minus the published forecast; negative is better.", "",
                  "| method | mean | 99% interval | A1 | EPL (95%) | La Liga (95%) | C "
                  "| proposed |",
                  "|---|---|---|---|---|---|---|---|"]
        for v in res["verdicts"]:
            lg = v["A2_by_league"]
            cell = {k: f"{fmt(x['mean'])} ({fmt(x['low'])} to {fmt(x['high'])})"
                    for k, x in lg.items()}
            prop = ("yes" if v["proposed"] else "other league only"
                    if v["proposed_for_other_league_only"] else "no")
            lines.append(f"| {v['method']} | {fmt(v['mean_diff'])} | {fmt(v['low_99'])} to "
                         f"{fmt(v['high_99'])} | {'pass' if v['A1_pass'] else 'fail'} | "
                         f"{cell.get('EPL', '')} | {cell.get('LaLiga', '')} | "
                         f"{'pass' if v['C_pass'] else 'fail'} | {prop} |")
    lines += ["", "## Choices made on 2021/22 and 2022/23", ""]
    for code, c in chosen["representatives"].items():
        losses = ", ".join(f"{m} {x:.4f}" for m, x in c["tuning_log_loss"].items())
        lines.append(f"- {code} representative: **{c['chosen']}** ({losses}).")
    for league, c in chosen["n6"].items():
        lines.append(f"- N6, {league}: **{c['chosen']}** (tuning log loss "
                     f"{c['tuning_log_loss'][c['chosen']]:.4f}).")
    for key in ("stack_weights", "n7_weights"):
        w = chosen.get(key) or {}
        lines.append(f"- {key.replace('_', ' ')}: "
                     + ", ".join(f"{m} {x:.2f}" for m, x in w.items()) + ".")
    if "markets" in res:
        lines += ["", "## Against the bookmakers (reported, not judged; matches with odds)", "",
                  "| forecast | n | log loss | RPS |", "|---|---|---|---|"]
        lines += [f"| {r['forecast']} | {r['n']} | {r['log_loss']:.4f} | {r['rps']:.4f} |"
                  for r in res["markets"]]
    if "by_season" in res:
        cols = [k for k in res["by_season"][0] if k != "season"]
        lines += ["", "## Log loss by test season", "", "| season | " + " | ".join(cols) + " |",
                  "|" + "---|" * (len(cols) + 1)]
        for r in res["by_season"]:
            lines.append(f"| {r['season']}/{(r['season'] + 1) % 100:02d} | "
                         + " | ".join(f"{r[c]:.4f}" for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preds", type=Path, required=True)
    ap.add_argument("--matches", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--predictions", type=Path, default=PREDICTIONS)
    args = ap.parse_args(argv)
    matches = pd.read_parquet(args.matches) if args.matches else None
    s = load(args.preds, matches)
    chosen = build_forecasts(s)
    res = checks(s)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report(chosen, res), encoding="utf-8")
    args.results.write_text(json.dumps({"chosen": chosen, **res}, indent=1) + "\n",
                            encoding="utf-8")
    keep = ["match_id", "league", "season", "outcome",
            *[f"{n}_{k}" for n in (*NEW_FILES, *JUDGED, "stack") for k in OUTCOMES]]
    s[keep].to_parquet(args.predictions, index=False)
    for v in res.get("verdicts", []):
        print(v["method"], "A1", v["A1_pass"], "C", v["C_pass"], "proposed", v["proposed"])
    return 1 if res["leakage_alarm"] else 0


if __name__ == "__main__":
    sys.exit(main())
