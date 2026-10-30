"""Basketball phase B4: daily EuroLeague and NBL forecasts (Lang: "Approved: build it",
30 Oct 2026).

Each run:
1. Reads this season's games from Wikipedia (basketball/data.py; earlier seasons come from
   the cache).
2. Fits the models chosen in B3 on every game played so far, with the B1 settings
   (data/basketball/b1_settings.json, fixed before the tests):
   - winner, both leagues: Elo;
   - handicap (margin), EuroLeague: Elo's margin line, width from the tuning seasons;
   - total points, EuroLeague: the points model, width from the tuning seasons.
   NBL handicap and totals failed their tests (reports/basketball_b1_backtest_2026_10.md),
   so the NBL shows the winner only.
3. Locks the forecast of every game 24 to 48 hours before tip-off into its own hash-chained
   ledger (ledger/basketball/), records the results of locked games, and writes
   ledger/basketball/upcoming.parquet for the Model Lab.

A game needs a tip-off time to lock, and is not locked within an hour of it. Wikipedia
lists EuroLeague rounds shortly before they are played and adds NBL times late in some
weeks, so some games lock late (flagged) or not at all. Nothing here touches a football
file.

    uv run python basketball/live.py [--dry-run] [--offline] [--now ISO]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

import ledger_bb  # noqa: E402
from audit_sample import CURRENT  # noqa: E402
from models import (  # noqa: E402
    EloSettings,
    PointsSettings,
    Spread,
    elo_ratings,
    points_expect,
    points_fit,
)

import data as bb_data  # noqa: E402
from fp import ROOT  # noqa: E402
from fp.pipeline.daily import model_version  # noqa: E402
from fp.validate.leakage import LOCK_MAX_HOURS, LOCK_MIN_HOURS  # noqa: E402

log = logging.getLogger(__name__)

DIR = ROOT / "ledger" / "basketball"
LEDGER = DIR / "predictions.parquet"
RESULTS = DIR / "results.parquet"
UPCOMING = DIR / "upcoming.parquet"
REPORT = DIR / "latest.md"
SETTINGS = ROOT / "data" / "basketball" / "b1_settings.json"
MODEL = "bb_b1_v1"
HORIZON_DAYS = 8
# A game this close to tip-off is not locked at all: Wikipedia times can be off by minutes.
MIN_LEAD = pd.Timedelta(hours=1)
# B3: the markets each league shows (the ones whose B1 test passed).
MARKETS = {"EuroLeague": ("winner", "handicap", "total"), "NBL": ("winner",)}
# Display names: Wikipedia titles without the club-type words.
SHORT = {
    "Anadolu Efes S.K.": "Anadolu Efes", "ASVEL Basket": "ASVEL", "BC Žalgiris": "Žalgiris",
    "Beşiktaş J.K. (men's basketball)": "Beşiktaş", "Dubai Basketball": "Dubai",
    "FC Barcelona Bàsquet": "Barcelona", "FC Bayern Munich (basketball)": "Bayern Munich",
    "Fenerbahçe S.K. (basketball)": "Fenerbahçe", "Hapoel Tel Aviv B.C.": "Hapoel Tel Aviv",
    "KK Crvena zvezda": "Crvena zvezda", "KK Partizan": "Partizan",
    "Maccabi Tel Aviv B.C.": "Maccabi Tel Aviv", "Olympiacos B.C.": "Olympiacos",
    "Panathinaikos B.C.": "Panathinaikos", "Paris Basketball": "Paris",
    "Real Madrid Baloncesto": "Real Madrid", "Saski Baskonia": "Baskonia",
    "Valencia Basket": "Valencia", "Monaco Basket": "Monaco", "Alba Berlin": "Alba Berlin",
}
UPCOMING_COLUMNS = ["game_id", "league", "round", "date", "tip_utc", "home_name", "away_name",
                    "locked", "lock_utc", "p_home", "margin_mean", "margin_sd", "total_mean",
                    "total_sd", "as_of_utc", "model_version"]


def short_name(title: str) -> str:
    if title in SHORT:
        return SHORT[title]
    name = re.sub(r"\s*\([^)]*\)$", "", title)
    return re.sub(r"\s+(B\.C\.|S\.K\.|BC|KK)$", "", name)


@dataclass
class Context:
    games: pd.DataFrame
    settings: dict
    ledger_path: Path = LEDGER
    results_path: Path = RESULTS
    upcoming_path: Path | None = UPCOMING
    report_path: Path | None = REPORT
    fits: dict = field(default_factory=dict)


def load_context(offline: bool) -> Context:
    games, _ = bb_data.build(offline)
    return Context(games=games, settings=json.loads(SETTINGS.read_text(encoding="utf-8")))


def played_games(games: pd.DataFrame, league: str) -> pd.DataFrame:
    g = games[(games["league"] == league) & games["played"] & ~games["left_out"]]
    g = g.sort_values(["date", "game_id"]).reset_index(drop=True)
    return g.assign(home_pts=g["home_pts"].astype(float), away_pts=g["away_pts"].astype(float))


def forecast(ctx: Context, fx: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """One row per fixture in `fx` (ledger columns, no hashes), from games played so far."""
    version, dirty = model_version()
    out = []
    for league, part in fx.groupby("league"):
        st = ctx.settings[league]
        e = st["elo"]
        played = played_games(ctx.games, league)
        ratings = elo_ratings(played, EloSettings(e["k"], e["home"], e["carry"], e["mov"]),
                              season=CURRENT)
        pt = st["points"]
        spread = Spread(pt["sd_home"], pt["sd_away"], pt["rho"])
        for r in part.itertuples():
            diff = ratings.get(r.home_id, 1500.0) + e["home"] - ratings.get(r.away_id, 1500.0)
            row = {"p_home": float(1 / (1 + 10 ** (-diff / 400))), "margin_mean": np.nan,
                   "margin_sd": np.nan, "total_mean": np.nan, "total_sd": np.nan}
            if "handicap" in MARKETS[league]:
                row["margin_mean"] = float(e["margin_scale_b"] * diff)
                row["margin_sd"] = float(e["margin_sd"])
            if "total" in MARKETS[league]:
                key = (league, r.date)
                if key not in ctx.fits:
                    ctx.fits[key] = points_fit(played, PointsSettings(pt["half_life"],
                                                                      pt["penalty"]), r.date)
                mh, ma = points_expect(ctx.fits[key], r.home_id, r.away_id)
                row["total_mean"], row["total_sd"] = float(mh + ma), spread.sd_total
            tip = pd.Timestamp(r.tip_utc) if pd.notna(r.tip_utc) else pd.NaT
            late = bool(pd.notna(tip) and (tip - now) < pd.Timedelta(hours=LOCK_MIN_HOURS))
            flags = ["basketball"] + (["late_lock"] if late else []) + (
                ["nbl_time_home_zone"] if league == "NBL" else [])
            out.append({
                "prediction_id": f"{r.game_id}:{MODEL}", "game_id": r.game_id, "league": league,
                "season": int(r.season), "round": r.section, "home_id": r.home_id,
                "away_id": r.away_id, "home_name": short_name(r.home_title),
                "away_name": short_name(r.away_title), "tip_utc": tip, "lock_utc": now,
                "as_of_utc": now, "model_name": MODEL, "model_version": version,
                "code_dirty": dirty, "late_lock": late, **row, "flags": json.dumps(flags),
                "date": r.date,
            })
    return pd.DataFrame(out)


def fixtures(games: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """This season's games not yet played, from today on (Juba date or later)."""
    g = games[(games["season"] == CURRENT) & ~games["played"]].copy()
    today = now.tz_convert("Africa/Juba").date()
    g = g[[d is not None and pd.notna(d) and d >= today for d in g["date"]]]
    g = g[g["tip_utc"].isna() | (g["tip_utc"] > now)]
    return g.sort_values(["tip_utc", "date", "game_id"], na_position="last")


def run_once(now: pd.Timestamp, ctx: Context, dry_run: bool = False) -> pd.DataFrame:
    fx = fixtures(ctx.games, now)
    locked = ledger_bb.load(ctx.ledger_path)
    have = set(locked["game_id"]) if len(locked) else set()
    window = fx[fx["tip_utc"].notna() & (fx["tip_utc"] > now + MIN_LEAD)
                & (fx["tip_utc"] <= now + pd.Timedelta(hours=LOCK_MAX_HOURS))
                & ~fx["game_id"].isin(have)]
    new = forecast(ctx, window, now)
    if len(new) and not dry_run:
        locked = ledger_bb.append(new.drop(columns=["date"]), ctx.ledger_path)
    if not dry_run:
        record_results(ctx.games, locked, now, ctx.results_path)
        if ctx.upcoming_path is not None:
            export_upcoming(ctx, fx, locked, now, ctx.upcoming_path)
        if ctx.report_path is not None:
            write_report(locked, fx, now, ctx.report_path)
    log.info("basketball %s: %d games to lock", now, len(new))
    return new


def record_results(games: pd.DataFrame, locked: pd.DataFrame, now: pd.Timestamp,
                   path: Path) -> pd.DataFrame:
    ids = set(locked["game_id"]) if len(locked) else set()
    done = games[games["game_id"].isin(ids) & games["played"] & ~games["left_out"]]
    out = pd.DataFrame({"game_id": done["game_id"], "home_pts": done["home_pts"].astype("Int64"),
                        "away_pts": done["away_pts"].astype("Int64"),
                        "overtime": done["overtime"].astype(bool), "recorded_utc": now,
                        "source": "wikipedia"}).reindex(columns=ledger_bb.RESULT_COLUMNS)
    if len(out):
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=False)
    return out


def export_upcoming(ctx: Context, fx: pd.DataFrame, locked: pd.DataFrame, now: pd.Timestamp,
                    path: Path) -> pd.DataFrame:
    """The next 8 days (Juba dates): locked rows as locked, the rest from today's fit. Games
    whose tip-off time is not published yet are kept, with an empty time."""
    end = (now + pd.Timedelta(days=HORIZON_DAYS)).tz_convert("Africa/Juba").date()
    soon = fx[[d <= end for d in fx["date"]]]
    rows = forecast(ctx, soon, now).assign(locked=False)
    if len(locked) and len(rows):
        lk = locked.sort_values("lock_utc").drop_duplicates("game_id", keep="last")
        lk = lk[lk["game_id"].isin(soon["game_id"])].assign(locked=True)
        lk = lk.assign(date=lk["game_id"].map(soon.set_index("game_id")["date"]))
        rows = pd.concat([rows[~rows["game_id"].isin(lk["game_id"])], lk], ignore_index=True)
    if len(rows):
        rows.loc[~rows["locked"].astype(bool), "lock_utc"] = pd.NaT
        rows["date"] = rows["date"].astype(str)
    out = rows.reindex(columns=UPCOMING_COLUMNS)
    if len(out):
        out = out.sort_values(["date", "tip_utc"], na_position="last")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def write_report(locked: pd.DataFrame, fx: pd.DataFrame, now: pd.Timestamp, path: Path) -> None:
    n = locked["game_id"].nunique() if len(locked) else 0
    late = int(locked["late_lock"].fillna(False).sum()) if len(locked) else 0
    no_time = int(fx["tip_utc"].isna().sum())
    lines = [f"# Basketball: {now:%Y-%m-%d %H:%M} UTC", "",
             f"Model `{MODEL}` (B1 settings; reports/basketball_b1_backtest_2026_10.md). "
             "EuroLeague: winner, handicap, total points. NBL: winner.", "",
             f"- Games locked so far: {n} ({late} late)",
             f"- Upcoming games this season without a published tip-off time: {no_time}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="use cached copies only")
    parser.add_argument("--now", help="with --dry-run: pretend the run happens at this UTC time")
    args = parser.parse_args(argv)
    if args.now and not args.dry_run:
        parser.error("--now needs --dry-run")
    ctx = load_context(args.offline)
    now = pd.Timestamp(args.now, tz="UTC") if args.now else pd.Timestamp(datetime.now(UTC))
    new = run_once(now, ctx, dry_run=args.dry_run)
    if len(new):
        show = new[["game_id", "tip_utc", "p_home", "margin_mean", "total_mean", "late_lock"]]
        print(show.round({"p_home": 3, "margin_mean": 1, "total_mean": 1}).to_string(index=False))
    print(f"basketball: locked {len(new)} rows" + (" (dry run, nothing written)"
                                                   if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
