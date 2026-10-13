"""Serie A and Ligue 1 in the background (Lang chose "Run what passed", 13 Oct 2026).

What locks, for the markets that passed the pre-registered backtest
(reports/trial_backtest_2026_10.md):
- `dc_bayes_v1`: home, draw, away with the goals fix (`shape_v1`, refitted monthly on
  these two leagues' own forecasts), and yellows from `cards_nb_v1` (no referee:
  neither league publishes one). Double chance comes from the home, draw, away numbers.
- `dc_bayes_v1_noshape`: the same forecast without the fix, with its expected goals,
  because the monthly refit of the fix learns from them.
- `elo_v0`: home, draw, away, the benchmark.
Goal lines, both teams score and corners failed the backtest and are not locked.

Where it writes: ledger/trial/ (its own hash-chained ledger, results and report),
data/posteriors/trial/ and data/shape/shape_v1_trial.json. It reads no live ledger,
writes no live file and publishes nothing. The models, lock window and result rules
are the live ones (fp.pipeline.daily).

    uv run python -m fp.pipeline.trial [--dry-run] [--offline]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT, leagues, ledger
from fp.features import rolling
from fp.ingest import matches as build
from fp.ingest import results_feed
from fp.models import posterior_store, shape
from fp.models.priors import PromotedPrior
from fp.models.promotion import fit_promotion_model
from fp.pipeline import counts_live, daily
from fp.pipeline import data as data_pipeline
from fp.validate import freshness
from fp.validate.leakage import known_as_of

log = logging.getLogger(__name__)

TRIAL_DIR = ledger.LEDGER_DIR / "trial"
LEDGER = TRIAL_DIR / "predictions.parquet"
RESULTS = TRIAL_DIR / "results.parquet"
REPORT = TRIAL_DIR / "latest.md"
STORE = posterior_store.STORE / "trial"
SHAPE_STORE = shape.STORE.with_name("shape_v1_trial.json")
SHAPE_BACKTEST = ROOT / "data" / "backtests" / "trial" / "dc_bayes_v1_walkforward_2021_2025.parquet"
COMPETITIONS = {lg.fdorg: lg.code for lg in leagues.TRIAL}
KEEP_MODELS = (daily.BAYES_MODEL, daily.NO_SHAPE_MODEL, daily.ELO_MODEL)
# Columns that stay empty: the markets that failed the backtest.
DROP = ["p_over_1_5", "p_over_2_5", "p_over_3_5", "p_btts",
        "p_corners_over_8_5", "p_corners_over_9_5", "p_corners_over_10_5", "p_corners_over_11_5",
        "exp_corners_home", "exp_corners_away"]
INTERVALS = ("p_home", "p_draw", "p_away")
FLAG = "trial"


@dataclass
class TrialContext:
    matches: pd.DataFrame
    goal_matches: pd.DataFrame
    score_only: pd.DataFrame
    fixtures: pd.DataFrame
    second_tier: pd.DataFrame
    ledger_path: Path = LEDGER
    results_path: Path = RESULTS
    report_path: Path | None = REPORT
    store: Path = STORE
    shape_store: Path = SHAPE_STORE


def trim(rows: pd.DataFrame) -> pd.DataFrame:
    """Keep the passing markets only, and mark every row as a trial row."""
    if rows.empty:
        return rows
    out = rows[rows["model_name"].isin(KEEP_MODELS)].copy()
    for col in DROP:
        if col in out:
            out[col] = np.nan
    primary = out["model_name"] == daily.BAYES_MODEL
    for col in ("exp_goals_home", "exp_goals_away"):
        if col in out:  # the fix keeps them; the plain copy carries them for the refit
            out.loc[primary, col] = np.nan
    out["top_scorelines"] = "[]"
    if "intervals" in out:
        out["intervals"] = [json.dumps({k: v for k, v in json.loads(iv).items() if k in INTERVALS})
                            if isinstance(iv, str) else iv for iv in out["intervals"]]

    def flags(text: str) -> str:
        names = json.loads(text)
        had_counts = any(f.startswith("counts:") for f in names)
        names = [f for f in names if not f.startswith("counts:")]
        if had_counts:  # only the yellows model rides on the row
            names.append(f"counts:{counts_live.CARDS_MODEL}")
        return json.dumps([*names, FLAG])
    out["flags"] = out["flags"].map(flags)
    return out


def run_once(now: pd.Timestamp, ctx: TrialContext, dry_run: bool = False) -> pd.DataFrame:
    existing = ledger.load(ctx.ledger_path)
    report = freshness.check(known_as_of(ctx.matches, now), ctx.fixtures, now=now)
    if report.stale:
        log.warning("trial: stale source: %s", report.summary())
    season = int(ctx.fixtures["season"].max())
    cands = daily.candidates(ctx.fixtures, now, existing)
    prior = PromotedPrior(ctx.matches)
    promo = fit_promotion_model(ctx.matches, ctx.second_tier)
    codes = [lg.code for lg in leagues.TRIAL]
    models = {lg: daily.fit_league(ctx.goal_matches, ctx.fixtures, lg, now, prior, season,
                                   ctx.second_tier, promo, True, ctx.store) for lg in codes}
    sh = shape.current(ctx.matches, existing, now, ctx.shape_store, save=not dry_run,
                       backtest=SHAPE_BACKTEST)
    features = rolling.match_features(known_as_of(ctx.matches, now))
    counts = {lg: counts_live.fit_league(ctx.matches, features, lg, now, ctx.store,
                                         targets=("cards",)) for lg in codes}
    fixture_features = (rolling.features_for_fixtures(cands, ctx.matches, now)
                        if len(cands) else None)
    new = trim(daily.build_rows(cands, models, now, report.stale, counts, fixture_features,
                                {}, None, sh))
    log.info("trial %s: %d matches to lock, %d rows", now, len(cands), len(new))
    if len(new) and not dry_run:
        existing = ledger.append(new, ctx.ledger_path)
    results = (daily.record_results(ctx.matches, ctx.fixtures, existing, now, ctx.results_path,
                                    ctx.score_only) if not dry_run else pd.DataFrame())
    if ctx.report_path is not None and not dry_run:
        write_report(existing, results, now, models, sh, ctx.report_path)
    return new


def write_report(locked: pd.DataFrame, results: pd.DataFrame, now: pd.Timestamp,
                 models: dict[str, daily.LeagueModels], sh: shape.Shape,
                 path: Path) -> None:
    primary = locked[locked["model_name"] == daily.BAYES_MODEL] if len(locked) else locked
    per = (primary.groupby("league")["match_id"].nunique().to_dict() if len(primary) else {})
    lines = [f"# Leagues on trial: {now:%Y-%m-%d %H:%M} UTC", "",
             "Serie A and Ligue 1 in the background: locked and scored, not published "
             "(Lang, 13 Oct 2026). Markets: home, draw, away (with double chance) and yellows.",
             "", f"- Matches locked so far: {sum(per.values())}"
             + (f" ({', '.join(f'{k} {v}' for k, v in per.items())})" if per else ""),
             f"- Results recorded: {len(results)}",
             f"- Goals fix this month: home dispersion {sh.vh:.3f}, away {sh.va:.3f}, "
             f"rho {sh.rho:+.4f}, stretch {sh.s:+.4f}"]
    for lg, m in models.items():
        state = ("fallback to the last good fit" if m.bayes_fallback
                 else "fit passed" if m.bayes is not None else "no fit")
        lines.append(f"- {lg} Bayesian model: {state}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_context(offline: bool) -> TrialContext:
    data_pipeline.build_trial(skip_download=offline)
    matches = pd.read_parquet(build.TRIAL_DIR / "matches.parquet")
    fixtures = pd.read_parquet(build.TRIAL_DIR / "fixtures.parquet")
    second_tier = pd.read_parquet(build.TRIAL_DIR / "second_tier.parquet")
    fast = results_feed.collect(fixtures, offline=offline, competitions=COMPETITIONS)
    score_only = results_feed.score_only_rows(matches, fixtures, fast)
    log.info("trial fast results: %d finished matches waiting for football-data.co.uk",
             len(score_only))
    return TrialContext(matches=matches,
                        goal_matches=results_feed.with_scores(matches, score_only),
                        score_only=score_only, fixtures=fixtures, second_tier=second_tier)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="skip downloads")
    parser.add_argument("--now", help="with --dry-run: pretend the run happens at this UTC time")
    args = parser.parse_args(argv)
    if args.now and not args.dry_run:
        parser.error("--now needs --dry-run")
    ctx = load_context(args.offline)
    now = pd.Timestamp(args.now, tz="UTC") if args.now else pd.Timestamp(datetime.now(UTC))
    new = run_once(now, ctx, dry_run=args.dry_run)
    if len(new):
        cols = ["match_id", "model_name", "p_home", "p_draw", "p_away", "p_yellows_over_4_5"]
        print(new.reindex(columns=cols).round(3).to_string(index=False))
    print(f"trial: locked {len(new)} rows" + (" (dry run, nothing written)" if args.dry_run
                                              else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    np.seterr(all="ignore")
    sys.exit(main())
