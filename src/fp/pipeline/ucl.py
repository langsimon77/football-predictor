"""Champions League forecasts (Lang asked to add them to the predictions; the model
passed its pre-registered test on 20 Oct 2026: reports/ucl_backtest_2026_10.md).

Each daily run, after the live and trial steps:
1. Update the domestic results (fp.ingest.europe) and this season's Champions League
   fixtures and results (football-data.org; openfootball has no 2026/27 files).
2. Fit fp.models.club_dc on every result known now.
3. Lock `club_dc_v1` for matches 24 to 48 hours ahead into ledger/ucl/ (its own
   hash-chained ledger and results), record finished results, and write
   ledger/ucl/upcoming.parquet for the Model Lab.

Markets: home, draw, away, and goal lines over 1.5, 2.5 and 3.5 (the tested ones).
Clubs from leagues without domestic data are flagged: they are rated from their
European matches only (the europe_only column of the export lists their IDs).
Nothing here touches a live or trial file.

    uv run python -m fp.pipeline.ucl [--dry-run] [--offline] [--now ISO]
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

from fp import ledger
from fp.ingest import europe
from fp.ingest import football_data_api as api
from fp.ingest import football_data_csv as fd
from fp.models import club_dc
from fp.pipeline import daily
from fp.validate.leakage import LOCK_MAX_HOURS, LOCK_MIN_HOURS

log = logging.getLogger(__name__)

UCL_DIR = ledger.LEDGER_DIR / "ucl"
LEDGER = UCL_DIR / "predictions.parquet"
RESULTS = UCL_DIR / "results.parquet"
UPCOMING = UCL_DIR / "upcoming.parquet"
REPORT = UCL_DIR / "latest.md"
MODEL = "club_dc_v1"
HORIZON_DAYS = 8
UPCOMING_COLUMNS = ["match_id", "round", "kickoff_utc", "home_id", "away_id", "locked",
                    "lock_utc", "p_home", "p_draw", "p_away", "p_over_1_5", "p_over_2_5",
                    "p_over_3_5", "exp_goals_home", "exp_goals_away", "europe_only",
                    "as_of_utc", "model_version"]


@dataclass
class UclContext:
    matches: pd.DataFrame       # domestic and past European results
    current: pd.DataFrame       # this season's Champions League, results and fixtures
    countries: dict[str, str]
    ledger_path: Path = LEDGER
    results_path: Path = RESULTS
    upcoming_path: Path | None = UPCOMING
    report_path: Path | None = REPORT


def load_context(offline: bool) -> UclContext:
    if not offline:
        europe.download_domestic()
    past = europe.all_matches()
    path = api.download_matches("CL", fd.CURRENT_SEASON, refresh=not offline)
    current = europe.current_ucl(api.read_matches(path))
    alias = pd.read_csv(europe.ALIASES_CSV)
    cmap = club_dc.countries(past, dict(zip(alias["club_id"], alias["country"], strict=True)))
    return UclContext(matches=past, current=current, countries=cmap)


def forecast_rows(fit: club_dc.ClubFit, fx: pd.DataFrame, now: pd.Timestamp,
                  domestic: set[str]) -> pd.DataFrame:
    version, dirty = daily.model_version()
    rows = []
    for r in fx.itertuples():
        home, away = str(r.home_id), str(r.away_id)
        kickoff = pd.Timestamp(str(r.kickoff_utc))
        m = fit.markets(home, away, bool(r.neutral))
        only = [c for c in (home, away) if c not in domestic]
        late = (kickoff - now) < pd.Timedelta(hours=LOCK_MIN_HOURS)
        flags = ["ucl", *[f"europe_only_rating:{c}" for c in only]]
        if late:
            flags.append("late_lock")
        rows.append({
            "prediction_id": f"{r.match_id!s}:{MODEL}", "match_id": r.match_id, "league": "UCL",
            "season": int(str(r.season)), "home_id": home, "away_id": away,
            "kickoff_utc": kickoff, "lock_utc": now, "as_of_utc": now,
            "model_name": MODEL, "model_version": version, "code_dirty": dirty,
            "degraded": not fit.converged, "late_lock": bool(late), "relock_reason": None,
            "p_home": m["p_home"], "p_draw": m["p_draw"], "p_away": m["p_away"],
            "p_over_1_5": m["p_over_1_5"], "p_over_2_5": m["p_over_2_5"],
            "p_over_3_5": m["p_over_3_5"], "p_btts": np.nan,
            "exp_goals_home": m["exp_goals_home"], "exp_goals_away": m["exp_goals_away"],
            "top_scorelines": json.dumps(m["top_scorelines"]), "intervals": "{}",
            "tiers": "{}", "news_adjustments": "[]", "unanswered_questions": "[]",
            "flags": json.dumps(flags), "round": r.round, "europe_only": ",".join(only),
        })
    return pd.DataFrame(rows)


def run_once(now: pd.Timestamp, ctx: UclContext, dry_run: bool = False) -> pd.DataFrame:
    cur = ctx.current
    known = pd.concat([ctx.matches, cur.dropna(subset=["home_goals"])], ignore_index=True)
    upcoming = cur[cur["home_goals"].isna() & (cur["kickoff_utc"] > now)]
    clubs = tuple(sorted(set(upcoming["home_id"]) | set(upcoming["away_id"])))
    fit = club_dc.fit(known, now, ctx.countries, clubs)
    log.info("UCL fit at %s: %d matches, %d clubs, converged %s", now, fit.n_matches,
             len(fit.clubs), fit.converged)
    domestic = set(ctx.matches.loc[ctx.matches["kind"] == "domestic", "home_id"])
    existing = ledger.load(ctx.ledger_path)
    locked_ids = set(existing["match_id"]) if len(existing) else set()
    window = upcoming[(upcoming["kickoff_utc"] <= now + pd.Timedelta(hours=LOCK_MAX_HOURS))
                      & ~upcoming["match_id"].isin(locked_ids)]
    new = forecast_rows(fit, window, now, domestic)
    if len(new) and not dry_run:
        existing = ledger.append(new.drop(columns=["round", "europe_only"]), ctx.ledger_path)
    if not dry_run:
        record_results(cur, existing, now, ctx.results_path)
        if ctx.upcoming_path is not None:
            export_upcoming(fit, upcoming, existing, now, domestic, ctx.upcoming_path)
        if ctx.report_path is not None:
            write_report(existing, fit, now, ctx.report_path)
    log.info("UCL %s: %d matches to lock", now, len(new))
    return new


def record_results(cur: pd.DataFrame, locked: pd.DataFrame, now: pd.Timestamp,
                   path: Path) -> pd.DataFrame:
    ids = set(locked["match_id"]) if len(locked) else set()
    done = cur[cur["match_id"].isin(ids) & cur["home_goals"].notna()
               & (cur["result_available_utc"] <= now)]
    out = pd.DataFrame({"match_id": done["match_id"],
                        "home_goals": done["home_goals"].astype("Int64"),
                        "away_goals": done["away_goals"].astype("Int64"),
                        "recorded_utc": now, "source": "football_data_org"})
    out = out.reindex(columns=ledger.RESULT_COLUMNS)
    if len(out):
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=False)
    return out


def export_upcoming(fit: club_dc.ClubFit, upcoming: pd.DataFrame, locked: pd.DataFrame,
                    now: pd.Timestamp, domestic: set[str], path: Path) -> pd.DataFrame:
    """Next 8 days plus the next matchday in full: locked rows as locked, the rest from
    today's fit."""
    soon = upcoming[upcoming["kickoff_utc"] <= now + pd.Timedelta(days=HORIZON_DAYS)]
    if len(upcoming):
        nxt = upcoming.sort_values("kickoff_utc").iloc[0]["round"]
        soon = pd.concat([soon, upcoming[upcoming["round"] == nxt]]).drop_duplicates("match_id")
    rows = forecast_rows(fit, soon, now, domestic).assign(locked=False)
    if len(locked):
        lk = locked.sort_values("lock_utc").drop_duplicates("match_id", keep="last")
        lk = lk[lk["match_id"].isin(soon["match_id"])].assign(locked=True)
        rows = rows[~rows["match_id"].isin(lk["match_id"])]
        rounds = soon.set_index("match_id")["round"]
        lk = lk.assign(round=lk["match_id"].map(rounds),
                       europe_only=[",".join(c for c in (h, a) if c not in domestic)
                                    for h, a in zip(lk["home_id"], lk["away_id"], strict=True)])
        rows = pd.concat([rows, lk], ignore_index=True)
    if len(rows):
        rows.loc[~rows["locked"], "lock_utc"] = pd.NaT
    out = rows.reindex(columns=UPCOMING_COLUMNS).sort_values("kickoff_utc")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def write_report(locked: pd.DataFrame, fit: club_dc.ClubFit, now: pd.Timestamp,
                 path: Path) -> None:
    n = locked["match_id"].nunique() if len(locked) else 0
    lines = [f"# Champions League: {now:%Y-%m-%d %H:%M} UTC", "",
             "Model `club_dc_v1` (passed its pre-registered test, "
             "`reports/ucl_backtest_2026_10.md`). Markets: home, draw, away and goal lines.", "",
             f"- Matches locked so far: {n}",
             f"- Fit: {fit.n_matches} results, {len(fit.clubs)} clubs, converged {fit.converged}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        print(new[["match_id", "p_home", "p_draw", "p_away", "p_over_2_5", "late_lock"]]
              .round(3).to_string(index=False))
    print(f"ucl: locked {len(new)} rows" + (" (dry run, nothing written)" if args.dry_run
                                            else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
