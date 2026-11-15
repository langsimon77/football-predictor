"""Test of one accuracy candidate: recalibrate the yes/no football markets.

Rules are fixed in data/audit/preregistration_recalibration_2026_11.md, written and
committed before this script was run on the stored forecasts. Run once:

    uv run python scripts/recalibration_test.py

For each test season, league and market, a logistic curve a + b * log-odds is fitted on that
league's forecasts and results from the earlier stored seasons only, then applied to the
test season. Nothing here changes a live forecast.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accuracy_baseline as base  # noqa: E402

from fp import ROOT  # noqa: E402
from fp.evaluate import metrics  # noqa: E402

REPORT = ROOT / "reports" / "recalibration_test_2026_11.md"
RESULTS = ROOT / "data" / "audit" / "recalibration_test_2026_11.json"
TEST = (2023, 2024, 2025)


def fit(p: np.ndarray, y: np.ndarray, steps: int = 50) -> tuple[float, float]:
    """Intercept and slope of the logistic curve of the result on the forecast's log-odds."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.column_stack([np.ones_like(p), np.log(p / (1 - p))])
    b = np.zeros(2)
    for _ in range(steps):
        q = 1 / (1 + np.exp(-(x @ b)))
        step = np.linalg.solve(x.T @ (x * (q * (1 - q))[:, None]) + 1e-9 * np.eye(2),
                               x.T @ (y - q))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(b[0]), float(b[1])


def apply(p: np.ndarray, a: float, b: float) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return 1 / (1 + np.exp(-(a + b * np.log(p / (1 - p)))))


def walk_forward(long: pd.DataFrame) -> pd.DataFrame:
    """Adds p_new for the test seasons: fitted on earlier seasons of the same league and
    market, never on the season being forecast or a later one."""
    out = []
    for (_lg, _mk), g in long.groupby(["league", "market"]):
        for season in TEST:
            past, now = g[g["season"] < season], g[g["season"] == season]
            if len(now) == 0 or len(past) < 300:
                continue
            a, b = fit(past["p"].to_numpy(), past["happened"].to_numpy())
            out.append(now.assign(p_new=apply(now["p"].to_numpy(), a, b), fit_a=a, fit_b=b))
    return pd.concat(out, ignore_index=True)


def paired(diff: np.ndarray, seed: int = 0, n_boot: int = 2000) -> dict:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    lo, hi = np.quantile(diff[idx].mean(axis=1), [0.025, 0.975])
    return {"mean": float(diff.mean()), "lo": float(lo), "hi": float(hi), "n": int(len(diff))}


def score(wf: pd.DataFrame) -> dict:
    y = wf["happened"].to_numpy(bool)
    wf = wf.assign(diff=metrics.binary_log_loss(wf["p_new"].to_numpy(), y)
                   - metrics.binary_log_loss(wf["p"].to_numpy(), y))
    out = {}
    for market, g in wf.groupby("market"):
        per = {lg: paired(x["diff"].to_numpy()) for lg, x in g.groupby("league")}
        pooled = paired(g["diff"].to_numpy())
        out[market] = {
            "pooled": pooled, "leagues": per,
            "slope_before": base.binary_slope(g["p"].to_numpy(), g["happened"].to_numpy()),
            "slope_after": base.binary_slope(g["p_new"].to_numpy(), g["happened"].to_numpy()),
            "pass": bool(pooled["hi"] < 0 and all(v["lo"] <= 0 for v in per.values()))}
    return out


def main() -> int:
    long, _ = base.binary_markets()
    res = score(walk_forward(long))
    RESULTS.write_text(json.dumps(res, indent=1), encoding="utf-8")
    lines = ["# Recalibrating the yes/no football markets: test result (November 2026)", "",
             "Rules: `data/audit/preregistration_recalibration_2026_11.md`, committed before "
             "this test ran. One run. [V] verified by `scripts/recalibration_test.py`.", "",
             "Change in log loss, recalibrated minus published (below 0 is better), test "
             "seasons 2023/24 to 2025/26. A market passes when the whole pooled 95% interval "
             "is below 0 and no league is clearly worse.", "",
             "| Market | Matches | Pooled change (95% interval) | By league | Slope before | "
             "Slope after | Result |", "|---|---|---|---|---|---|---|"]
    for market in base.MARKET_ORDER:
        r = res[market]
        per = "; ".join(f"{base.NAMES[lg]} {v['mean']:+.4f} ({v['lo']:+.4f} to {v['hi']:+.4f})"
                        for lg, v in r["leagues"].items())
        lines.append(f"| {market} | {r['pooled']['n']:,} | {r['pooled']['mean']:+.4f} "
                     f"({r['pooled']['lo']:+.4f} to {r['pooled']['hi']:+.4f}) | {per} | "
                     f"{r['slope_before']:.2f} | {r['slope_after']:.2f} | "
                     f"{'**pass**' if r['pass'] else 'fail'} |")
    lines += ["", "No live forecast changed. A passing market is a candidate for Lang's "
              "decision only.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
