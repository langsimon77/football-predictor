"""Phase 3b report: corners and cards models against a league-average and a
team-average baseline (spec S8, PRD item 14), on walk-forward predictions.

    uv run python scripts/backtest_phase3b.py --stage tune --target cards DIR --variants nb poisson
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

from fp import ROOT
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.features import rolling
from fp.ingest.matches import PROCESSED
from fp.models import counts_nb as cn
from fp.validate.leakage import lock_time

BASE_WINDOW = 380


def load(folder: Path, stage: str, target: str, variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pat = f"{stage}_{target}_*_{variant}"
    preds = pd.concat([pd.read_parquet(f) for f in folder.rglob(f"{pat}.parquet")
                       if not f.name.endswith(".fits.parquet")], ignore_index=True)
    fits = pd.concat([pd.read_parquet(f) for f in folder.rglob(f"{pat}.fits.parquet")],
                     ignore_index=True)
    return preds, fits


def nb_pmf(mean: float, var: float, k: np.ndarray) -> np.ndarray:
    """Negative binomial with this mean and variance; Poisson if not overdispersed."""
    if var <= mean:
        p = poisson.pmf(k, mean)
    else:
        r = mean**2 / (var - mean)
        p = nbinom.pmf(k, r, r / (r + mean))
    return p / p.sum()


def baselines(matches: pd.DataFrame, target: str, match_ids: pd.Series) -> dict[str, np.ndarray]:
    """As-of league-average and team-average predictive pmfs for each match."""
    k = np.arange(cn.MAX_COUNT[target] + 1)
    col_h, col_a = ("home_yellows", "away_yellows") if target == "cards" else \
        ("home_corners", "away_corners")
    m = matches.copy()
    m["total"] = m[col_h] + m[col_a]
    m["lock_utc"] = lock_time(m["kickoff_utc"])
    feats = rolling.match_features(matches).set_index("match_id")
    league_pmf, team_pmf = [], []
    for mid in match_ids:
        row = m.loc[m["match_id"] == mid].iloc[0]
        past = m[(m["league"] == row["league"]) & (m["result_available_utc"] <= row["lock_utc"])]
        recent = past.sort_values("result_available_utc").tail(BASE_WINDOW)["total"]
        mean, var = float(recent.mean()), float(recent.var())
        league_pmf.append(nb_pmf(mean, var, k))
        f = feats.loc[mid]
        if target != "cards":
            team_mean = ((f["home_corners_for"] + f["away_corners_against"]) / 2
                         + (f["away_corners_for"] + f["home_corners_against"]) / 2)
        else:
            team_mean = f["home_yellows"] + f["away_yellows"]
        team_mean = float(team_mean) if np.isfinite(team_mean) else mean
        # Keep the league's overdispersion ratio, rescaled to this match's mean.
        ratio = var / mean if mean > 0 else 1.0
        team_pmf.append(nb_pmf(team_mean, ratio * team_mean, k))
    return {"league_avg": np.array(league_pmf), "team_avg": np.array(team_pmf)}


def log_score(pmf: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(pmf[np.arange(len(y)), y], 1e-12, 1))


def crps(pmf: np.ndarray, y: np.ndarray) -> np.ndarray:
    k = np.arange(pmf.shape[1])
    cdf = np.cumsum(pmf, axis=1)
    return ((cdf - (k[None, :] >= y[:, None])) ** 2).sum(axis=1)


def table(rows: list[dict]) -> str:
    frame = pd.DataFrame(rows)
    head = "| " + " | ".join(frame.columns) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                                       for v in r) + " |" for r in frame.itertuples(index=False))
    return head + "\n" + body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--target", required=True, choices=["corners", "corners_total", "cards"])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--variants", nargs="+", default=["nb"])
    args = ap.parse_args(argv)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    col_h, col_a = ("home_yellows", "away_yellows") if args.target == "cards" else \
        ("home_corners", "away_corners")
    totals = (matches[col_h] + matches[col_a]).astype(int)
    total_of = dict(zip(matches["match_id"], totals, strict=True))
    lines = cn.LINES[args.target]

    pmfs: dict[str, np.ndarray] = {}
    fit_rows = []
    ids = None
    for v in args.variants:
        preds, fits = load(args.folder, args.stage, args.target, v)
        preds = preds.sort_values("match_id").reset_index(drop=True)
        ids = preds["match_id"] if ids is None else ids
        preds = preds.set_index("match_id").loc[ids]
        pmfs[v] = np.vstack(preds["pmf"].to_numpy())
        alpha = fits["alpha_mean"].dropna()
        fit_rows.append({"variant": v, "fits": len(fits), "passed": int(fits["ok"].sum()),
                         "median_seconds": float(fits["seconds"].median()),
                         "dispersion_alpha_median": float(alpha.median()) if len(alpha)
                         else "none (Poisson)"})
    assert ids is not None
    pmfs.update(baselines(matches, args.target, ids))
    y = ids.map(total_of).to_numpy()
    k = np.arange(cn.MAX_COUNT[args.target] + 1)

    rows = []
    for name, pmf in pmfs.items():
        mean = (pmf * k).sum(axis=1)
        rec = {"forecast": name, "log_score": float(log_score(pmf, y).mean()),
               "crps": float(crps(pmf, y).mean()), "mean_forecast": float(mean.mean()),
               "mean_actual": float(y.mean())}
        for line in lines:
            p_over = pmf[:, k > line].sum(axis=1)
            rec[f"logloss_o{line}"] = float(metrics.binary_log_loss(p_over, y > line).mean())
        rows.append(rec)
    diffs = []
    for v in args.variants:
        for base in ("league_avg", "team_avg"):
            for metric_name, fn in (("log_score", log_score), ("crps", crps)):
                d = fn(pmfs[v], y) - fn(pmfs[base], y)
                lo, hi = bt.paired_ci(d)
                diffs.append({"comparison": f"{v} minus {base}", "metric": metric_name,
                              "diff": float(d.mean()), "ci_low": lo, "ci_high": hi})
    mid_line = lines[len(lines) // 2]
    calib = []
    for name in (*args.variants, "league_avg"):
        p_over = pmfs[name][:, k > mid_line].sum(axis=1)
        order = np.argsort(p_over)
        for j, g in enumerate(np.array_split(order, 5)):
            calib.append({"forecast": name, "group": j + 1,
                          "mean_p_over": float(p_over[g].mean()),
                          "observed": float((y[g] > mid_line).mean()), "n": len(g)})

    text = f"""# Phase 3b backtest: {args.target}, {args.stage} stage

Generated by `scripts/backtest_phase3b.py`. Walk-forward, weekly refits, each match
predicted at its lock time. Baselines, also as of each lock: `league_avg` = negative
binomial matched to the league's last {BASE_WINDOW} matches; `team_avg` = the two clubs'
rolling averages with the league's overdispersion. Lower log score, CRPS, and log loss
are better. {len(y)} matches.

## Scores

{table(rows)}

## Differences with 95% paired bootstrap intervals (negative = model better)

{table(diffs)}

## Sampler health and dispersion

Negative binomial shape alpha: variance = mean + mean^2 / alpha. Large alpha means
close to Poisson.

{table(fit_rows)}

## Calibration of over {mid_line} (five equal groups)

{table(calib)}
"""
    out = ROOT / "reports" / f"backtest_phase3b_{args.target}_{args.stage}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
