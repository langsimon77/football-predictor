"""The daily run (spec S10, Phase 1F version).

1. Refresh data (download, build, validate).
2. Record results for matches already in the ledger.
3. Refit the models on results known right now.
4. Lock every match kicking off in the next 48 hours that is not yet locked.
   A match with under 24 hours to go gets late_lock (it should have been locked
   by an earlier run that failed or did not happen).
5. Append to the ledger and write reports/latest.md.

Usage:
    python -m fp.pipeline.daily                  live run, now = current time
    python -m fp.pipeline.daily --dry-run        do everything, write nothing
    python -m fp.pipeline.daily --replay START END --ledger PATH
        run the daily loop at 04:41 UTC on every day from START to END,
        using only data known on each day. For testing on past rounds.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from fp import ROOT, ledger
from fp.ingest import matches as build
from fp.models import bayes_dc, elo, posterior_store
from fp.models import dixon_coles as dc
from fp.models.priors import PromotedPrior, season_teams
from fp.models.promotion import PromotionModel, fit_promotion_model, promoted_priors
from fp.pipeline import data as data_pipeline
from fp.validate import freshness
from fp.validate.leakage import LOCK_MAX_HOURS, LOCK_MIN_HOURS, RUN_TIME_UTC, known_as_of

log = logging.getLogger(__name__)

REPORT = ROOT / "reports" / "latest.md"
DC_MODEL = "dc_mle_v0"
ELO_MODEL = "elo_v0"
BAYES_MODEL = "dc_bayes_v1"
# Live since Lang approved Phase 2 on 25 Sep 2026 (spec S0: model changes wait
# for approval). The fast model and Elo keep running beside it as challengers.
BAYES_LIVE = True
PRIMARY_MODEL = BAYES_MODEL
# Chosen on the tuning seasons (reports/backtest_phase2_tune.md) and the runner
# benchmark (reports/sampler_benchmark.md).
BAYES_PARAMS = bayes_dc.BayesParams(use_sot=True, sampler="numpyro")
LEAGUES = ("EPL", "LaLiga")
PROMOTED_FLAG_GAMES = 6


@dataclass
class LeagueModels:
    dc_fit: dc.DCFit
    tracker: elo.EloTracker
    curve: elo.GapCurve
    promoted: set[str]
    games_played: dict[str, int]
    bayes: bayes_dc.Posterior | None = None
    bayes_fallback: bool = False


def model_version() -> tuple[str, bool]:
    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=False).stdout.strip() or "unknown"
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=ROOT,
                           capture_output=True, text=True, check=False).stdout.strip() != ""
    return sha[:12], dirty


def fit_league(matches: pd.DataFrame, fixtures: pd.DataFrame, league: str, now: pd.Timestamp,
               prior: PromotedPrior, season: int, second_tier: pd.DataFrame | None = None,
               promo: PromotionModel | None = None, with_bayes: bool = False,
               store: Path = posterior_store.STORE) -> LeagueModels:
    lg = matches[matches["league"] == league]
    teams_by_season = season_teams(matches, league)
    teams_by_season[season] = set(fixtures.loc[fixtures["league"] == league, "home_id"])
    known = known_as_of(lg, now)
    fit = dc.fit(known, now, dc.DCParams(), prior.for_season(teams_by_season, season),
                 extra_teams=sorted(teams_by_season[season]))
    tracker = elo.EloTracker(lg, teams_by_season)
    tracker.advance_to(now)
    tracker.ensure_season(season)
    this_season = known[known["season"] == season]
    games = pd.concat([this_season["home_id"], this_season["away_id"]]).value_counts()
    models = LeagueModels(
        dc_fit=fit, tracker=tracker, curve=elo.curve_as_of(tracker, now),
        promoted=prior_promoted(teams_by_season, season), games_played=games.to_dict(),
    )
    if with_bayes and second_tier is not None and promo is not None:
        priors = promoted_priors(promo, teams_by_season, second_tier, league, season)
        post = bayes_dc.fit_checked(known, now, sorted(teams_by_season[season]), priors,
                                    BAYES_PARAMS)
        log.info("%s Bayesian fit %.1fs %s", league, post.seconds, post.diagnostics)
        if post.ok:
            posterior_store.save(post, league, now, store)
            models.bayes = post
        else:  # never publish from a failed fit: fall back to the last good one
            stored = posterior_store.load(league, store)
            if stored is not None:
                models.bayes, models.bayes_fallback = stored[0], True
                log.warning("%s: diagnostics failed; using posterior from %s", league,
                            stored[1].get("as_of_utc"))
            else:
                log.warning("%s: diagnostics failed and no stored posterior; "
                            "no Bayesian rows this run", league)
    return models


def prior_promoted(teams_by_season: dict[int, set[str]], season: int) -> set[str]:
    return teams_by_season[season] - teams_by_season.get(season - 1, set())


def candidates(fixtures: pd.DataFrame, now: pd.Timestamp, existing: pd.DataFrame
               ) -> pd.DataFrame:
    """Unlocked matches with a confirmed kickoff in (now, now + 48 h]."""
    window = fixtures[
        fixtures["time_confirmed"]
        & (fixtures["kickoff_utc"] > now)
        & (fixtures["kickoff_utc"] <= now + pd.Timedelta(hours=LOCK_MAX_HOURS))
    ].copy()
    done = set(existing["match_id"]) if len(existing) else set()
    window = window[~window["match_id"].isin(done)]
    window["late_lock"] = window["kickoff_utc"] - now < pd.Timedelta(hours=LOCK_MIN_HOURS)
    return window


def build_rows(cands: pd.DataFrame, models: dict[str, LeagueModels], now: pd.Timestamp,
               stale: bool) -> pd.DataFrame:
    version, dirty = model_version()
    rows = []
    for r in cands.itertuples():
        m = models[str(r.league)]
        home, away = str(r.home_id), str(r.away_id)
        flags: list[str] = []
        if r.late_lock:
            flags.append("late_lock")
        if stale:
            flags.append("stale_source")
        for team in (home, away):
            if team in m.promoted and m.games_played.get(team, 0) < PROMOTED_FLAG_GAMES:
                flags.append(f"promoted_lt{PROMOTED_FLAG_GAMES}:{team}")
        common = {
            "match_id": r.match_id, "league": r.league, "season": r.season,
            "home_id": r.home_id, "away_id": r.away_id, "kickoff_utc": r.kickoff_utc,
            "lock_utc": now, "as_of_utc": now, "model_version": version,
            "code_dirty": dirty, "late_lock": bool(r.late_lock), "relock_reason": None,
            "tiers": "{}", "news_adjustments": "[]", "unanswered_questions": "[]",
        }
        goals = dc.markets(m.dc_fit.score_matrix(home, away))
        top = goals.pop("top_scorelines")
        rows.append({
            **common, **goals, "prediction_id": f"{r.match_id}:{DC_MODEL}",
            "model_name": DC_MODEL, "degraded": not m.dc_fit.converged,
            "top_scorelines": json.dumps(top), "flags": json.dumps(["fast_track_model", *flags]),
        })
        if m.bayes is not None and home in m.bayes.teams and away in m.bayes.teams:
            b = bayes_dc.markets(m.bayes, home, away)
            b_top, b_iv = b.pop("top_scorelines"), b.pop("intervals")
            b_flags = flags + (["posterior_fallback"] if m.bayes_fallback else [])
            rows.append({
                **common, **b, "prediction_id": f"{r.match_id}:{BAYES_MODEL}",
                "model_name": BAYES_MODEL, "degraded": m.bayes_fallback,
                "top_scorelines": json.dumps(b_top), "intervals": json.dumps(b_iv),
                "flags": json.dumps(b_flags),
            })
        e = m.curve.probs(m.tracker.gap(home, away))[0]
        rows.append({
            **common, "prediction_id": f"{r.match_id}:{ELO_MODEL}", "model_name": ELO_MODEL,
            "degraded": False, "p_home": e[0], "p_draw": e[1], "p_away": e[2],
            "top_scorelines": "[]", "flags": json.dumps(flags),
        })
    return pd.DataFrame(rows)


def record_results(matches: pd.DataFrame, fixtures: pd.DataFrame, locked: pd.DataFrame,
                   now: pd.Timestamp, path: Path) -> pd.DataFrame:
    """Outcomes for locked matches: football-data.co.uk first, openfootball score as fallback."""
    ids = set(locked["match_id"]) if len(locked) else set()
    full = known_as_of(matches[matches["match_id"].isin(ids)], now)
    rows = full[["match_id", "home_goals", "away_goals", "home_corners", "away_corners",
                 "home_yellows", "away_yellows", "home_reds", "away_reds"]].copy()
    rows["source"] = "football_data_co_uk"
    fallback = fixtures[fixtures["match_id"].isin(ids - set(rows["match_id"]))
                        & fixtures["home_goals"].notna()
                        & (fixtures["kickoff_utc"] + build.RESULT_DELAY <= now)]
    fb = fallback[["match_id", "home_goals", "away_goals"]].assign(source="openfootball")
    results = pd.concat([rows, fb], ignore_index=True)
    results["recorded_utc"] = now
    if len(results):
        path.parent.mkdir(parents=True, exist_ok=True)
        results.reindex(columns=ledger.RESULT_COLUMNS).to_parquet(path, index=False)
    return results


MODEL_LABELS = {
    BAYES_MODEL: "Bayesian Dixon-Coles with shots on target",
    DC_MODEL: "fast maximum-likelihood Dixon-Coles",
    ELO_MODEL: "Elo",
}


def _primary_rows(ledger_frame: pd.DataFrame) -> pd.DataFrame:
    """One row per match: the primary model's, or the fast model's if the primary
    has none for that match (for example when both Bayesian fits failed)."""
    order = [PRIMARY_MODEL, DC_MODEL]
    rows = ledger_frame[ledger_frame["model_name"].isin(order)].copy()
    rows["rank"] = rows["model_name"].map({m: i for i, m in enumerate(order)})
    return rows.sort_values("rank").drop_duplicates("match_id", keep="first")


def write_report(ledger_frame: pd.DataFrame, results: pd.DataFrame, now: pd.Timestamp,
                 path: Path) -> None:
    from fp.evaluate import metrics
    from fp.teams import teams

    short = teams().set_index("team_id")["short_name"].to_dict()
    juba = "Africa/Juba"
    primary = _primary_rows(ledger_frame)
    upcoming = primary[primary["kickoff_utc"] > now].sort_values("kickoff_utc")
    lines = [
        "# Latest predictions",
        "",
        f"Updated {now.tz_convert(juba):%a %d %b %Y, %H:%M} Juba time. Primary model: "
        f"`{PRIMARY_MODEL}` ({MODEL_LABELS[PRIMARY_MODEL]}). Probabilities are locked and "
        "never edited. The range after the home-win chance is the model's 80% interval.",
        "",
        "## Locked, not yet played",
        "",
        "| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Over 2.5 | BTTS | "
        "Exp. goals | Flags |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in upcoming.itertuples():
        flags = [f.split(":")[0] for f in json.loads(str(r.flags)) if f != "fast_track_model"]
        if r.model_name != PRIMARY_MODEL:
            flags.append(f"shown from {r.model_name}")
        intervals = json.loads(str(r.intervals)) if isinstance(r.intervals, str) else {}
        home = f"{r.p_home:.0%}"
        if "p_home" in intervals:
            lo, hi = intervals["p_home"]
            home += f" ({lo:.0%} to {hi:.0%})"
        kickoff = cast(pd.Timestamp, r.kickoff_utc).tz_convert(juba)
        lines.append(
            f"| {kickoff:%a %d %b %H:%M} | {short[r.home_id]} v {short[r.away_id]} | {home} | "
            f"{r.p_draw:.0%} | {r.p_away:.0%} | {r.p_over_2_5:.0%} | {r.p_btts:.0%} | "
            f"{r.exp_goals_home:.1f} to {r.exp_goals_away:.1f} | {', '.join(flags) or 'none'} |"
        )
    if upcoming.empty:
        lines.append("| none | | | | | | | | |")

    scored = ledger_frame.merge(results, on="match_id") if len(results) else None
    if scored is not None and len(scored):
        lines += ["", "## Scored so far", "",
                  "Lower RPS is better; 0 is perfect.", "",
                  "| Model | Matches | Mean RPS | Top pick right |", "|---|---|---|---|"]
        for model, g in scored.groupby("model_name"):
            y = metrics.outcome_1x2(g["home_goals"].to_numpy(), g["away_goals"].to_numpy())
            probs = g[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
            lines.append(f"| `{model}` | {len(g)} | {metrics.rps(probs, y).mean():.3f} | "
                         f"{(probs.argmax(axis=1) == y).mean():.0%} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class Context:
    """Everything a run needs besides the clock."""

    matches: pd.DataFrame
    fixtures: pd.DataFrame
    second_tier: pd.DataFrame
    prior: PromotedPrior
    promo: PromotionModel
    ledger_path: Path
    results_path: Path
    report_path: Path | None
    with_bayes: bool
    store: Path = posterior_store.STORE


def run_once(now: pd.Timestamp, ctx: Context, dry_run: bool = False) -> pd.DataFrame:
    existing = ledger.load(ctx.ledger_path)
    report = freshness.check(known_as_of(ctx.matches, now), ctx.fixtures, now=now)
    season = int(ctx.fixtures["season"].max())
    cands = candidates(ctx.fixtures, now, existing)
    # Refit every run, lock day or not (spec S5.6 step 1). This keeps the fallback
    # store fresh, so a failed fit on a lock day falls back to yesterday's posterior.
    bayes = ctx.with_bayes
    models = {lg: fit_league(ctx.matches, ctx.fixtures, lg, now, ctx.prior, season,
                             ctx.second_tier, ctx.promo, bayes, ctx.store) for lg in LEAGUES}
    new = build_rows(cands, models, now, report.stale)
    log.info("%s: %d matches to lock", now, len(cands))
    if len(new) and not dry_run:
        existing = ledger.append(new, ctx.ledger_path)
    results = (record_results(ctx.matches, ctx.fixtures, existing, now, ctx.results_path)
               if not dry_run else pd.DataFrame())
    if ctx.report_path is not None and not dry_run:
        write_report(existing, results, now, ctx.report_path)
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="skip downloads")
    parser.add_argument("--replay", nargs=2, metavar=("START", "END"))
    parser.add_argument("--ledger", type=Path, default=ledger.PREDICTIONS)
    parser.add_argument("--with-bayes", action="store_true",
                        help="include the Bayesian model even before it is live")
    args = parser.parse_args(argv)

    data_pipeline.main(skip_download=args.offline)
    matches = pd.read_parquet(build.PROCESSED / "matches.parquet")
    second_tier = pd.read_parquet(build.PROCESSED / "second_tier.parquet")
    replay = args.replay is not None
    ctx = Context(
        matches=matches,
        fixtures=pd.read_parquet(build.PROCESSED / "fixtures.parquet"),
        second_tier=second_tier,
        prior=PromotedPrior(matches),
        promo=fit_promotion_model(matches, second_tier),
        ledger_path=args.ledger,
        results_path=args.ledger.parent / "results.parquet",
        report_path=(args.ledger.parent / "latest.md" if replay
                     else None if args.dry_run else REPORT),
        with_bayes=BAYES_LIVE or args.with_bayes,
        store=(args.ledger.parent / "posteriors" if replay else posterior_store.STORE),
    )

    if replay:
        start, end = (pd.Timestamp(d, tz="UTC") for d in args.replay)
        offset = pd.Timedelta(hours=RUN_TIME_UTC.hour, minutes=RUN_TIME_UTC.minute)
        for day in pd.date_range(start, end, freq="D"):
            run_once(day + offset, ctx)
        return 0

    new = run_once(pd.Timestamp(datetime.now(UTC)), ctx, dry_run=args.dry_run)
    if args.dry_run and len(new):
        cols = ["match_id", "model_name", "p_home", "p_draw", "p_away", "late_lock"]
        print(new[cols].round(3).to_string(index=False))
    print(f"locked {len(new)} rows" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    np.seterr(all="ignore")
    sys.exit(main())
