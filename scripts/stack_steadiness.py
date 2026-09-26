"""Does a pull towards the current weights steady the weekly stack re-weight
without costing accuracy? (Test plan fixed in docs/DECISIONS.md, 26 Sep 2026.)

The live weekly rule is replayed week by week: each Monday, the target weights
are fitted on every result known by then (recent matches counting more, half-life
one year), and the weights move towards the target by at most 10 points, never
below 5%, only after 60 scored matches in the replayed seasons.

1. Choose λ on a replay of 2022/23 (start: weights fitted on 2021/22).
2. Test once on 2023/24 to 2025/26 (start: the live stack weights), against λ = 0.

    uv run python scripts/stack_steadiness.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ensemble import stacking
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.ingest.matches import PROCESSED

BASELINES = ROOT / "data" / "backtests" / "baselines_2021_2025.parquet"
STACK = ROOT / "data" / "stacking" / "stack_1x2.json"
OUT = ROOT / "reports" / "stack_steadiness.md"
MODELS = ["elo", "dc", "bdc", "multinomial", "ordered_logit", "random_forest", "xgboost"]
PREFIX = {"bdc": "p"}
GRID = [0.003, 0.01, 0.03, 0.1]
HALF_LIFE = 365
NOISE = 1e-6
MARGIN = 0.001


def component(frame: pd.DataFrame, m: str) -> np.ndarray:
    return frame[[f"{PREFIX.get(m, m)}_{k}" for k in ("home", "draw", "away")]].to_numpy(float)


def replay(frame: pd.DataFrame, seasons: list[int], start: np.ndarray, pull: float,
           sensitivity: bool = False) -> tuple[np.ndarray, pd.DataFrame]:
    probs = {m: component(frame, m) for m in MODELS}
    y = frame["outcome"].to_numpy(int)
    kickoff = frame["kickoff_utc"]
    in_replay = frame["season"].isin(seasons).to_numpy()
    week = (frame["lock_utc"].dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
            .dt.tz_localize("UTC"))
    out = np.full((len(frame), 3), np.nan)
    w = start.copy()
    rng = np.random.default_rng(0)
    rows = []
    for wk in sorted(week[in_replay].unique()):
        known = (frame["result_available_utc"] <= wk).to_numpy()
        n_live = int((known & in_replay).sum())
        target = sens = None
        if n_live >= stacking.MIN_LIVE_PREDICTIONS:
            age = (wk - kickoff[known]).dt.days.to_numpy()
            decay = 0.5 ** (age / HALF_LIFE)
            pool = {m: p[known] for m, p in probs.items()}
            target = stacking.fit(pool, y[known], sample_weight=decay, anchor=w,
                                  pull=pull).weights
            if sensitivity:
                noisy = {}
                for m, p in pool.items():
                    q = p * np.exp(NOISE * rng.standard_normal(p.shape))
                    noisy[m] = q / q.sum(axis=1, keepdims=True)
                again = stacking.fit(noisy, y[known], sample_weight=decay, anchor=w,
                                     pull=pull).weights
                sens = float(np.abs(again - target).sum())
            new = stacking.guarded_update(w, target, n_live)
        else:
            new = w
        move = float(np.abs(new - w).sum())
        w = new
        now_rows = in_replay & (week == wk).to_numpy()
        out[now_rows] = sum(wi * probs[m][now_rows] for m, wi in zip(MODELS, w, strict=True))
        rows.append({"week": wk, "n_live": n_live, "move": move, "sensitivity": sens,
                     **{f"t_{m}": (None if target is None else float(v))
                        for m, v in zip(MODELS, target if target is not None else [None] * 7,
                                        strict=True)},
                     **{f"w_{m}": float(v) for m, v in zip(MODELS, w, strict=True)}})
    return out, pd.DataFrame(rows)


def jitter(hist: pd.DataFrame) -> float:
    t = hist[[f"t_{m}" for m in MODELS]].dropna().to_numpy(float)
    return float(np.abs(np.diff(t, axis=0)).sum(axis=1).mean()) if len(t) > 1 else float("nan")


def table(rows: list[dict]) -> str:
    frame = pd.DataFrame(rows)
    head = "| " + " | ".join(frame.columns) + " |\n|" + "---|" * len(frame.columns)
    return head + "\n" + "\n".join("| " + " | ".join(f"{v:.4f}" if isinstance(v, float)
                                                     else str(v) for v in r) + " |"
                                   for r in frame.itertuples(index=False))


def main() -> int:
    frame = pd.read_parquet(BASELINES)
    matches = pd.read_parquet(PROCESSED / "matches.parquet").set_index("match_id")
    frame["result_available_utc"] = frame["match_id"].map(matches["result_available_utc"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["lock_utc"] = pd.to_datetime(frame["lock_utc"], utc=True)
    frame = frame.sort_values("lock_utc").reset_index(drop=True)
    y = frame["outcome"].to_numpy(int)

    # 1. Choose λ on 2022/23.
    first = (frame["season"] == 2021).to_numpy()
    start_22 = stacking.fit({m: component(frame, m)[first] for m in MODELS}, y[first]).weights
    sel = (frame["season"] == 2022).to_numpy()
    choice = []
    for pull in [0.0, *GRID]:
        p, hist = replay(frame, [2022], start_22, pull)
        choice.append({"pull": pull, "log_loss": float(metrics.log_loss(p[sel], y[sel]).mean()),
                       "target_jitter": jitter(hist)})
    best = min((r for r in choice if r["pull"] > 0),
               key=lambda r: (round(r["log_loss"], 6), -r["pull"]))["pull"]

    # 2. Test once on 2023/24 to 2025/26.
    test = frame["season"].isin([2023, 2024, 2025]).to_numpy()
    start = np.asarray(json.loads(STACK.read_text(encoding="utf-8"))["weights"], dtype=float)
    p0, h0 = replay(frame, [2023, 2024, 2025], start, 0.0, sensitivity=True)
    p1, h1 = replay(frame, [2023, 2024, 2025], start, best, sensitivity=True)
    d = metrics.log_loss(p1[test], y[test]) - metrics.log_loss(p0[test], y[test])
    lo, hi = bt.paired_ci(d)
    rows = []
    for name, p, h in (("current (no pull)", p0, h0), (f"steadier (pull {best})", p1, h1)):
        rows.append({"method": name, "log_loss": float(metrics.log_loss(p[test], y[test]).mean()),
                     "rps": float(metrics.rps(p[test], y[test]).mean()),
                     "target_jitter": jitter(h), "noise_sensitivity": float(h["sensitivity"]
                                                                           .dropna().mean()),
                     "mean_weekly_move": float(h["move"].mean())})
    accuracy_ok = hi < MARGIN
    steadier = (rows[1]["target_jitter"] <= 0.5 * rows[0]["target_jitter"]
                and rows[1]["noise_sensitivity"] <= 0.5 * rows[0]["noise_sensitivity"])
    adopt = accuracy_ok and steadier
    last0 = {m: round(float(h0[f"w_{m}"].iloc[-1]), 3) for m in MODELS}
    last1 = {m: round(float(h1[f"w_{m}"].iloc[-1]), 3) for m in MODELS}
    text = f"""# Steadier stack fit: replay test

Generated by `scripts/stack_steadiness.py`. Test plan fixed beforehand in
`docs/DECISIONS.md` (26 Sep 2026). Every Monday the target weights are refitted on
all results known by then (half-life one year); the weights move towards the target
by at most 10 points, never below 5%, after 60 scored replay matches. The candidate
adds `pull x sum((w - current)^2)` to the fitted loss.

## Step 1: choose the pull on 2022/23 (start: weights fitted on 2021/22)

{table(choice)}

Chosen: **{best}**. `target_jitter`: average week-to-week change in the target
weights (sum of absolute changes).

## Step 2: test once on 2023/24 to 2025/26 (start: the live stack weights)

{table(rows)}

Log loss change, steadier minus current: {d.mean():+.5f} (95% interval {lo:+.5f} to
{hi:+.5f}). `noise_sensitivity`: how far the target moves when every input probability
is nudged by one part in a million, the size of rerun noise.

Weights at the end of 2025/26, current: {last0}

Weights at the end of 2025/26, steadier: {last1}

## Decision rule

- Accuracy no worse (upper end below +{MARGIN}): **{'yes' if accuracy_ok else 'no'}**
- At least twice as steady on jitter and noise sensitivity: **{'yes' if steadier else 'no'}**

**{'Adopt the steadier fit.' if adopt else 'Do not adopt: keep the current fit.'}**
"""
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
