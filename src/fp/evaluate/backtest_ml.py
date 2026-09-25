"""Walk-forward backtest of the home, draw, away challengers (Phase 4).

1. Choose each challenger's settings by time-ordered cross-validation on
   2017/18 to 2020/21 only (before the tuning and test seasons).
2. Walk forward over the target seasons: refit at the first lock of every month on
   matches whose results were known by then; predict that month's matches from
   their own lock-time features.

    uv run python -m fp.evaluate.backtest_ml --out PATH [--seasons 2021 2022 2023 2024 2025]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from fp.features import ml_features
from fp.ingest.matches import PROCESSED
from fp.models import ml

log = logging.getLogger(__name__)
CV_SEASONS = (2017, 2018, 2019, 2020)


def choose_settings(features: pd.DataFrame, models: list[str]) -> tuple[dict, pd.DataFrame]:
    rows = features[features["season"].isin(CV_SEASONS)]
    grids = pd.concat([ml.time_series_cv(name, rows) for name in models], ignore_index=True)
    best = {name: grids[grids["model"] == name].sort_values("log_loss").iloc[0]["params"]
            for name in models}
    return best, grids


def walk_forward(features: pd.DataFrame, seasons: list[int], settings: dict) -> pd.DataFrame:
    targets = features[features["season"].isin(seasons)].sort_values("lock_utc")
    months = targets["lock_utc"].dt.tz_convert(None).dt.to_period("M")
    out = []
    for month, group in targets.groupby(months, sort=True):
        refit_at = group["lock_utc"].min()
        train = features[features["result_available_utc"] <= refit_at]
        for name, params in settings.items():
            model = ml.Challenger(name, params).fit(train)
            p = model.predict(group)
            out.append(pd.DataFrame({
                "match_id": group["match_id"].to_numpy(), "league": group["league"].to_numpy(),
                "season": group["season"].to_numpy(), "model": name,
                "refit_utc": refit_at, "lock_utc": group["lock_utc"].to_numpy(),
                "n_train": len(train), "p_home": p[:, 0], "p_draw": p[:, 1], "p_away": p[:, 2],
            }))
        log.info("%s: trained on %d matches, predicted %d", month, len(train), len(group))
    preds = pd.concat(out, ignore_index=True)
    # Leakage guard: every training result was known at the refit, which is at or
    # before every predicted match's lock.
    assert (preds["refit_utc"] <= preds["lock_utc"]).all()
    return preds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seasons", nargs="+", type=int, default=[2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args(argv)
    start = time.time()
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    features = ml_features.build(matches)
    models = [m for m in ml.MODELS if m != "xgboost" or ml.xgboost_available()]
    if "xgboost" not in models:
        log.warning("XGBoost unavailable here (no OpenMP runtime); run on GitHub for it")
    settings, grids = choose_settings(features, models)
    log.info("chosen settings: %s", settings)
    preds = walk_forward(features, args.seasons, settings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(args.out, index=False)
    grids.assign(params=grids["params"].map(json.dumps)).to_parquet(
        args.out.with_suffix(".cv.parquet"), index=False)
    print(f"{len(preds)} predictions from {len(models)} challengers in "
          f"{time.time() - start:.0f}s; settings {settings}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.exit(main())
