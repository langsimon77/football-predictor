"""Walk-forward backtest for the Bayesian Dixon-Coles model (Phase 2).

NUTS sampling takes seconds, not milliseconds, so the model is refitted once a
week (spec S8), at a lock time. Each match is predicted at its own lock time with
the latest fit made at or before that time. A fit can be up to a week older than
the lock, so it may know less than the live system would, never more.

Run one league and a list of seasons per process, so leagues can run in parallel:
    uv run python -m fp.evaluate.backtest_bayes EPL 2021 2022 --out PATH [--sot]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import cast

import pandas as pd

from fp.ingest.matches import PROCESSED
from fp.models import bayes_dc
from fp.models.priors import season_teams
from fp.models.promotion import fit_promotion_model, promoted_priors
from fp.validate.leakage import check_features, known_as_of, lock_time

log = logging.getLogger(__name__)
REFIT_DAYS = 7


def predict_league(matches: pd.DataFrame, second_tier: pd.DataFrame, league: str,
                   seasons: list[int], params: bayes_dc.BayesParams) -> pd.DataFrame:
    lg = matches[matches["league"] == league]
    teams_by_season = season_teams(matches, league)
    promo = fit_promotion_model(matches, second_tier)
    targets = lg[lg["season"].isin(seasons)].copy()
    targets["lock_utc"] = lock_time(targets["kickoff_utc"])

    rows, fits = [], []
    post: bayes_dc.Posterior | None = None
    fit_time: pd.Timestamp | None = None
    fit_season: int | None = None
    source_max: pd.Timestamp | None = None
    for lock_key, group in targets.groupby("lock_utc", sort=True):
        lock = cast(pd.Timestamp, lock_key)
        season = int(group["season"].iloc[0])
        stale = fit_time is None or lock - fit_time >= pd.Timedelta(days=REFIT_DAYS)
        if post is None or stale or season != fit_season:
            known = known_as_of(lg, lock)
            priors = promoted_priors(promo, teams_by_season, second_tier, league, season)
            new = bayes_dc.fit_checked(known, lock, sorted(teams_by_season[season]), priors,
                                       params)
            fits.append({"league": league, "as_of_utc": lock, "seconds": new.seconds,
                         **new.diagnostics, "ok": new.ok})
            log.info("%s %s fit: %.1fs %s", league, lock.date(), new.seconds, new.diagnostics)
            # Like the live run: never predict from a failed fit. Keep the last good
            # one, unless there is none or the season changed (new clubs to rate).
            if new.ok or post is None or season != fit_season:
                post, fit_time, fit_season = new, lock, season
                source_max = known["result_available_utc"].max()
        for r in group.itertuples():
            out = bayes_dc.markets(post, str(r.home_id), str(r.away_id))
            rows.append({
                "match_id": r.match_id, "league": league, "season": season,
                "as_of_utc": fit_time, "lock_utc": lock, "source_max_utc": source_max,
                "fit_ok": post.ok,
                "bdc_home": out["p_home"], "bdc_draw": out["p_draw"], "bdc_away": out["p_away"],
                "bdc_over_2_5": out["p_over_2_5"], "bdc_btts": out["p_btts"],
                "bdc_exp_goals_home": out["exp_goals_home"],
                "bdc_exp_goals_away": out["exp_goals_away"],
                "bdc_intervals": json.dumps(out["intervals"]),
            })
    preds = pd.DataFrame(rows)
    check_features(preds)
    preds.attrs["fits"] = fits
    return preds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("league")
    ap.add_argument("seasons", nargs="+", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sot", action="store_true", help="add the shots-on-target layer")
    ap.add_argument("--dynamic", action="store_true", help="random-walk challenger")
    ap.add_argument("--xi", type=float, default=0.002)
    ap.add_argument("--sampler", default="nutpie")
    args = ap.parse_args(argv)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    second_tier = pd.read_parquet(PROCESSED / "second_tier.parquet")
    params = bayes_dc.BayesParams(xi=args.xi, use_sot=args.sot, dynamic=args.dynamic,
                                  sampler=args.sampler)
    start = time.time()
    preds = predict_league(matches, second_tier, args.league, args.seasons, params)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(args.out, index=False)
    pd.DataFrame(preds.attrs["fits"]).to_parquet(args.out.with_suffix(".fits.parquet"),
                                                 index=False)
    print(f"{args.league} {args.seasons}: {len(preds)} predictions, "
          f"{len(preds.attrs['fits'])} fits, {time.time() - start:.0f}s")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.exit(main())
