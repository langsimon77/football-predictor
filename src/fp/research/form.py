"""N4 and N5 form features: each club's next-match forecasts from ARIMA (N4) or Prophet (N5).

Four series per club, from its own top-flight matches in the order their results became
known: goals for, goals against, shots on target for, shots on target against. Rules
(Amendment 1, item 4):

- refit for every club at the first lock of every month from 2017/18 on, on results known
  by then (the challengers' refit rule);
- ARIMA: order (p, 0, q) with a constant, p and q from 0 to 2, lowest AIC; between refits the
  forecast is updated with each new result at fixed parameters;
- Prophet: Prophet's own default for the yearly pattern (used once the history spans two
  years; Amendment 1, item 8), weekly and daily off; between refits it forecasts from that
  month's fit;
- a club with fewer than 20 top-flight matches at the refit gets no forecast (left empty).

Each match gets eight columns: the four forecasts for its home club, then its away club.

    uv run python -m fp.research.form --kind arima --prepared out/ --out out/form_arima.parquet
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import warnings
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

SERIES = {"gf": "goals_for", "ga": "goals_against", "sf": "sot_for", "sa": "sot_against"}
MIN_MATCHES = 20
FIRST_SEASON = 2017
ORDERS = [(p, q) for p in range(3) for q in range(3)]
KINDS = ("arima", "prophet")


def columns(kind: str) -> list[str]:
    return [f"{side}_{kind}_{s}" for side in ("home", "away") for s in SERIES]


def months(rows: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.DataFrame]]:
    """(refit time, the month's rows) for every month from 2017/18 on."""
    rows = rows[rows["season"] >= FIRST_SEASON].sort_values("lock_utc")
    period = pd.to_datetime(rows["lock_utc"], utc=True).dt.tz_convert(None).dt.to_period("M")
    return [(g["lock_utc"].min(), g) for _, g in rows.groupby(period, sort=True)]


def usable(res: Any, train: np.ndarray) -> bool:
    """A fit counts as failed (Amendment 1, item 7) if the optimiser did not converge, a root
    sits on the edge of stationarity or invertibility, or the error variance is absurd. A
    broken fit can report a tiny AIC, so it must not take part in the AIC choice."""
    if not np.isfinite(res.aic) or not res.mle_retvals.get("converged", True):
        return False
    for roots in (res.arroots, res.maroots):
        if len(roots) and np.min(np.abs(roots)) < 1.001:
            return False
    return float(res.params[-1]) < 100 * max(float(np.var(train)), 1e-6)


def _arima(known: np.ndarray, values: np.ndarray, refit_at: np.datetime64,
           locks: np.ndarray) -> np.ndarray:
    from statsmodels.tsa.arima.model import ARIMA

    train = values[known <= refit_at]
    out = np.full(len(locks), np.nan)
    if len(train) < MIN_MATCHES:
        return out
    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for p, q in ORDERS:
            try:
                res = ARIMA(train, order=(p, 0, q), trend="c").fit()
            except Exception:  # a failed fit is skipped; the others still compete
                continue
            if not usable(res, train):
                continue
            if best is None or res.aic < best.aic:
                best = res
        if best is None:
            return out
        for i, lock in enumerate(locks):
            seen = values[known <= lock]  # the refit data plus results known since
            out[i] = float(np.asarray(best.apply(seen).forecast(1))[0])
    return out


def _prophet(known: np.ndarray, kickoffs: np.ndarray, values: np.ndarray,
             refit_at: np.datetime64, targets: np.ndarray) -> np.ndarray:
    from prophet import Prophet

    keep = known <= refit_at
    out = np.full(len(targets), np.nan)
    if keep.sum() < MIN_MATCHES:
        return out
    for name in ("prophet", "cmdstanpy"):
        logging.getLogger(name).setLevel(logging.ERROR)
    frame = pd.DataFrame({"ds": pd.to_datetime(kickoffs[keep]), "y": values[keep]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = Prophet(yearly_seasonality="auto", weekly_seasonality=False,
                        daily_seasonality=False).fit(frame)
        pred = model.predict(pd.DataFrame({"ds": pd.to_datetime(targets)}))
    return pred["yhat"].to_numpy(dtype=float)


def _club_month(task: tuple) -> list[tuple[str, str, str, float]]:
    """All four forecasts for one club's matches in one month."""
    kind, team, refit_at, known, kickoffs, series, targets = task
    out = []
    ids, sides, locks, target_kickoffs = targets
    for short, values in series.items():
        if kind == "arima":
            f = _arima(known, values, refit_at, locks)
        else:
            f = _prophet(known, kickoffs, values, refit_at, target_kickoffs)
        out += [(mid, side, short, float(v)) for mid, side, v in zip(ids, sides, f, strict=True)]
    return out


def _naive(series: pd.Series) -> np.ndarray:
    return pd.to_datetime(series, utc=True).dt.tz_convert(None).to_numpy(dtype="datetime64[ns]")


def tasks(kind: str, rows: pd.DataFrame, clubs: pd.DataFrame) -> Iterable[tuple]:
    by_team = {t: g.sort_values("result_available_utc") for t, g in clubs.groupby("team")}
    for refit_at, month in months(rows):
        refit = np.datetime64(pd.Timestamp(refit_at).tz_convert(None).to_datetime64(), "ns")
        for side in ("home", "away"):
            for team, g in month.groupby(f"{side}_id"):
                hist = by_team.get(team)
                if hist is None:
                    continue
                targets = (g["match_id"].to_numpy(), np.array([side] * len(g)),
                           _naive(g["lock_utc"]), _naive(g["kickoff_utc"]))
                series = {s: hist[c].to_numpy(dtype=float) for s, c in SERIES.items()}
                yield (kind, team, refit, _naive(hist["result_available_utc"]),
                       _naive(hist["kickoff_utc"]), series, targets)


def build(kind: str, rows: pd.DataFrame, clubs: pd.DataFrame, jobs: int = 1) -> pd.DataFrame:
    """The eight form columns for every row from 2017/18 on, indexed by match_id."""
    work = list(tasks(kind, rows, clubs))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            parts = list(pool.map(_club_month, work, chunksize=8))
    else:
        parts = [_club_month(t) for t in work]
    long = pd.DataFrame([x for p in parts for x in p],
                        columns=["match_id", "side", "series", "value"])
    long["column"] = long["side"] + f"_{kind}_" + long["series"]
    wide = long.pivot_table(index="match_id", columns="column", values="value", aggfunc="first")
    return wide.reindex(columns=columns(kind))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=KINDS, required=True)
    ap.add_argument("--prepared", type=Path, required=True,
                    help="folder written by `fp.research.methods prepare`")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--last-season", type=int, default=None,
                    help="local trials only: stop after this season")
    args = ap.parse_args(argv)
    start = time.time()
    rows = pd.read_parquet(args.prepared / "features.parquet")
    if args.last_season is not None:
        rows = rows[rows["season"] <= args.last_season]
    clubs = pd.read_parquet(args.prepared / "clubs.parquet")
    form = build(args.kind, rows, clubs, args.jobs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    form.reset_index().to_parquet(args.out, index=False)
    filled = form.notna().mean().round(3).to_dict()
    print(f"{args.kind}: {len(form)} matches in {time.time() - start:.0f}s; share filled {filled}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.exit(main())
