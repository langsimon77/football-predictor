"""The weekly run (spec S10: Monday 06:00 UTC; spec S5.6 steps 2, 4, 5).

1. Score the week and the season so far: the published model against Elo, base
   rates, and the market, plus the shadows.
2. Miss audit: the five biggest surprises per league, causes tagged from data.
3. Drift monitor: last four gameweeks against the backtest norm, per market.
4. Stack re-weight (shadow stack): target weights from the backtest pool plus
   live results, recent matches counting more (half-life one year, PRD item 10);
   the weights move towards the target by at most 10 points, never below 5%,
   and only after 60 scored live matches. Every change is logged with evidence.
5. Write docs/weekly/<date>.md. Open an Issue only if drift is flagged.

    python -m fp.pipeline.weekly [--now 2026-10-19T06:00Z] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from fp import ROOT, ledger
from fp.ensemble import stacking
from fp.evaluate import drift, metrics, miss_audit
from fp.ingest import matches as build
from fp.pipeline import data as data_pipeline

log = logging.getLogger(__name__)

HALF_LIFE_DAYS = 365
STACK_FILE = ROOT / "data" / "stacking" / "stack_1x2.json"
STACK_HISTORY = ROOT / "data" / "stacking" / "history.csv"
AUDIT = ROOT / "data" / "audit" / "misses.csv"
DRIFT = ROOT / "data" / "audit" / "drift.json"
BASELINES = ROOT / "data" / "backtests" / "baselines_2021_2025.parquet"
WEEKLY = ROOT / "docs" / "weekly"
ANSWERS = ROOT / "data" / "manual" / "answers.yaml"
PROBS = ["p_home", "p_draw", "p_away"]
# Stack component -> ledger model (the Bayesian one without news, as in the backtest).
LEDGER_NAME = {"elo": "elo_v0", "dc": "dc_mle_v0", "bdc": "dc_bayes_v1",
               "ordered_logit": "ordered_logit_v1", "multinomial": "multinomial_v1",
               "random_forest": "random_forest_v1", "xgboost": "xgboost_v1"}


# ---------------------------------------------------------------- live data

def live_frame(pred: pd.DataFrame, results: pd.DataFrame, matches: pd.DataFrame,
               fixtures: pd.DataFrame) -> pd.DataFrame:
    """One row per scored match: the published forecast (latest lock), every other
    model's home, draw, away, results, base rates at lock, and the gameweek."""
    if pred.empty or results.empty:
        return pd.DataFrame()
    latest = pred.sort_values("lock_utc").drop_duplicates(["match_id", "model_name"], keep="last")
    primary = latest[latest["model_name"] == "dc_bayes_v1"].set_index("match_id")
    res = results.drop_duplicates("match_id", keep="last").set_index("match_id")
    primary = primary[primary.index.isin(res.index)]
    if primary.empty:
        return pd.DataFrame()
    frame = primary.reset_index()
    for col in ("home_goals", "away_goals", "home_corners", "away_corners", "home_yellows",
                "away_yellows", "home_reds", "away_reds"):
        frame[col] = frame["match_id"].map(res[col]) if col in res else np.nan
    wide = latest.set_index(["match_id", "model_name"])[PROBS]
    for model in latest["model_name"].unique():
        if model == "dc_bayes_v1":
            continue
        part = wide.xs(model, level="model_name")
        for k, c in zip(("home", "draw", "away"), PROBS, strict=True):
            frame[f"{model}_{k}"] = frame["match_id"].map(part[c])
    for k in ("home", "draw", "away"):  # benchmark columns used by drift.MARKETS
        frame[f"elo_{k}"] = frame.get(f"elo_v0_{k}")
    frame = frame.merge(drift.base_rates(matches, frame[["match_id", "league", "lock_utc"]]),
                        on="match_id", how="left")
    frame["round"] = frame["match_id"].map(fixtures.set_index("match_id")["round"])
    m = matches.set_index("match_id")
    for name, prefix in (("market_friday", "odds_avg_pre"), ("market_close", "odds_pin_close"),
                         ("market_bfe", "odds_bfe_close")):
        cols = [f"{prefix}_{k}" for k in ("home", "draw", "away")]
        if set(cols) <= set(m.columns):
            odds = frame["match_id"].map(lambda i, c=cols: tuple(m.loc[i, c]) if i in m.index
                                         else (np.nan,) * 3)
            p = metrics.demargin_power(np.array(odds.tolist(), dtype=float))
            for j, k in enumerate(("home", "draw", "away")):
                frame[f"{name}_{k}"] = p[:, j]
    for k in ("home", "draw", "away"):  # sharp closing: Pinnacle, else Betfair
        if f"market_close_{k}" in frame and f"market_bfe_{k}" in frame:
            frame[f"market_close_{k}"] = frame[f"market_close_{k}"].fillna(frame[f"market_bfe_{k}"])
    return drift.add_outcomes(frame)


def scores(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = frame["outcome"].to_numpy(int)
    for label, prefix in (("Published (Bayesian)", None), ("Elo", "elo_v0"),
                          ("Base rates", "base"), ("Stack (shadow)", "stack_v1"),
                          ("Market, Friday", "market_friday"), ("Market, closing", "market_close")):
        cols = PROBS if prefix is None else [f"{prefix}_{k}" for k in ("home", "draw", "away")]
        if not set(cols) <= set(frame.columns):
            continue
        ok = frame[cols].notna().all(axis=1).to_numpy()
        if not ok.any():
            continue
        p = frame.loc[ok, cols].to_numpy(float)
        rows.append({"forecast": label, "matches": int(ok.sum()),
                     "rps": float(metrics.rps(p, y[ok]).mean()),
                     "log_loss": float(metrics.log_loss(p, y[ok]).mean())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- stack

def reweight(live: pd.DataFrame, now: pd.Timestamp, dry_run: bool) -> dict:
    stack = json.loads(STACK_FILE.read_text(encoding="utf-8"))
    models, current = stack["models"], np.asarray(stack["weights"], dtype=float)
    base = pd.read_parquet(BASELINES)
    pools, ages, ys = [], [], []
    prefix = {"bdc": "p"}  # baselines file: Bayesian as p_*, others as <model>_*
    bt = {m: base[[f"{prefix.get(m, m)}_{k}" for k in ("home", "draw", "away")]]
          .to_numpy(float) for m in models}
    pools.append(bt)
    ages.append(((now - pd.to_datetime(base["kickoff_utc"], utc=True)).dt.days).to_numpy())
    ys.append(base["outcome"].to_numpy(int))
    n_live = 0
    if len(live):
        cols = {}
        for m in models:
            name = LEDGER_NAME[m]
            if m == "bdc":
                plain = [f"dc_bayes_v1_nonews_{k}" for k in ("home", "draw", "away")]
                use = live[PROBS].to_numpy(float)
                if set(plain) <= set(live.columns):
                    alt = live[plain].to_numpy(float)
                    use = np.where(np.isfinite(alt), alt, use)
                cols[m] = use
            else:
                c = [f"{name}_{k}" for k in ("home", "draw", "away")]
                cols[m] = (live[c].to_numpy(float) if set(c) <= set(live.columns)
                           else np.full((len(live), 3), np.nan))
        ok = np.all([np.isfinite(v).all(axis=1) for v in cols.values()], axis=0)
        n_live = int(ok.sum())
        if n_live:
            pools.append({m: v[ok] for m, v in cols.items()})
            ages.append(((now - pd.to_datetime(live.loc[ok, "kickoff_utc"], utc=True)).dt.days)
                        .to_numpy())
            ys.append(live.loc[ok, "outcome"].to_numpy(int))
    probs = {m: np.concatenate([p[m] for p in pools]) for m in models}
    y = np.concatenate(ys)
    decay = np.exp(-np.log(2) * np.concatenate(ages) / HALF_LIFE_DAYS)
    target = stacking.fit(probs, y, sample_weight=decay).weights
    new = stacking.guarded_update(current, target, n_live)

    def pooled_loss(w: np.ndarray) -> float:
        p = sum(wi * probs[m] for m, wi in zip(models, w, strict=True))
        return float(np.sum(decay * metrics.log_loss(p, y)) / decay.sum())

    moved = bool(np.abs(new - current).max() > 1e-9)
    record = {"date": f"{now:%Y-%m-%d}", "n_live": n_live, "moved": moved,
              "loss_current": round(pooled_loss(current), 5),
              "loss_target": round(pooled_loss(target), 5),
              "loss_new": round(pooled_loss(new), 5),
              **{f"w_{m}": round(float(w), 4) for m, w in zip(models, new, strict=True)},
              **{f"target_{m}": round(float(w), 4) for m, w in zip(models, target, strict=True)}}
    if not dry_run:
        STACK_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        hist = pd.read_csv(STACK_HISTORY) if STACK_HISTORY.exists() else pd.DataFrame()
        hist = pd.concat([hist[hist.get("date", pd.Series(dtype=str)) != record["date"]]
                          if len(hist) else hist, pd.DataFrame([record])], ignore_index=True)
        hist.to_csv(STACK_HISTORY, index=False)
        if moved:
            stack["weights"] = [round(float(w), 4) for w in new]
            stack["updated"] = record["date"]
            STACK_FILE.write_text(json.dumps(stack, indent=2) + "\n", encoding="utf-8")
    return record


# ---------------------------------------------------------------- report

def table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_None._"
    head = "| " + " | ".join(map(str, frame.columns)) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(
        "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v))
        else f"{v:.4f}" if isinstance(v, float) else str(v) for v in r) + " |"
        for r in frame.itertuples(index=False))
    return head + "\n" + body


def stack_table(record: dict) -> pd.DataFrame:
    models = [k[2:] for k in record if k.startswith("w_")]
    return pd.DataFrame({"model": models,
                         "target": [record[f"target_{m}"] for m in models],
                         "weight after this week": [record[f"w_{m}"] for m in models]})


def news_effect(frame: pd.DataFrame) -> str:
    cols = [f"dc_bayes_v1_nonews_{k}" for k in ("home", "draw", "away")]
    if not set(cols) <= set(frame.columns):
        return "No forecast has been moved by team news yet."
    f = frame.dropna(subset=cols)
    if f.empty:
        return "No forecast has been moved by team news yet."
    y = f["outcome"].to_numpy(int)
    d = metrics.log_loss(f[PROBS].to_numpy(float), y) - metrics.log_loss(f[cols].to_numpy(float), y)
    return (f"{len(f)} scored matches had news applied. Log loss with news minus without: "
            f"{d.mean():+.4f} (negative means news helped). The formal test comes after 10 "
            "gameweeks (spec S6.5).")


def questions_line(now: pd.Timestamp) -> str:
    if not ANSWERS.exists():
        return "No questions answered yet."
    rows = pd.DataFrame(yaml.safe_load(ANSWERS.read_text(encoding="utf-8")) or [])
    if rows.empty:
        return "No questions answered yet."
    rows["used"] = pd.to_datetime(rows["used_at_utc"], utc=True)
    week = rows[rows["used"] > now - pd.Timedelta(days=7)]
    if week.empty:
        return "No questions were due this week."
    answered = (week["status"] == "answered").mean()
    return f"{len(week)} club questions were due this week; {answered:.0%} answered."


def run(now: pd.Timestamp, dry_run: bool = False, pred_path: Path = ledger.PREDICTIONS,
        results_path: Path = ledger.RESULTS) -> Path:
    matches = pd.read_parquet(build.PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(build.PROCESSED / "fixtures.parquet")
    pred = ledger.load(pred_path)
    results = pd.read_parquet(results_path) if results_path.exists() else pd.DataFrame()
    live = live_frame(pred, results, matches, fixtures)
    since = now - pd.Timedelta(days=7)
    week = live[pd.to_datetime(live["kickoff_utc"], utc=True) > since] if len(live) else live
    label = f"{now:%Y-%m-%d}"

    audit_rows = miss_audit.audit(week, label) if len(week) else pd.DataFrame()
    history = pd.read_csv(AUDIT) if AUDIT.exists() else pd.DataFrame()
    if len(audit_rows):
        history = pd.concat([history[history["week"] != label] if len(history) else history,
                             audit_rows], ignore_index=True)
    fix = miss_audit.proposal(history)

    baseline = pd.read_parquet(BASELINES)
    baseline = baseline[baseline["season"] >= 2023]
    recent = drift.last_rounds(live) if len(live) else live
    checks = drift.check(recent, baseline) if len(recent) else []
    flagged = [c for c in checks if c.flagged]

    stack = reweight(live, now, dry_run)

    misses = (audit_rows.assign(match=audit_rows["home_id"] + " v " + audit_rows["away_id"],
                                score=audit_rows["home_goals"].astype(int).astype(str) + "-"
                                + audit_rows["away_goals"].astype(int).astype(str))
              [["league", "match", "score", "chance_given", "tags"]]
              if len(audit_rows) else pd.DataFrame())
    drift_table = pd.DataFrame(drift.as_records(checks)) if checks else pd.DataFrame()
    text = f"""# Weekly report, {now:%a %d %b %Y}

Generated by `python -m fp.pipeline.weekly`. Week: kickoffs after {since:%a %d %b %H:%M} UTC.
Lower scores are better.

## This week

{table(scores(week)) if len(week) else "_No scored matches this week._"}

## Season so far

{table(scores(live)) if len(live) else "_No scored matches yet._"}

## Team news

{news_effect(live) if len(live) else "No scored matches yet."} {questions_line(now)}

## Miss audit: five biggest surprises per league

{table(misses)}

Causes are tagged from data only (PRD item 12). Model error is judged over many
matches, not from one.

{"**Proposed fix (awaiting Lang):** " + fix if fix else "No recurring controllable cause."}

## Drift monitor: last four gameweeks against the backtest norm

{table(drift_table)}

`live_gap` and `baseline_gap`: published model minus benchmark, per match (negative means
the published model is better). Flagged when worse than the norm beyond chance, after a
Holm correction across the four markets.

## Shadow stack weights

{table(stack_table(stack))}

Scored live matches with every model: {stack["n_live"]}. Weights moved this week:
{"yes" if stack["moved"] else "no"}. Pooled log loss (recent matches count more): current
{stack["loss_current"]:.4f}, target {stack["loss_target"]:.4f}, after {stack["loss_new"]:.4f}.
Weights move only after 60 scored live matches, by at most 10 points a week, never below 5%.
"""
    out = WEEKLY / f"{label}.md"
    if not dry_run:
        WEEKLY.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        if len(history):
            history.to_csv(AUDIT, index=False)
        DRIFT.write_text(json.dumps({"date": label, "checks": drift.as_records(checks)},
                                    indent=1) + "\n", encoding="utf-8")
        if flagged:
            from fp.news import github
            if github.available():
                github.create_issue(
                    f"Drift flagged: {label}",
                    "The weekly drift monitor flagged: "
                    + ", ".join(c.market for c in flagged)
                    + f". Details in `docs/weekly/{label}.md`.")
    else:
        print(text)
    return out


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
    out = run(now, args.dry_run, args.ledger, args.ledger.parent / "results.parquet")
    print(f"weekly report: {out}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
