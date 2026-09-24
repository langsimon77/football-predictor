"""Phase 2 backtest report: Bayesian Dixon-Coles variants against Elo, the fast
Dixon-Coles model, base rates, and the market.

Reads prediction files written by `python -m fp.evaluate.backtest_bayes`
(one per league and variant), scores them, and writes a Markdown report.

    uv run python scripts/backtest_phase2.py --stage tune  DIR
    uv run python scripts/backtest_phase2.py --stage test  DIR --variant goals
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.evaluate import backtest as bt
from fp.evaluate import metrics
from fp.ingest.matches import PROCESSED

SEASONS = {"tune": [2021, 2022], "test": [2023, 2024, 2025]}


def table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in frame.itertuples(index=False):
        out.append("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                                     for v in r) + " |")
    return "\n".join(out)


def load_variant(folder: Path, stage: str, variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    preds = pd.concat([pd.read_parquet(f) for f in sorted(folder.glob(f"{stage}_*_{variant}"
                                                                        ".parquet"))])
    fits = pd.concat([pd.read_parquet(f) for f in sorted(folder.glob(f"{stage}_*_{variant}"
                                                                       ".fits.parquet"))])
    return preds, fits


def market_inside_interval(scored: pd.DataFrame, prefix: str) -> float:
    """Proxy check of interval width (PRD item 21).

    The true probability of a home win is never observed. The sharp closing market
    is the best outside estimate. If our 80% intervals are honest, the market should
    land inside them at least about 80% of the time. Far less means the intervals
    are too narrow, for example because the time-decay weighting overstates certainty.
    """
    iv = scored[f"{prefix}_intervals"].dropna().map(json.loads)
    ref = scored.loc[iv.index, "mkt_sharp_home"]
    lo = iv.map(lambda d: d["p_home"][0])
    hi = iv.map(lambda d: d["p_home"][1])
    ok = ref.notna()
    return float(((lo[ok] <= ref[ok]) & (ref[ok] <= hi[ok])).mean())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["tune", "test"], required=True)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--variants", nargs="+", default=["goals", "sot"])
    args = ap.parse_args(argv)

    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    seasons = SEASONS[args.stage]
    base = bt.run(matches, bt.Config(seasons=seasons))  # elo, fast dc, base rates
    scored = bt.attach_outcomes_and_market(base, matches)

    fit_rows = []
    for v in args.variants:
        preds, fits = load_variant(args.folder, args.stage, v)
        keep = preds.set_index("match_id")
        for k in ("home", "draw", "away", "over_2_5"):
            scored[f"b{v}_{k}"] = scored["match_id"].map(keep[f"bdc_{k}"])
        scored[f"b{v}_intervals"] = scored["match_id"].map(keep["bdc_intervals"])
        fit_rows.append({"variant": v, "fits": len(fits), "passed": int(fits["ok"].sum()),
                         "retried": int(fits.get("retried", pd.Series(dtype=bool))
                                        .fillna(False).sum()),
                         "median_seconds": float(fits["seconds"].median()),
                         "market_inside_80pct": market_inside_interval(scored, f"b{v}")})

    models = ["base", "elo", "dc"] + [f"b{v}" for v in args.variants] + ["mkt_sharp"]
    overall = bt.summary(scored, models)
    per = [f"### {lg}\n\n" + table(bt.summary(g, models))
           for lg, g in scored.groupby("league")]

    common = scored.dropna(subset=[f"{m}_{k}" for m in models for k in ("home", "draw", "away")])
    rps = {m: bt.score_1x2(common, m)["rps"].to_numpy() for m in models}
    diffs = []
    for v in args.variants:
        for other in ("base", "elo", "dc", "mkt_sharp"):
            d = rps[f"b{v}"] - rps[other]
            lo, hi = bt.paired_ci(d)
            diffs.append({"comparison": f"b{v} minus {other}", "mean_rps_diff": float(d.mean()),
                          "ci_low": lo, "ci_high": hi})

    ou = scored.dropna(subset=["mkt_sharp_over_2_5"] + [f"b{v}_over_2_5" for v in args.variants])
    y = ou["over_2_5"].to_numpy()
    ou_rows = [{"model": m, "log_loss": float(metrics.binary_log_loss(ou[c].to_numpy(), y).mean())}
               for m, c in [("base", "base_over_2_5"), ("dc", "dc_over_2_5")]
               + [(f"b{v}", f"b{v}_over_2_5") for v in args.variants]
               + [("mkt_sharp", "mkt_sharp_over_2_5")]]

    best = min(args.variants, key=lambda v: float(np.mean(rps[f"b{v}"])))
    top_pick = {m: float((common[[f"{m}_home", f"{m}_draw", f"{m}_away"]].to_numpy()
                          .argmax(1) == common["outcome"]).mean()) for m in models}
    text = f"""# Phase 2 backtest: {args.stage} stage

Seasons: {', '.join(f'{s}/{(s + 1) % 100:02d}' for s in seasons)}. Walk-forward: the Bayesian
model is refitted weekly at a lock time; each match uses the latest fit at or before its
own lock. Elo, fast Dixon-Coles (`dc`), and base rates are refitted at every lock.
Variants: `bgoals` = goals only; `bsot` = goals plus shots on target (decision D1);
`bdynamic` = random-walk challenger. Lower is better.

## 1X2, both leagues

{table(overall)}

## Paired differences in RPS with 95% bootstrap intervals (negative = Bayesian better)

{table(pd.DataFrame(diffs))}

## Over/under 2.5 goals, log loss

{table(pd.DataFrame(ou_rows))}

## Sampler health

{table(pd.DataFrame(fit_rows))}

## Top-pick accuracy (leakage alarm at 60%)

{table(pd.DataFrame([{'model': k, 'top_pick': v} for k, v in top_pick.items()]))}

## Per league

{chr(10).join(chr(10) + s + chr(10) for s in per)}

Best variant by mean RPS on this stage: **b{best}**.
"""
    out = ROOT / "reports" / f"backtest_phase2_{args.stage}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
