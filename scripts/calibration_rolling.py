"""Phase 3a, step 4: walk-forward monthly calibration (spec S5.6 step 3).

The fixed map from the tuning seasons could not fix a timidity that only appeared
from 2023/24. This tests the spec's own design: refit the map each month on the
trailing window of predictions whose results were known before that month, then
apply it to that month's matches. Settings fixed in advance: power scaling; window
of one season's matches; pooled across leagues, or per league. Both are reported.
The test seasons were already seen in step 3, so this is a second look.

    uv run python scripts/calibration_rolling.py TUNE_DIR TEST_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fp.ensemble import calibration as cal
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.ingest.matches import PROCESSED

sys.path.insert(0, str(Path(__file__).parent))
from calibration_phase3a import goal_markets, load, outcomes, probs, scores, table  # noqa: E402


def rolling(pool: pd.DataFrame, test_mask: pd.Series, per_league: bool) -> np.ndarray:
    """Calibrated probabilities for test rows, each month fitted only on the past."""
    out = probs(pool).copy()
    month = pool["lock_utc"].dt.tz_convert(None).dt.to_period("M")
    groups = pool.groupby("league") if per_league else [("all", pool)]
    window = 380 if per_league else 760
    for _, g in groups:
        for period in sorted(set(month[g.index][test_mask[g.index]])):
            start = period.start_time.tz_localize("UTC")
            past = g[g["result_available_utc"] <= start].sort_values("lock_utc").tail(window)
            now = g.index[(month[g.index] == period) & test_mask[g.index]]
            fitted = cal.PowerCalibration.fit(probs(past), past["y"].to_numpy())
            out[pool.index.get_indexer(now)] = fitted.apply(probs(pool.loc[now]))
    return out[test_mask.to_numpy()]


def main(tune_dir: Path, test_dir: Path) -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pool = pd.concat([load(tune_dir, matches), load(test_dir, matches)], ignore_index=True)
    pool = pool.join(matches.set_index("match_id")["result_available_utc"], on="match_id")
    test_mask = pool["season"] >= 2023
    test = pool[test_mask]
    y = test["y"].to_numpy()
    raw = probs(test)
    rows, diffs = [{"forecast": "raw", **scores(raw, y)}], []
    variants = {"monthly, pooled": rolling(pool, test_mask, per_league=False),
                "monthly, per league": rolling(pool, test_mask, per_league=True)}
    happened = outcomes(test)
    raw_goals = goal_markets(test, None)
    goal_rows = []
    for name, q in variants.items():
        rows.append({"forecast": name, **scores(q, y)})
        for metric_name, fn in (("rps", metrics.rps), ("log_loss", metrics.log_loss)):
            d = fn(q, y) - fn(raw, y)
            lo, hi = bt.paired_ci(d)
            diffs.append({"variant": name, "metric": metric_name, "minus_raw": float(d.mean()),
                          "ci_low": lo, "ci_high": hi})
        rescaled = goal_markets(test, q)
        for k in ("p_over_2_5", "p_btts"):
            d = (metrics.binary_log_loss(rescaled[k].to_numpy(), happened[k])
                 - metrics.binary_log_loss(raw_goals[k].to_numpy(), happened[k]))
            lo, hi = bt.paired_ci(d)
            goal_rows.append({"variant": name, "market": k, "minus_raw": float(d.mean()),
                              "ci_low": lo, "ci_high": hi})
    text = f"""
## Step 4: walk-forward monthly calibration (spec S5.6 design; second look at test seasons)

Each month's map is fitted only on predictions whose results were known before the
month began: power scaling, trailing window of 760 matches pooled or 380 per league.

{table(rows)}

### Differences from raw with 95% paired bootstrap intervals (negative = calibration helps)

{table(diffs)}

### Goals markets after rescaling the scoreline table

{table(goal_rows)}
"""
    print(text)
    with open(Path(__file__).resolve().parents[1] / "reports" / "calibration_phase3a.md", "a",
              encoding="utf-8") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
