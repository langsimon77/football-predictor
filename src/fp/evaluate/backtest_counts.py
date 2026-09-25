"""Walk-forward backtest for the corners and cards models (Phase 3b).

Same design as the Bayesian goals backtest: weekly refits at a lock time, each
match predicted at its own lock with the latest fit at or before it.

EPL referees: the CSV names every referee after the match, but at lock time the
live system only knows the appointment if football-data.co.uk's fixtures file has
been refreshed. That happens on Friday afternoons (weekend games) and Tuesday
afternoons (midweek games) [V: notes.txt]. So at the 04:41 UTC lock the referee is
known for Sunday, Monday, and Thursday kickoffs only [E: derived from that
schedule]. Otherwise the prediction averages over referees (decision D3).

    uv run python -m fp.evaluate.backtest_counts corners EPL 2021 2022 --out PATH [--poisson]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import cast

import pandas as pd

from fp.features import rolling
from fp.ingest.matches import PROCESSED
from fp.models import counts_nb as cn
from fp.validate.leakage import check_features, known_as_of, lock_time

log = logging.getLogger(__name__)
REFIT_DAYS = 7
REFEREE_KNOWN_DAYS = {"Sunday", "Monday", "Thursday"}


def referee_known_at_lock(kickoff_utc: pd.Series) -> pd.Series:
    return kickoff_utc.dt.tz_convert("Europe/London").dt.day_name().isin(REFEREE_KNOWN_DAYS)


def predict_league(matches: pd.DataFrame, features: pd.DataFrame, target: str, league: str,
                   seasons: list[int], params: cn.CountParams
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    lg = matches[matches["league"] == league]
    teams = sorted(set(lg["home_id"]) | set(lg["away_id"]))
    to_rows = cn.corner_rows if target == "corners" else cn.card_rows
    targets = lg[lg["season"].isin(seasons)].copy()
    targets["lock_utc"] = lock_time(targets["kickoff_utc"])
    if target == "cards":
        # Hide appointments the live system would not have had at lock time.
        targets.loc[~referee_known_at_lock(targets["kickoff_utc"]), "referee"] = None

    rows, fits = [], []
    post: cn.CountPosterior | None = None
    fit_time: pd.Timestamp | None = None
    source_max: pd.Timestamp | None = None
    for lock_key, group in targets.groupby("lock_utc", sort=True):
        lock = cast(pd.Timestamp, lock_key)
        if post is None or fit_time is None or lock - fit_time >= pd.Timedelta(days=REFIT_DAYS):
            known = known_as_of(lg, lock)
            new = cn.fit_checked(to_rows(known, features), lock, teams, params)
            alpha = new.draws.get("alpha")
            fits.append({"league": league, "target": target, "as_of_utc": lock,
                         "seconds": new.seconds, **new.diagnostics, "ok": new.ok,
                         "alpha_mean": float(alpha.mean()) if alpha is not None else None})
            log.info("%s %s %s fit: %.1fs %s", league, target, lock.date(), new.seconds,
                     new.diagnostics)
            if new.ok or post is None:  # never predict from a failed fit if a good one exists
                post, fit_time = new, lock
                source_max = known["result_available_utc"].max()
        match_rows = to_rows(group, features)
        for i, r in enumerate(group.itertuples()):
            row: dict
            if target == "corners":
                row = {"home": match_rows.iloc[i].to_dict(),
                       "away": match_rows.iloc[i + len(group)].to_dict()}
            else:
                row = match_rows.iloc[i].to_dict()
            out = cn.predict(post, row)
            rec = {"match_id": r.match_id, "league": league, "season": r.season,
                   "as_of_utc": fit_time, "lock_utc": lock, "source_max_utc": source_max,
                   "fit_ok": post.ok, "exp_total": out["exp_total"],
                   "pmf": out["pmf"].round(6).tolist()}
            rec.update({f"p_over_{str(line).replace('.', '_')}": v
                        for line, v in out["over"].items()})
            for key in ("exp_home", "exp_away", "referee_known"):
                if key in out:
                    rec[key] = out[key]
            rows.append(rec)
    preds = pd.DataFrame(rows)
    check_features(preds)
    return preds, pd.DataFrame(fits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["corners", "cards"])
    ap.add_argument("league")
    ap.add_argument("seasons", nargs="+", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--poisson", action="store_true")
    ap.add_argument("--sampler", default="numpyro")
    args = ap.parse_args(argv)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    features = rolling.match_features(matches)
    params = cn.CountParams(target=args.target, poisson=args.poisson, sampler=args.sampler,
                            use_referee=args.target == "cards" and args.league == "EPL")
    start = time.time()
    preds, fits = predict_league(matches, features, args.target, args.league, args.seasons,
                                 params)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(args.out, index=False)
    fits.to_parquet(args.out.with_suffix(".fits.parquet"), index=False)
    print(f"{args.target} {args.league} {args.seasons}: {len(preds)} predictions, "
          f"{len(fits)} fits, {int(fits['ok'].sum())} passed, {time.time() - start:.0f}s")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.exit(main())
