"""The monthly run (spec S10; spec S5.6 step 3 with PRD item 10).

1. Calibration check on the published home, draw, away forecast. The map is a
   Dirichlet calibration (the three-outcome version of beta calibration, PRD
   item 10), fitted on the backtest pool plus live results with recent matches
   counting more, and tested on the most recent held-out slice. It only reports:
   applying a map changes live forecasts, which needs Lang's approval.
2. Refresh the live-record section of docs/MODEL_CARD.md.

    python -m fp.pipeline.monthly [--now 2026-11-01T06:00Z] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT, ledger
from fp.ensemble import calibration as cal
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.ingest import matches as build
from fp.pipeline import data as data_pipeline
from fp.pipeline import weekly

MONTHLY = ROOT / "docs" / "monthly"
CHECK = ROOT / "data" / "calibration" / "monthly_check.json"
CARD = ROOT / "docs" / "MODEL_CARD.md"
START, END = "<!-- live-record:start -->", "<!-- live-record:end -->"
HOLDOUT_LIVE_DAYS = 30
MIN_HOLDOUT = 100
HOLDOUT_FALLBACK = 380
PROBS = ["p_home", "p_draw", "p_away"]


def pool(live: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_parquet(weekly.BASELINES)[["kickoff_utc", "outcome", *PROBS]]
    parts = [base.assign(source="backtest")]
    if len(live):
        parts.append(live[["kickoff_utc", "outcome", *PROBS]].assign(source="live"))
    out = pd.concat(parts, ignore_index=True)
    out["kickoff_utc"] = pd.to_datetime(out["kickoff_utc"], utc=True)
    return out.dropna(subset=PROBS).sort_values("kickoff_utc").reset_index(drop=True)


def calibration_check(frame: pd.DataFrame, now: pd.Timestamp) -> dict:
    live = frame[frame["source"] == "live"]
    recent = live[live["kickoff_utc"] > now - pd.Timedelta(days=HOLDOUT_LIVE_DAYS)]
    held = recent if len(recent) >= MIN_HOLDOUT else frame.tail(HOLDOUT_FALLBACK)
    train = frame[frame["kickoff_utc"] < held["kickoff_utc"].min()]
    age = (now - train["kickoff_utc"]).dt.days.to_numpy()
    keep = np.exp(-np.log(2) * age / weekly.HALF_LIFE_DAYS) > 0.25  # last two years or so
    train = train[keep]
    p_train, y_train = train[PROBS].to_numpy(float), train["outcome"].to_numpy(int)
    p_held, y_held = held[PROBS].to_numpy(float), held["outcome"].to_numpy(int)
    fitted = cal.DirichletCalibration.fit(p_train, y_train, penalty=0.01)
    q = fitted.apply(p_held)
    d = metrics.log_loss(q, y_held) - metrics.log_loss(p_held, y_held)
    lo, hi = bt.paired_ci(d)
    return {
        "date": f"{now:%Y-%m-%d}", "method": "dirichlet (beta calibration, 3 outcomes)",
        "train_matches": int(len(train)), "held_out_matches": int(len(held)),
        "held_out": "live, last 30 days" if held is recent else "most recent 380 matches",
        "log_loss_change": float(d.mean()), "ci_low": lo, "ci_high": hi,
        "slope_raw": cal.calibration_slope(p_held[:, 0], (y_held == 0).astype(float)),
        "slope_calibrated": cal.calibration_slope(q[:, 0], (y_held == 0).astype(float)),
        "passes_strict_rule": bool(hi < 0),
        "weights": np.round(np.array(fitted.weights), 4).tolist(),
        "bias": np.round(np.array(fitted.bias), 4).tolist(),
    }


def live_record(live: pd.DataFrame, now: pd.Timestamp) -> str:
    if live.empty:
        return (f"{START}\n## Live record, 2026/27\n\nNo locked forecast scored yet "
                f"(as of {now:%d %b %Y}).\n{END}")
    table = weekly.scores(live)
    tiers = live.assign(tier=live["tiers"].map(lambda s: json.loads(s).get("1x2", "")
                                               if isinstance(s, str) else ""))
    tiers["hit"] = tiers[PROBS].to_numpy(float).argmax(1) == tiers["outcome"]
    tiers["fav"] = tiers[PROBS].max(axis=1)
    t = tiers[tiers["tier"] != ""].groupby("tier").agg(matches=("hit", "size"),
                                                       promised=("fav", "mean"),
                                                       won=("hit", "mean")).reset_index()
    return (f"{START}\n## Live record, 2026/27\n\nUpdated by the monthly run on "
            f"{now:%d %b %Y} [V: ledger]. Home, draw, away; lower is better.\n\n"
            f"{weekly.table(table)}\n\nConfidence tiers (published forecast):\n\n"
            f"{weekly.table(t)}\n{END}")


def refresh_card(section: str) -> None:
    text = CARD.read_text(encoding="utf-8")
    if START in text and END in text:
        before, rest = text.split(START, 1)
        after = rest.split(END, 1)[1]
        text = before + section + after
    else:
        text = text.rstrip("\n") + "\n\n" + section + "\n"
    CARD.write_text(text, encoding="utf-8")


def run(now: pd.Timestamp, dry_run: bool = False, pred_path: Path = ledger.PREDICTIONS,
        results_path: Path = ledger.RESULTS) -> dict:
    matches = pd.read_parquet(build.PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(build.PROCESSED / "fixtures.parquet")
    pred = ledger.load(pred_path)
    results = pd.read_parquet(results_path) if results_path.exists() else pd.DataFrame()
    live = weekly.live_frame(pred, results, matches, fixtures)
    check = calibration_check(pool(live), now)
    change = (f"{check['log_loss_change']:+.4f} (interval {check['ci_low']:+.4f} to "
              f"{check['ci_high']:+.4f})")
    slopes = f"{check['slope_raw']:.2f}, {check['slope_calibrated']:.2f}"
    report = f"""# Monthly report, {now:%B %Y}

Generated by `python -m fp.pipeline.monthly` on {now:%d %b %Y}.

## Calibration check (published home, draw, away)

| Item | Value |
|---|---|
| Method | {check['method']} |
| Fitted on | {check['train_matches']} matches (backtest and live, recent weighted) |
| Tested on | {check['held_out_matches']} matches ({check['held_out']}) |
| Log loss change | {change} |
| Calibration slope, raw then calibrated | {slopes} |
| Passes the strict rule | {'yes' if check['passes_strict_rule'] else 'no'} |

The strict rule: the whole 95% interval of the change must be below zero. A pass is a
proposal for Lang, not an automatic change: live forecasts use no calibration map today.

{live_record(live, now).replace(START, '').replace(END, '')}
"""
    if dry_run:
        print(report)
        return check
    MONTHLY.mkdir(parents=True, exist_ok=True)
    (MONTHLY / f"{now:%Y-%m}.md").write_text(report, encoding="utf-8")
    CHECK.write_text(json.dumps(check, indent=1) + "\n", encoding="utf-8")
    refresh_card(live_record(live, now))
    if check["passes_strict_rule"]:
        from fp.news import github
        if github.available():
            github.create_issue(f"Calibration proposal: {now:%B %Y}",
                                "The monthly calibration check passed the strict rule. "
                                f"Details in `docs/monthly/{now:%Y-%m}.md`. Approve before "
                                "any map is applied to live forecasts.")
    return check


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--ledger", type=Path, default=ledger.PREDICTIONS)
    args = ap.parse_args(argv)
    data_pipeline.main(skip_download=args.offline)
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp(datetime.now(UTC))
    now = now.tz_convert("UTC") if now.tzinfo else now.tz_localize("UTC")
    check = run(now, args.dry_run, args.ledger, args.ledger.parent / "results.parquet")
    print(f"calibration check: change {check['log_loss_change']:+.4f}, "
          f"passes strict rule: {check['passes_strict_rule']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
