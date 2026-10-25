"""Walk-forward runs of the new methods N1 to N5.

Plan: data/audit/preregistration_methods_hda_2026_10.md.

Same protocol as the current challengers (fp.evaluate.backtest_ml):
1. settings chosen by time-ordered cross-validation on 2017/18 to 2020/21 (four expanding
   folds in kickoff order, the first 40% only for training), lowest mean log loss;
2. walk forward over 2021/22 to 2025/26: refit at the first lock of every month on matches
   whose results were known by then; forecast that month's matches.

Steps (one GitHub job each, see .github/workflows/methods.yml):

    uv run python -m fp.research.methods prepare --out out/prepared
    uv run python -m fp.research.form --kind arima --prepared out/prepared \
        --out out/form_arima.parquet
    uv run python -m fp.research.methods run --method lightgbm --prepared out/prepared --out out/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fp.evaluate import metrics
from fp.features import ml_features
from fp.features.ml_features import FEATURES
from fp.research import form, neural, sequences

log = logging.getLogger(__name__)

CV_SEASONS = (2017, 2018, 2019, 2020)
TARGET_SEASONS = (2021, 2022, 2023, 2024, 2025)
SEED = 2026
GRIDS: dict[str, list[dict[str, Any]]] = {
    "lightgbm": [{"num_leaves": leaves, "n_estimators": n, "learning_rate": rate}
                 for leaves in (7, 15, 31) for n in (150, 400) for rate in (0.03, 0.1)],
    "multinomial": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "lstm": [{"size": s, "length": n} for s in (16, 32) for n in (5, 10)],
    "transformer": [{"size": s, "length": n} for s in (16, 32) for n in (5, 10)],
}
# Method name -> (model family, feature set). N4 and N5 each have two forecasts (Amendment 1,
# item 5); the scoring script picks the representative on 2021/22 and 2022/23.
METHODS = {
    "lightgbm": ("lightgbm", "base"),             # N1
    "lstm": ("lstm", "base"),                     # N2
    "transformer": ("transformer", "base"),       # N3
    "arima_multinomial": ("multinomial", "arima"),    # N4
    "arima_lightgbm": ("lightgbm", "arima"),          # N4
    "prophet_multinomial": ("multinomial", "prophet"),  # N5
    "prophet_lightgbm": ("lightgbm", "prophet"),        # N5
}


def feature_list(feature_set: str) -> list[str]:
    return list(FEATURES) if feature_set == "base" else [*FEATURES, *form.columns(feature_set)]


@dataclass
class Tabular:
    """The multinomial GLM (as fp.models.ml) or LightGBM, on a given feature list."""

    family: str
    params: dict[str, Any]
    features: list[str]
    fitted: Any = None

    def fit(self, rows: pd.DataFrame) -> Tabular:
        x, y = rows[self.features], rows["outcome"].to_numpy()
        if self.family == "multinomial":
            self.fitted = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                        LogisticRegression(C=self.params["C"], max_iter=3000))
        else:
            from lightgbm import LGBMClassifier
            self.fitted = LGBMClassifier(objective="multiclass", min_child_samples=50,
                                         subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                         random_state=SEED, n_jobs=4, verbose=-1, **self.params)
        self.fitted.fit(x, y)
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        p = self.fitted.predict_proba(rows[self.features])
        return p[:, np.argsort(self.fitted.classes_)]


@dataclass
class Prepared:
    """Feature rows, club histories and the sequence arrays aligned to the rows."""

    rows: pd.DataFrame
    seq: np.ndarray
    mask: np.ndarray
    forms: dict[str, pd.DataFrame] = field(default_factory=dict)

    def take(self, idx: np.ndarray) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        return self.rows.iloc[idx], self.seq[idx], self.mask[idx]


def make_model(method: str, params: dict[str, Any]) -> tuple[Callable, Callable]:
    """fit(rows, seq, mask) and predict(model, rows, seq, mask) for a method and setting."""
    family, feature_set = METHODS[method]
    feats = feature_list(feature_set)
    if family in ("lstm", "transformer"):
        def fit_seq(rows: pd.DataFrame, seq: np.ndarray, mask: np.ndarray) -> Any:
            return neural.SeqNet(family, params, feats).fit(rows, seq, mask)
        return fit_seq, lambda m, rows, seq, mask: m.predict(rows, seq, mask)

    def fit_tab(rows: pd.DataFrame, seq: np.ndarray, mask: np.ndarray) -> Any:
        return Tabular(family, params, feats).fit(rows)
    return fit_tab, lambda m, rows, seq, mask: m.predict(rows)


def time_series_cv(method: str, data: Prepared, seasons: tuple[int, ...] = CV_SEASONS,
                   grid: list[dict[str, Any]] | None = None, folds: int = 4) -> pd.DataFrame:
    """Mean log loss of each setting over expanding folds in kickoff order (as fp.models.ml)."""
    pool = np.flatnonzero(data.rows["season"].isin(seasons).to_numpy())
    pool = pool[np.argsort(data.rows["kickoff_utc"].to_numpy()[pool], kind="stable")]
    edges = np.linspace(len(pool) * 0.4, len(pool), folds + 1).astype(int)
    family = METHODS[method][0]
    results = []
    for params in grid if grid is not None else GRIDS[family]:
        fit, predict = make_model(method, params)
        losses = []
        for start, end in zip(edges[:-1], edges[1:], strict=True):
            train, test = pool[:start], pool[start:end]
            model = fit(*data.take(train))
            p = predict(model, *data.take(test))
            y = data.rows["outcome"].to_numpy()[test]
            losses.append(metrics.log_loss(p, y).mean())
        results.append({"method": method, "params": params, "log_loss": float(np.mean(losses))})
        log.info("%s %s: CV log loss %.4f", method, params, results[-1]["log_loss"])
    return pd.DataFrame(results)


def walk_forward(method: str, params: dict[str, Any], data: Prepared,
                 seasons: tuple[int, ...] = TARGET_SEASONS) -> pd.DataFrame:
    """Monthly refits on results known at the refit; forecasts for that month's matches."""
    rows = data.rows
    targets = rows[rows["season"].isin(seasons)].sort_values("lock_utc")
    period = pd.to_datetime(targets["lock_utc"], utc=True).dt.tz_convert(None).dt.to_period("M")
    fit, predict = make_model(method, params)
    position = pd.Series(np.arange(len(rows)), index=rows.index)
    out = []
    for month, group in targets.groupby(period, sort=True):
        refit_at = group["lock_utc"].min()
        train = np.flatnonzero((rows["result_available_utc"] <= refit_at).to_numpy())
        model = fit(*data.take(train))
        idx = position[group.index].to_numpy()
        p = predict(model, *data.take(idx))
        out.append(pd.DataFrame({
            "match_id": group["match_id"].to_numpy(), "league": group["league"].to_numpy(),
            "season": group["season"].to_numpy(), "model": method, "refit_utc": refit_at,
            "lock_utc": group["lock_utc"].to_numpy(), "n_train": len(train),
            "p_home": p[:, 0], "p_draw": p[:, 1], "p_away": p[:, 2]}))
        log.info("%s %s: trained on %d matches, predicted %d", method, month, len(train),
                 len(group))
    preds = pd.concat(out, ignore_index=True)
    # Leakage guard, as for the challengers: every training result was known at the refit.
    assert (preds["refit_utc"] <= preds["lock_utc"]).all()
    return preds


def prepare(matches: pd.DataFrame, out: Path) -> None:
    rows = ml_features.build(matches)
    clubs = sequences.club_matches(matches)
    seq, mask = sequences.histories(rows, clubs, sequences.MAX_LENGTH)
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "features.parquet", index=False)
    clubs.to_parquet(out / "clubs.parquet", index=False)
    np.savez_compressed(out / "sequences.npz", seq=seq, mask=mask)
    print(f"prepared {len(rows)} rows, {len(clubs)} club-match rows")


def load(prepared: Path, feature_set: str, form_path: Path | None) -> Prepared:
    rows = pd.read_parquet(prepared / "features.parquet")
    arrays = np.load(prepared / "sequences.npz")
    if feature_set != "base":
        if form_path is None:
            raise SystemExit(f"--form is needed for the {feature_set} features")
        f = pd.read_parquet(form_path).set_index("match_id")
        rows = rows.join(f[form.columns(feature_set)], on="match_id")
    return Prepared(rows.reset_index(drop=True), arrays["seq"], arrays["mask"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="step", required=True)
    p1 = sub.add_parser("prepare")
    p1.add_argument("--matches", type=Path, default=None)
    p1.add_argument("--out", type=Path, required=True)
    p2 = sub.add_parser("run")
    p2.add_argument("--method", choices=sorted(METHODS), required=True)
    p2.add_argument("--prepared", type=Path, required=True)
    p2.add_argument("--form", type=Path, default=None)
    p2.add_argument("--out", type=Path, required=True)
    p2.add_argument("--trial", action="store_true",
                    help="local check only: first setting, CV on 2017/18 and 2018/19, forecast "
                         "2019/20; never used for results")
    args = ap.parse_args(argv)
    start = time.time()
    if args.step == "prepare":
        from fp.ingest.matches import PROCESSED
        prepare(pd.read_parquet(args.matches or PROCESSED / "matches.parquet"), args.out)
        return 0
    data = load(args.prepared, METHODS[args.method][1], args.form)
    family = METHODS[args.method][0]
    if args.trial:
        grids = time_series_cv(args.method, data, (2017, 2018), GRIDS[family][:1])
        seasons: tuple[int, ...] = (2019,)
    else:
        grids, seasons = time_series_cv(args.method, data), TARGET_SEASONS
    best = grids.sort_values("log_loss").iloc[0]["params"]
    log.info("%s: chosen setting %s", args.method, best)
    preds = walk_forward(args.method, best, data, seasons)
    args.out.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(args.out / f"methods_{args.method}.parquet", index=False)
    grids.assign(params=grids["params"].map(json.dumps)).to_parquet(
        args.out / f"methods_{args.method}_cv.parquet", index=False)
    print(f"{args.method}: {len(preds)} forecasts in {time.time() - start:.0f}s; setting {best}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.exit(main())
