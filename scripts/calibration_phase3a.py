"""Phase 3a: calibrate the Bayesian model's home, draw, away probabilities.

1. Choose the method inside the tuning seasons: fit on 2021/22, validate on 2022/23.
2. Refit the chosen method on both tuning seasons.
3. Score the test seasons (2023/24 to 2025/26) once, raw against calibrated,
   including every goals market after rescaling the scoreline table.
4. Save the map to data/calibration/dc_bayes_v1.json, and the report to
   reports/calibration_phase3a.md. Spec S5.6: use it only if test log loss improves.

    uv run python scripts/calibration_phase3a.py TUNE_DIR TEST_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ensemble import calibration as cal
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.ingest.matches import PROCESSED
from fp.models import dixon_coles as dc

OUT_JSON = ROOT / "data" / "calibration" / "dc_bayes_v1.json"
OUT_MD = ROOT / "reports" / "calibration_phase3a.md"
GOAL_MARKETS = ["p_over_1_5", "p_over_2_5", "p_over_3_5", "p_btts"]


def load(folder: Path, matches: pd.DataFrame) -> pd.DataFrame:
    files = [f for f in folder.rglob("*_sot.parquet") if not f.name.endswith(".fits.parquet")]
    preds = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    m = matches.set_index("match_id")[["home_goals", "away_goals"]]
    preds = preds.join(m, on="match_id")
    preds["y"] = metrics.outcome_1x2(preds["home_goals"].to_numpy(),
                                     preds["away_goals"].to_numpy())
    return preds


def probs(frame: pd.DataFrame) -> np.ndarray:
    return frame[["bdc_home", "bdc_draw", "bdc_away"]].to_numpy()


def scores(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    return {"log_loss": float(metrics.log_loss(p, y).mean()),
            "rps": float(metrics.rps(p, y).mean()),
            "brier": float(metrics.brier(p, y).mean()),
            "top_pick": float((p.argmax(1) == y).mean()),
            "slope": cal.calibration_slope(p[:, 0], (y == 0).astype(float))}


def candidates(p: np.ndarray, y: np.ndarray) -> dict[str, cal.Calibrator]:
    out: dict[str, cal.Calibrator] = {"identity": cal.Identity(),
                                      "power": cal.PowerCalibration.fit(p, y)}
    for pen in (0.001, 0.01, 0.1):
        out[f"dirichlet_{pen}"] = cal.DirichletCalibration.fit(p, y, penalty=pen)
    return out


def goal_markets(frame: pd.DataFrame, q: np.ndarray | None) -> pd.DataFrame:
    """Goals markets from each match's table, rescaled to q when given."""
    rows = []
    for i, flat in enumerate(frame["bdc_matrix"]):
        m = np.asarray(flat, dtype=float).reshape(11, 11)
        if q is not None:
            m = cal.rescale_matrix(m, q[i])
        mk = dc.markets(m)
        rows.append({k: mk[k] for k in GOAL_MARKETS})
    return pd.DataFrame(rows, index=frame.index)


def outcomes(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    total = frame["home_goals"] + frame["away_goals"]
    return {"p_over_1_5": (total > 1.5).to_numpy(), "p_over_2_5": (total > 2.5).to_numpy(),
            "p_over_3_5": (total > 3.5).to_numpy(),
            "p_btts": ((frame["home_goals"] > 0) & (frame["away_goals"] > 0)).to_numpy()}


def table(rows: list[dict]) -> str:
    frame = pd.DataFrame(rows)
    head = "| " + " | ".join(frame.columns) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                                       for v in r) + " |" for r in frame.itertuples(index=False))
    return head + "\n" + body


def main(tune_dir: Path, test_dir: Path) -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    tune = load(tune_dir, matches)
    test = load(test_dir, matches)

    # 1. Method choice inside the tuning seasons.
    first, second = tune[tune["season"] == 2021], tune[tune["season"] == 2022]
    choice_rows = []
    for name, c in candidates(probs(first), first["y"].to_numpy()).items():
        s = scores(c.apply(probs(second)), second["y"].to_numpy())
        choice_rows.append({"method": name, **s})
    best = min(choice_rows, key=lambda r: r["log_loss"])["method"]

    # 2. Refit the winner on both tuning seasons.
    chosen = candidates(probs(tune), tune["y"].to_numpy())[best]

    # 3. Test seasons, once.
    y = test["y"].to_numpy()
    raw, calibrated = probs(test), chosen.apply(probs(test))
    test_rows = [{"forecast": "raw", **scores(raw, y)},
                 {"forecast": f"calibrated ({best})", **scores(calibrated, y)}]
    diffs = []
    for metric_name, fn in (("rps", metrics.rps), ("log_loss", metrics.log_loss)):
        d = fn(calibrated, y) - fn(raw, y)
        lo, hi = bt.paired_ci(d)
        diffs.append({"metric": metric_name, "calibrated_minus_raw": float(d.mean()),
                      "ci_low": lo, "ci_high": hi})
    by_league = []
    for lg, g in test.groupby("league"):
        yy = g["y"].to_numpy()
        by_league.append({"league": lg, "raw_rps": scores(probs(g), yy)["rps"],
                          "calibrated_rps": scores(chosen.apply(probs(g)), yy)["rps"],
                          "raw_slope": scores(probs(g), yy)["slope"],
                          "calibrated_slope": scores(chosen.apply(probs(g)), yy)["slope"]})

    raw_goals, cal_goals, happened = goal_markets(test, None), goal_markets(test, calibrated), \
        outcomes(test)
    goal_rows = []
    for k in GOAL_MARKETS:
        a = metrics.binary_log_loss(raw_goals[k].to_numpy(), happened[k])
        b = metrics.binary_log_loss(cal_goals[k].to_numpy(), happened[k])
        lo, hi = bt.paired_ci(b - a)
        goal_rows.append({"market": k, "raw_log_loss": float(a.mean()),
                          "rescaled_log_loss": float(b.mean()),
                          "diff": float((b - a).mean()), "ci_low": lo, "ci_high": hi})

    # A real improvement: the whole 95% interval of the log-loss change below zero.
    # A negative average alone can be noise.
    improves = diffs[1]["ci_high"] < 0
    cal.save(chosen, OUT_JSON, fitted_on="2021/22 and 2022/23 walk-forward predictions",
             n_matches=int(len(tune)), chosen_on="fit 2021/22, validate 2022/23",
             test_log_loss_change=diffs[1]["calibrated_minus_raw"], use=bool(improves))

    params = (f"alpha = {chosen.alpha:.3f}" if isinstance(chosen, cal.PowerCalibration)
              else f"weights = {np.round(np.array(getattr(chosen, 'weights', [])), 3).tolist()}, "
                   f"bias = {np.round(np.array(getattr(chosen, 'bias', [])), 3).tolist()}")
    text = f"""# Phase 3a: calibrating the Bayesian model

Generated by `scripts/calibration_phase3a.py`. Predictions: walk-forward backtests on
GitHub (tuning seasons 2021/22 and 2022/23; test seasons 2023/24 to 2025/26), model
`dc_bayes_v1` (shots on target, NumPyro). Slope: observed home-win rate against mean
forecast over five equal groups; 1 is perfect, above 1 is too timid.

## Step 1: choose the method (fit 2021/22, validate 2022/23)

{table(choice_rows)}

Chosen: **{best}**.

## Step 2: refit on both tuning seasons

{params}

## Step 3: test seasons, scored once

{table(test_rows)}

### Differences with 95% paired bootstrap intervals (negative = calibration helps)

{table(diffs)}

### By league

{table(by_league)}

### Goals markets after rescaling the scoreline table

{table(goal_rows)}

## Decision rule (spec S5.6)

Apply only if it improves out-of-sample log loss. Here "improves" means the whole 95%
interval of the change lies below zero. Test log loss change:
{diffs[1]['calibrated_minus_raw']:+.4f} (interval {diffs[1]['ci_low']:+.4f} to
{diffs[1]['ci_high']:+.4f}). **{'Clear improvement.' if improves else
'No clear improvement: do not apply this fixed map.'}**

Why: in the tuning seasons the model was not timid (slope near 1 on 2022/23), so a map
learned there barely changes anything. The timidity appeared from 2023/24.
"""
    OUT_MD.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
