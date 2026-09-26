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
from fp.features import rolling
from fp.ingest import matches as build
from fp.models import bayes_dc, elo, posterior_store
from fp.models import dixon_coles as dc
from fp.models.priors import PromotedPrior, season_teams
from fp.models.promotion import PromotionModel, fit_promotion_model, promoted_priors
from fp.news import impact
from fp.news import live as news_live
from fp.pipeline import counts_live, shadows
from fp.pipeline import data as data_pipeline
from fp.publish import export as publish
from fp.publish import site
from fp.validate import freshness
from fp.validate.leakage import LOCK_MAX_HOURS, LOCK_MIN_HOURS, RUN_TIME_UTC, known_as_of

log = logging.getLogger("fp.pipeline.daily")  # stable name, also when run with -m

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
RELOCK_DAYS = 7
# Failure-path test (Phase 7): set by FP_FORCE_FAIL, honoured only on dry runs.
# "bayes" fails the Bayesian diagnostics so the run falls back; "crash" stops the run.
FORCE_FAIL = ""


class ProblemLog(logging.Handler):
    """Collects warnings and errors from the pipeline, so a run that locked with a
    fallback still reports it (spec S10: degraded runs open an Issue)."""

    SOURCES = ("fp.pipeline", "fp.news", "fp.publish", "__main__")

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(self.SOURCES):
            self.lines.append(f"{record.levelname}: {record.getMessage()}")


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
        if FORCE_FAIL == "bayes":
            post.diagnostics = {**post.diagnostics, "rhat_max": 9.0, "forced": True}
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
    """Unlocked matches with a confirmed kickoff in (now, now + 48 h]. A locked match
    whose kickoff moved by more than 7 days locks again, with the reason recorded
    (spec S10); scoring then uses the latest lock (PRD item 26b)."""
    window = fixtures[
        fixtures["time_confirmed"]
        & (fixtures["kickoff_utc"] > now)
        & (fixtures["kickoff_utc"] <= now + pd.Timedelta(hours=LOCK_MAX_HOURS))
    ].copy()
    window["relock_reason"] = None
    if len(existing) and not {"lock_utc", "kickoff_utc"} <= set(existing.columns):
        window = window[~window["match_id"].isin(set(existing["match_id"]))]
    elif len(existing):
        last = (existing.sort_values("lock_utc").drop_duplicates("match_id", keep="last")
                .set_index("match_id")["kickoff_utc"])
        locked_at = window["match_id"].map(last)
        moved = locked_at.notna() & ((window["kickoff_utc"] - locked_at).abs()
                                     > pd.Timedelta(days=RELOCK_DAYS))
        window.loc[moved, "relock_reason"] = [
            f"kickoff moved from {pd.Timestamp(k):%Y-%m-%d %H:%M} UTC" for k in locked_at[moved]]
        window = window[locked_at.isna() | moved]
    window["late_lock"] = window["kickoff_utc"] - now < pd.Timedelta(hours=LOCK_MIN_HOURS)
    return window


def build_rows(cands: pd.DataFrame, models: dict[str, LeagueModels], now: pd.Timestamp,
               stale: bool, counts: dict[str, counts_live.LeagueCounts] | None = None,
               fixture_features: pd.DataFrame | None = None,
               referees: dict[str, str] | None = None,
               news: news_live.NewsState | None = None) -> pd.DataFrame:
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
            if news is not None and team in news.manager_flags:
                flags.append(f"manager_change:{team}")
        common = {
            "match_id": r.match_id, "league": r.league, "season": r.season,
            "home_id": r.home_id, "away_id": r.away_id, "kickoff_utc": r.kickoff_utc,
            "lock_utc": now, "as_of_utc": now, "model_version": version,
            "code_dirty": dirty, "late_lock": bool(r.late_lock),
            "relock_reason": getattr(r, "relock_reason", None),
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
            match_news = news.by_match.get(str(r.match_id)) if news is not None else None
            scale, adjustments, unanswered = (1.0, 1.0), [], []
            if match_news is not None:
                home_scale, away_scale, _ = impact.scales(match_news.home, match_news.away)
                scale = (home_scale, away_scale)
                adjustments = [impact.record(match_news.home, match_news.away,
                                             match_news.source)]
                unanswered = match_news.unanswered(str(r.match_id))
            b = bayes_dc.markets(m.bayes, home, away, scale=scale)
            b_top, b_iv = b.pop("top_scorelines"), b.pop("intervals")
            b.pop("matrix")
            b_flags = flags + (["posterior_fallback"] if m.bayes_fallback else [])
            if scale != (1.0, 1.0):
                b_flags.append("news_adjusted")
                # The same forecast without news, kept to test whether news helps (S6.5).
                plain = bayes_dc.markets(m.bayes, home, away)
                p_top, p_iv = plain.pop("top_scorelines"), plain.pop("intervals")
                plain.pop("matrix")
                rows.append({
                    **common, **plain, "prediction_id": f"{r.match_id}:{BAYES_MODEL}_nonews",
                    "model_name": f"{BAYES_MODEL}_nonews", "degraded": m.bayes_fallback,
                    "top_scorelines": json.dumps(p_top), "intervals": json.dumps(p_iv),
                    "flags": json.dumps([*b_flags[:-1], "shadow", "no_news"]),
                })
            if unanswered:
                b_flags.append("unanswered_question")
            if counts is not None and fixture_features is not None:
                # Corners and cards ride on the primary row: one row, one full forecast.
                c_cols, c_flags = counts_live.columns(
                    counts[str(r.league)], fixture_features, str(r.match_id),
                    (referees or {}).get(str(r.match_id)))
                b.update(c_cols)
                b_flags += c_flags
            rows.append({
                **common, **b, "prediction_id": f"{r.match_id}:{BAYES_MODEL}",
                "model_name": BAYES_MODEL, "degraded": m.bayes_fallback,
                "top_scorelines": json.dumps(b_top), "intervals": json.dumps(b_iv),
                "flags": json.dumps(b_flags), "news_adjustments": json.dumps(adjustments),
                "unanswered_questions": json.dumps(unanswered),
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
    shadows.STACK_MODEL: "stacked ensemble (shadow)",
    **{v: f"{k.replace('_', ' ')} (shadow)" for k, v in shadows.CHALLENGER_MODELS.items()},
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
        "never edited. The range after the home-win chance is the model's 80% interval. "
        "Tier: how far to trust the home, draw, away forecast, then over 2.5 goals "
        "(High, Medium, Low; see `docs/LEARN.md` chapter 4).",
        "",
        "## Locked, not yet played",
        "",
        "| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | "
        "Exp. goals | Exp. corners | Exp. yellows | Flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in upcoming.itertuples():
        flags = [f.split(":")[0] for f in json.loads(str(r.flags))
                 if f != "fast_track_model" and not f.startswith("counts:")]
        c_home, c_away = cast(float, r.exp_corners_home), cast(float, r.exp_corners_away)
        corners = f"{c_home:.1f} to {c_away:.1f}" if pd.notna(c_home) else ""
        yellows = f"{cast(float, r.exp_yellows):.1f}" if pd.notna(r.exp_yellows) else ""
        if r.model_name != PRIMARY_MODEL:
            flags.append(f"shown from {r.model_name}")
        intervals = json.loads(str(r.intervals)) if isinstance(r.intervals, str) else {}
        home = f"{r.p_home:.0%}"
        if "p_home" in intervals:
            lo, hi = intervals["p_home"]
            home += f" ({lo:.0%} to {hi:.0%})"
        kickoff = cast(pd.Timestamp, r.kickoff_utc).tz_convert(juba)
        tier_map = json.loads(str(r.tiers)) if isinstance(r.tiers, str) else {}
        tier = ", ".join(tier_map[k] for k in ("1x2", "over_2_5") if k in tier_map)
        lines.append(
            f"| {kickoff:%a %d %b %H:%M} | {short[r.home_id]} v {short[r.away_id]} | {home} | "
            f"{r.p_draw:.0%} | {r.p_away:.0%} | {tier} | {r.p_over_2_5:.0%} | {r.p_btts:.0%} | "
            f"{r.exp_goals_home:.1f} to {r.exp_goals_away:.1f} | {corners} | {yellows} | "
            f"{', '.join(flags) or 'none'} |"
        )
    if upcoming.empty:
        lines.append("| none | | | | | | | | | | | |")

    latest = ledger_frame.sort_values("lock_utc").drop_duplicates(
        ["match_id", "model_name"], keep="last")
    scored = latest.merge(results, on="match_id") if len(results) else None
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


def _short_names() -> dict[str, str]:
    from fp.teams import teams
    frame = teams()
    return dict(zip(frame["team_id"].astype(str), frame["short_name"].astype(str), strict=True))


def known_referees(appointments: pd.DataFrame | None, now: pd.Timestamp) -> dict[str, str]:
    """EPL referee appointments our pipeline had actually seen by `now`."""
    if appointments is None or appointments.empty:
        return {}
    seen = appointments[appointments["first_seen_utc"] <= now]
    return dict(zip(seen["match_id"], seen["referee"], strict=True))


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
    with_counts: bool = False
    referee_appointments: pd.DataFrame | None = None
    with_shadows: bool = False
    with_tiers: bool = False
    with_news: bool = False
    use_github: bool = False
    publish_dir: Path | None = None
    site_dir: Path | None = None


def run_once(now: pd.Timestamp, ctx: Context, dry_run: bool = False) -> pd.DataFrame:
    if FORCE_FAIL == "crash":
        raise RuntimeError("forced failure (FP_FORCE_FAIL=crash) for the failure-path test")
    existing = ledger.load(ctx.ledger_path)
    report = freshness.check(known_as_of(ctx.matches, now), ctx.fixtures, now=now)
    if report.stale:
        log.warning("stale source: %s", report.summary())
    season = int(ctx.fixtures["season"].max())
    cands = candidates(ctx.fixtures, now, existing)
    # Refit every run, lock day or not (spec S5.6 step 1). This keeps the fallback
    # store fresh, so a failed fit on a lock day falls back to yesterday's posterior.
    bayes = ctx.with_bayes
    models = {lg: fit_league(ctx.matches, ctx.fixtures, lg, now, ctx.prior, season,
                             ctx.second_tier, ctx.promo, bayes, ctx.store) for lg in LEAGUES}
    counts = fixture_features = referees = None
    if ctx.with_counts:
        features = rolling.match_features(known_as_of(ctx.matches, now))
        counts = {lg: counts_live.fit_league(ctx.matches, features, lg, now, ctx.store)
                  for lg in LEAGUES}
        if len(cands):
            fixture_features = rolling.features_for_fixtures(cands, ctx.matches, now)
            referees = known_referees(ctx.referee_appointments, now)
    news = (news_live.gather(ctx.fixtures, now, ctx.use_github) if ctx.with_news else None)
    new = build_rows(cands, models, now, report.stale, counts, fixture_features, referees,
                     news)
    if ctx.with_shadows and len(cands):
        try:  # shadows never block the published forecast
            challengers = shadows.fit_challengers(ctx.matches, now)
            feats = shadows.fixture_features(cands, ctx.matches, ctx.fixtures, now, models,
                                             fixture_features)
            new = shadows.add_shadows(new, challengers, feats)
        except Exception:
            log.exception("shadow models failed; locking without them")
    if ctx.with_tiers and len(new):
        try:
            new = shadows.add_tiers(new, PRIMARY_MODEL)
        except Exception:
            log.exception("tiers failed; locking without them")
    log.info("%s: %d matches to lock", now, len(cands))
    ledger_ids = set(existing["match_id"]) if len(existing) else set()
    if len(new) and not dry_run:
        existing = ledger.append(new, ctx.ledger_path)
    questions: list[dict] = []
    if news is not None:
        try:
            opened = news_live.after_lock(
                news, ctx.fixtures, sorted(set(cands["match_id"])), ledger_ids,
                {lg: models[lg].dc_fit for lg in LEAGUES}, _short_names(), now, dry_run,
                ctx.use_github)
            if dry_run and opened:
                print(opened["body"])
            questions = question_list(news, opened)
        except Exception:
            log.exception("question queue failed after locking")
    results = (record_results(ctx.matches, ctx.fixtures, existing, now, ctx.results_path)
               if not dry_run else pd.DataFrame())
    if ctx.report_path is not None and not dry_run:
        write_report(existing, results, now, ctx.report_path)
    if ctx.publish_dir is not None and not dry_run:
        try:  # the dashboard never blocks the ledger
            publish_run(ctx, now, existing, results, models, counts, news, report.stale,
                        questions)
        except Exception:
            log.exception("dashboard export failed")
    return new


def question_list(news: news_live.NewsState, opened: dict | None) -> list[dict]:
    """Open question Issues for the dashboard's read-only Questions page."""
    out = []
    for issue in news.issues:
        out.append({"title": issue["title"], "number": issue["number"],
                    "url": issue.get("html_url"), "body": issue.get("body") or "",
                    "created_utc": issue.get("created_at")})
    if opened:
        out.append({"title": opened["title"], "number": opened["number"], "url": None,
                    "body": opened["body"], "created_utc": None,
                    "deadline_utc": opened["deadline_utc"]})
    return out


def publish_run(ctx: Context, now: pd.Timestamp, locked: pd.DataFrame, results: pd.DataFrame,
                models: dict[str, LeagueModels], counts: dict | None,
                news: news_live.NewsState | None, stale: bool, questions: list[dict]) -> None:
    """Provisional forecasts for unlocked matches in the window, then the
    dashboard files and the static page. Nothing here touches the ledger."""
    fx = ctx.fixtures
    soon = fx[fx["time_confirmed"] & (fx["kickoff_utc"] > now)
              & fx["match_id"].isin(publish.window(fx, now))]
    done = set(locked["match_id"]) if len(locked) else set()
    prov = soon[~soon["match_id"].isin(done)].assign(late_lock=False)
    features = (rolling.features_for_fixtures(soon, ctx.matches, now)
                if counts is not None and len(soon) else None)
    referees = known_referees(ctx.referee_appointments, now)
    rows = build_rows(prov, models, now, stale, counts, features, referees, news)
    if ctx.with_tiers and len(rows):
        rows = shadows.add_tiers(rows, PRIMARY_MODEL)
    assert ctx.publish_dir is not None
    view = publish.RunView(
        now=now, ledger=locked, results=results, provisional=rows, matches=ctx.matches,
        fixtures=fx, models=models, counts=counts, features=features, referees=referees,
        manager_flags=news.manager_flags if news is not None else set(),
        names=_short_names(), questions=questions, model_version=model_version()[0])
    table = publish.export(view, ctx.publish_dir)
    if ctx.site_dir is not None:
        site.write(table, now, ctx.site_dir, ctx.publish_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="skip downloads")
    parser.add_argument("--replay", nargs=2, metavar=("START", "END"))
    parser.add_argument("--ledger", type=Path, default=ledger.PREDICTIONS)
    parser.add_argument("--with-bayes", action="store_true",
                        help="include the Bayesian model even before it is live")
    parser.add_argument("--with-counts", action="store_true",
                        help="include corners and cards even before they are live")
    parser.add_argument("--with-news", action="store_true",
                        help="include team news and the Question Queue before it is live")
    parser.add_argument("--read-issues", action="store_true",
                        help="with --with-news: read the question Issues on GitHub")
    args = parser.parse_args(argv)
    global FORCE_FAIL
    FORCE_FAIL = os.environ.get("FP_FORCE_FAIL", "") if args.dry_run else ""
    problems = ProblemLog()
    logging.getLogger().addHandler(problems)
    try:
        return _main(args)
    finally:
        out = os.environ.get("FP_PROBLEMS_FILE")
        if out:
            Path(out).write_text("\n".join(problems.lines), encoding="utf-8")


def _main(args: argparse.Namespace) -> int:
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
        with_counts=counts_live.COUNTS_LIVE or args.with_counts,
        referee_appointments=pd.read_parquet(build.PROCESSED / "referee_appointments.parquet"),
        with_shadows=shadows.SHADOWS_LIVE,
        with_tiers=shadows.TIERS_LIVE,
        with_news=(news_live.NEWS_LIVE or args.with_news) and not replay,
        use_github=(news_live.NEWS_LIVE or args.read_issues) and not replay,
        publish_dir=(None if args.dry_run else args.ledger.parent / "app_data" if replay
                     else publish.OUT),
        site_dir=(None if args.dry_run else args.ledger.parent / "site" if replay
                  else site.SITE),
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
