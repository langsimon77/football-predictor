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
from fp.models import dixon_coles as dc
from fp.models import elo
from fp.models.priors import PromotedPrior, season_teams
from fp.pipeline import data as data_pipeline
from fp.validate import freshness
from fp.validate.leakage import LOCK_MAX_HOURS, LOCK_MIN_HOURS, RUN_TIME_UTC, known_as_of

log = logging.getLogger(__name__)

REPORT = ROOT / "reports" / "latest.md"
DC_MODEL = "dc_mle_v0"
ELO_MODEL = "elo_v0"
LEAGUES = ("EPL", "LaLiga")
PROMOTED_FLAG_GAMES = 6


@dataclass
class LeagueModels:
    dc_fit: dc.DCFit
    tracker: elo.EloTracker
    curve: elo.GapCurve
    promoted: set[str]
    games_played: dict[str, int]


def model_version() -> tuple[str, bool]:
    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=False).stdout.strip() or "unknown"
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=ROOT,
                           capture_output=True, text=True, check=False).stdout.strip() != ""
    return sha[:12], dirty


def fit_league(matches: pd.DataFrame, fixtures: pd.DataFrame, league: str, now: pd.Timestamp,
               prior: PromotedPrior, season: int) -> LeagueModels:
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
    return LeagueModels(
        dc_fit=fit, tracker=tracker, curve=elo.curve_as_of(tracker, now),
        promoted=prior_promoted(teams_by_season, season), games_played=games.to_dict(),
    )


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
        flags = ["fast_track_model"]
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
            "top_scorelines": json.dumps(top), "flags": json.dumps(flags),
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


def write_report(ledger_frame: pd.DataFrame, results: pd.DataFrame, now: pd.Timestamp,
                 path: Path) -> None:
    from fp.teams import teams

    short = teams().set_index("team_id")["short_name"].to_dict()
    juba = "Africa/Juba"
    dcl = ledger_frame[ledger_frame["model_name"] == DC_MODEL].copy()
    upcoming = dcl[dcl["kickoff_utc"] > now].sort_values("kickoff_utc")
    lines = [
        "# Latest predictions",
        "",
        f"Updated {now.tz_convert(juba):%a %d %b %Y, %H:%M} Juba time. Model: `{DC_MODEL}` "
        "(fast-track maximum-likelihood Dixon-Coles). Probabilities are locked and never edited.",
        "",
        "## Locked, not yet played",
        "",
        "| Kickoff (Juba) | Match | Home | Draw | Away | Over 2.5 | BTTS | Exp. goals | Flags |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in upcoming.itertuples():
        flags = ", ".join(
            f.split(":")[0] for f in json.loads(str(r.flags)) if f != "fast_track_model"
        )
        kickoff = cast(pd.Timestamp, r.kickoff_utc).tz_convert(juba)
        lines.append(
            f"| {kickoff:%a %d %b %H:%M} | {short[r.home_id]} v "
            f"{short[r.away_id]} | {r.p_home:.0%} | {r.p_draw:.0%} | {r.p_away:.0%} | "
            f"{r.p_over_2_5:.0%} | {r.p_btts:.0%} | {r.exp_goals_home:.1f} to "
            f"{r.exp_goals_away:.1f} | {flags or 'none'} |"
        )
    if upcoming.empty:
        lines.append("| none | | | | | | | | |")
    played = dcl.merge(results, on="match_id") if len(results) else dcl.iloc[0:0]
    if len(played):
        from fp.evaluate import metrics

        y = metrics.outcome_1x2(played["home_goals"].to_numpy(), played["away_goals"].to_numpy())
        probs = played[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
        lines += [
            "",
            "## Scored so far",
            "",
            f"{len(played)} locked matches played. Mean RPS {metrics.rps(probs, y).mean():.3f} "
            "(lower is better; 0 is perfect). "
            f"Top pick right in {(probs.argmax(axis=1) == y).mean():.0%}.",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_once(now: pd.Timestamp, matches: pd.DataFrame, fixtures: pd.DataFrame,
             ledger_path: Path, results_path: Path, report_path: Path | None,
             prior: PromotedPrior, dry_run: bool = False) -> pd.DataFrame:
    existing = ledger.load(ledger_path)
    report = freshness.check(known_as_of(matches, now), fixtures, now=now)
    season = int(fixtures["season"].max())
    models = {lg: fit_league(matches, fixtures, lg, now, prior, season) for lg in LEAGUES}
    cands = candidates(fixtures, now, existing)
    new = build_rows(cands, models, now, report.stale)
    log.info("%s: %d matches to lock", now, len(cands))
    if len(new) and not dry_run:
        existing = ledger.append(new, ledger_path)
    results = record_results(matches, fixtures, existing, now, results_path) if not dry_run \
        else pd.DataFrame()
    if report_path is not None and not dry_run:
        write_report(existing, results, now, report_path)
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="skip downloads")
    parser.add_argument("--replay", nargs=2, metavar=("START", "END"))
    parser.add_argument("--ledger", type=Path, default=ledger.PREDICTIONS)
    args = parser.parse_args(argv)

    data_pipeline.main(skip_download=args.offline)
    matches = pd.read_parquet(build.PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(build.PROCESSED / "fixtures.parquet")
    prior = PromotedPrior(matches)
    results_path = args.ledger.parent / "results.parquet"

    if args.replay:
        start, end = (pd.Timestamp(d, tz="UTC") for d in args.replay)
        offset = pd.Timedelta(hours=RUN_TIME_UTC.hour, minutes=RUN_TIME_UTC.minute)
        for day in pd.date_range(start, end, freq="D"):
            run_once(day + offset, matches, fixtures, args.ledger, results_path,
                     args.ledger.parent / "latest.md", prior)
        return 0

    now = pd.Timestamp(datetime.now(UTC))
    new = run_once(now, matches, fixtures, args.ledger, results_path,
                   None if args.dry_run else REPORT, prior, dry_run=args.dry_run)
    if args.dry_run and len(new):
        cols = ["match_id", "model_name", "p_home", "p_draw", "p_away", "late_lock"]
        print(new[cols].round(3).to_string(index=False))
    print(f"locked {len(new)} rows" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    np.seterr(all="ignore")
    sys.exit(main())
