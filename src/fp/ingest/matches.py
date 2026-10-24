"""Build the processed match tables from the raw downloads.

Outputs (data/processed/):
- matches.parquet: one row per top-flight match played, 2016/17 onward.
- fixtures.parquet: the full current-season calendar, played or not.
- second_tier.parquet: Championship and Segunda results, for promoted-team priors.
- referee_appointments.parquet: EPL referees as first seen in fixtures.csv.

Each builder takes a group of leagues (fp.leagues). The defaults build the live
leagues only, so the leagues on trial never reach a live table.

Every row that holds an outcome also holds result_available_utc: the earliest time
the pipeline may treat that outcome as known. The leakage guard checks it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from fp import ROOT, leagues
from fp.ingest import football_data_api as fdorg
from fp.ingest import football_data_csv as fd
from fp.ingest import openfootball
from fp.ingest.http import cached_copies
from fp.teams import map_series, to_team_id

log = logging.getLogger(__name__)

PROCESSED = ROOT / "data" / "processed"
TRIAL_DIR = PROCESSED / "trial"  # the leagues on trial, apart from every live table

# division -> (league name, openfootball code), for every known league
TOP_DIVISIONS = {lg.division: (lg.code, lg.openfootball) for lg in leagues.ALL}
Group = tuple[leagues.League, ...]

# Matches whose recorded score is not a football result (data/manual/left_out_matches.csv):
# matches stopped before full time, and rulings that replaced the score on the pitch.
# No model learns from them. None in the EPL or La Liga since 2016/17 (checked 12 Oct 2026).
LEFT_OUT_CSV = ROOT / "data" / "manual" / "left_out_matches.csv"

# A match lasts about 2 hours with stoppages. Treat its result as known 3 hours
# after kickoff. Conservative on purpose: later is safe, earlier would leak.
RESULT_DELAY = pd.Timedelta(hours=3)

# football-data.co.uk column -> our column. Missing columns become empty.
STAT_COLUMNS = {
    "FTHG": "home_goals", "FTAG": "away_goals",
    "HTHG": "ht_home_goals", "HTAG": "ht_away_goals",
    "HS": "home_shots", "AS": "away_shots",
    "HST": "home_sot", "AST": "away_sot",
    "HF": "home_fouls", "AF": "away_fouls",
    "HC": "home_corners", "AC": "away_corners",
    "HY": "home_yellows", "AY": "away_yellows",
    "HR": "home_reds", "AR": "away_reds",
}
COUNT_COLUMNS = list(STAT_COLUMNS.values())

# Benchmark odds only. Never model features (spec S5.5).
# pin = Pinnacle, bfe = Betfair Exchange, avg = market average.
# pre = Friday or Tuesday afternoon snapshot, close = closing price.
ODDS_COLUMNS = {
    "PSH": "odds_pin_pre_home", "PSD": "odds_pin_pre_draw", "PSA": "odds_pin_pre_away",
    "PSCH": "odds_pin_close_home", "PSCD": "odds_pin_close_draw", "PSCA": "odds_pin_close_away",
    "BFEH": "odds_bfe_pre_home", "BFED": "odds_bfe_pre_draw", "BFEA": "odds_bfe_pre_away",
    "BFECH": "odds_bfe_close_home", "BFECD": "odds_bfe_close_draw", "BFECA": "odds_bfe_close_away",
    "AvgH": "odds_avg_pre_home", "AvgD": "odds_avg_pre_draw", "AvgA": "odds_avg_pre_away",
    "AvgCH": "odds_avg_close_home", "AvgCD": "odds_avg_close_draw", "AvgCA": "odds_avg_close_away",
    "P>2.5": "odds_pin_pre_over25", "P<2.5": "odds_pin_pre_under25",
    "PC>2.5": "odds_pin_close_over25", "PC<2.5": "odds_pin_close_under25",
    "BFE>2.5": "odds_bfe_pre_over25", "BFE<2.5": "odds_bfe_pre_under25",
    "BFEC>2.5": "odds_bfe_close_over25", "BFEC<2.5": "odds_bfe_close_under25",
    "Avg>2.5": "odds_avg_pre_over25", "Avg<2.5": "odds_avg_pre_under25",
    "AvgC>2.5": "odds_avg_close_over25", "AvgC<2.5": "odds_avg_close_under25",
    "AHh": "ah_line_pre", "AvgAHH": "odds_avg_pre_ah_home", "AvgAHA": "odds_avg_pre_ah_away",
    "AHCh": "ah_line_close", "AvgCAHH": "odds_avg_close_ah_home",
    "AvgCAHA": "odds_avg_close_ah_away",
}


def processed_dir(league: str) -> Path:
    """Where a league's processed tables live."""
    return PROCESSED if leagues.get(league).status == "live" else TRIAL_DIR


def match_id(league: str, season: int, home_id: str, away_id: str) -> str:
    """Stable ID. Each pair of clubs meets once at each ground per season."""
    return f"{league}_{fd.season_code(season)}_{home_id}_{away_id}"


def _latest(source: str, filename: str):
    copies = cached_copies(source, filename)
    if not copies:
        raise FileNotFoundError(f"{source}/{filename} not downloaded. Run `make data`.")
    return copies[-1]


def _calendar(division: str, season: int) -> pd.DataFrame:
    """openfootball rows for one league-season, keyed by team IDs."""
    league, code = TOP_DIVISIONS[division]
    path = _latest(openfootball.SOURCE, f"{code}_{fd.season_code(season)}.json")
    cal = openfootball.read(path, code)
    cal["home_id"] = map_series(cal["team1"], openfootball.SOURCE)
    cal["away_id"] = map_series(cal["team2"], openfootball.SOURCE)
    cal["league"] = league
    cal["season"] = season
    cal["match_id"] = [
        match_id(league, season, h, a) for h, a in zip(cal["home_id"], cal["away_id"], strict=True)
    ]
    return cal


def _numeric(raw: pd.DataFrame, column: str) -> pd.Series:
    """A numeric column, or all-missing if this season's file lacks it."""
    if column not in raw:
        return pd.Series(float("nan"), index=raw.index)
    return pd.to_numeric(raw[column], errors="coerce")


def _uk_kickoff(frame: pd.DataFrame) -> pd.Series:
    """football-data.co.uk Date and Time are UK local time. Blank if no Time column."""
    if "Time" not in frame:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
    local = pd.to_datetime(frame["Date"] + " " + frame["Time"], dayfirst=True, format="mixed")
    return local.dt.tz_localize("Europe/London").dt.tz_convert("UTC")


def build_top_tier(division: str, season: int) -> pd.DataFrame:
    league, _ = TOP_DIVISIONS[division]
    raw = fd.read_csv(_latest(fd.SOURCE, f"{division}_{fd.season_code(season)}.csv"))

    out = pd.DataFrame({
        "league": league,
        "division": division,
        "season": season,
        "home_id": map_series(raw["HomeTeam"], fd.SOURCE),
        "away_id": map_series(raw["AwayTeam"], fd.SOURCE),
        "match_date": pd.to_datetime(raw["Date"], dayfirst=True, format="mixed").dt.date,
    })
    out["match_id"] = [
        match_id(league, season, h, a) for h, a in zip(out["home_id"], out["away_id"], strict=True)
    ]
    for src, dst in {**STAT_COLUMNS, **ODDS_COLUMNS}.items():
        out[dst] = _numeric(raw, src)
    # Decimal odds must exceed 1. The source uses 0 as a placeholder now and then
    # (e.g. Barcelona v Girona, 18 Oct 2025). Treat those as missing.
    for dst in ODDS_COLUMNS.values():
        if dst.startswith("odds_"):
            bad = out[dst] <= 1.0
            if bad.any():
                log.warning("%s %s: %d impossible %s values set to missing",
                            division, season, int(bad.sum()), dst)
                out.loc[bad, dst] = float("nan")
    out["referee"] = raw["Referee"].str.strip() if "Referee" in raw else None
    out["home_xg"] = _numeric(raw, "HxG")
    out["away_xg"] = _numeric(raw, "AxG")

    # Kickoff: the football-data.co.uk time when present, since it records when the
    # match was actually played. Otherwise the openfootball time on the same date.
    fd_kickoff = _uk_kickoff(raw)
    cal = _calendar(division, season).set_index("match_id")
    of_kickoff = out["match_id"].map(cal["kickoff_utc"])
    of_date = out["match_id"].map(pd.to_datetime(cal["date"]).dt.date)
    same_day = of_date == out["match_date"]
    out["kickoff_utc"] = fd_kickoff.where(fd_kickoff.notna(), of_kickoff.where(same_day))
    out["kickoff_source"] = "football_data_co_uk"
    out.loc[fd_kickoff.isna() & same_day, "kickoff_source"] = "openfootball"
    # Last resort: noon UTC on the match date, flagged, and its result held back
    # a further 12 hours so it can never leak. No match needs this as of Sep 2026.
    missing = out["kickoff_utc"].isna()
    noon = pd.to_datetime(out["match_date"]).dt.tz_localize("UTC") + pd.Timedelta(hours=12)
    out.loc[missing, "kickoff_utc"] = noon[missing]
    out.loc[missing, "kickoff_source"] = "date_only"
    out["round"] = out["match_id"].map(cal["round"])

    delay = pd.Series(RESULT_DELAY, index=out.index).where(~missing, pd.Timedelta(hours=15))
    out["result_available_utc"] = out["kickoff_utc"] + delay
    for column in COUNT_COLUMNS:
        out[column] = out[column].astype("Int64")
    dropped = out["match_id"].isin(left_out())
    if dropped.any():
        log.info("%s %s: left out %d matches with no football result",
                 division, season, int(dropped.sum()))
    return out[~dropped].reset_index(drop=True)


def left_out() -> set[str]:
    return set(pd.read_csv(LEFT_OUT_CSV)["match_id"])


def build_matches(group: Group = leagues.LIVE) -> pd.DataFrame:
    frames = [build_top_tier(lg.division, y) for lg in group for y in fd.seasons()]
    matches = pd.concat(frames, ignore_index=True)
    return matches.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)


def fill_kickoffs(cal: pd.DataFrame, league: leagues.League, season: int,
                  times: pd.DataFrame | None = None) -> pd.DataFrame:
    """Kickoff times from football-data.org wherever it has set one.

    openfootball lags the leagues' announcements. On 24 Oct 2026 every La Liga match
    from matchday 10 on had a placeholder Sunday date and no time, so none could
    lock, while football-data.org had set all ten matchday 10 times by 13 Oct.
    Its EPL file also gave the 7 Nov round default Saturday 15:00 times that
    football-data.org had already moved to the real slots.

    So, when football-data.org marks a time as set (fdorg.TIME_SET), its time and
    date are used, both where openfootball is blank and where the two differ (Lang
    chose this on 24 Oct 2026). Otherwise openfootball's time stays. The date
    follows the kickoff in local time. A locked match whose kickoff changes locks
    again only if it moved more than 7 days (fp.pipeline.daily.candidates).

    `times` (home_id, away_id, kickoff_utc) defaults to the newest cached file.
    """
    out = cal.copy()
    out["kickoff_source"] = pd.Series("openfootball", index=out.index).where(
        out["time_confirmed"])
    if times is None:
        copies = cached_copies(fdorg.SOURCE, f"{league.fdorg}_{season}.json")
        if not copies:
            return out
        times = fdorg.set_kickoffs(copies[-1])
    lookup = {(h, a): k for h, a, k in times[["home_id", "away_id", "kickoff_utc"]].itertuples(
        index=False)}
    found = pd.to_datetime(pd.Series([lookup.get((h, a)) for h, a in zip(
        out["home_id"], out["away_id"], strict=True)], index=out.index, dtype=object), utc=True)

    blank = ~out["time_confirmed"] & found.notna()
    differ = out["time_confirmed"] & found.notna() & (out["kickoff_utc"] != found)
    if differ.any():  # logged before the change, while openfootball's time is still here
        both = out.loc[differ, ["match_id", "kickoff_utc"]].assign(theirs=found[differ])
        first = both.sort_values("theirs").iloc[0]
        log.info("%s: %d kickoff times from football-data.org where openfootball differs. "
                 "Earliest: %s %s UTC (openfootball %s UTC)",
                 league.code, int(differ.sum()), first["match_id"],
                 f"{first['theirs']:%a %d %b %H:%M}", f"{first['kickoff_utc']:%a %d %b %H:%M}")
    if blank.any():
        log.info("%s: %d kickoff times from football-data.org (blank in openfootball)",
                 league.code, int(blank.sum()))

    use = blank | differ
    out.loc[use, "kickoff_utc"] = found[use].astype(out["kickoff_utc"].dtype)
    out.loc[use, "time_confirmed"] = True
    out.loc[use, "date"] = found[use].dt.tz_convert(league.time_zone).dt.strftime("%Y-%m-%d")
    out.loc[use, "kickoff_source"] = fdorg.SOURCE
    return out


def build_fixtures(season: int = fd.CURRENT_SEASON, group: Group = leagues.LIVE) -> pd.DataFrame:
    """The full calendar for one season from openfootball, with kickoff times from
    football-data.org wherever it has set one (fill_kickoffs)."""
    frames = []
    for lg in group:
        cal = fill_kickoffs(_calendar(lg.division, season), lg, season)
        cal["status"] = cal["home_goals"].notna().map({True: "played", False: "scheduled"})
        frames.append(cal[[
            "match_id", "league", "season", "round", "date", "kickoff_utc", "time_confirmed",
            "kickoff_source", "home_id", "away_id", "home_goals", "away_goals", "status",
        ]])
    return pd.concat(frames, ignore_index=True).sort_values(["date", "match_id"])


def build_second_tier(group: Group = leagues.LIVE) -> pd.DataFrame:
    """Second-tier results. Clubs never promoted have no canonical ID, so names stay."""
    frames = []
    for division, league in ((lg.second, lg.code) for lg in group):
        for season in fd.seasons():
            raw = fd.read_csv(_latest(fd.SOURCE, f"{division}_{fd.season_code(season)}.csv"))
            frame = pd.DataFrame({
                "league": league,
                "division": division,
                "season": season,
                "match_date": pd.to_datetime(raw["Date"], dayfirst=True, format="mixed").dt.date,
                "home_name": raw["HomeTeam"].str.strip(),
                "away_name": raw["AwayTeam"].str.strip(),
            })
            for src, dst in STAT_COLUMNS.items():
                frame[dst] = _numeric(raw, src)
            frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    ids: dict[str, str | None] = {}
    for name in set(out["home_name"]) | set(out["away_name"]):
        try:
            ids[name] = to_team_id(name, fd.SOURCE)
        except KeyError:
            ids[name] = None
    out["home_id"] = out["home_name"].map(ids)
    out["away_id"] = out["away_name"].map(ids)
    # No kickoff times before 2019/20 here, so results count as known at the end
    # of the match day, UTC.
    out["result_available_utc"] = pd.to_datetime(out["match_date"]).dt.tz_localize(
        "UTC"
    ) + pd.Timedelta(days=1)
    for column in COUNT_COLUMNS:
        out[column] = out[column].astype("Int64")
    return out


def build_referee_appointments() -> pd.DataFrame:
    """EPL referees from every cached fixtures.csv, stamped when we first saw them.

    first_seen_utc is the file's download time, so an appointment only counts as
    known from the moment our pipeline actually had it.
    """
    rows = []
    for path in cached_copies(fd.SOURCE, "fixtures.csv"):
        seen = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        raw = fd.read_csv(path)
        raw = raw[(raw["Div"] == "E0") & raw["Referee"].notna()]
        for _, r in raw.iterrows():
            date = pd.to_datetime(r["Date"], dayfirst=True)
            season = date.year if date.month >= 7 else date.year - 1
            home, away = to_team_id(r["HomeTeam"], fd.SOURCE), to_team_id(r["AwayTeam"], fd.SOURCE)
            rows.append({
                "match_id": match_id("EPL", season, home, away),
                "referee": r["Referee"].strip(),
                "first_seen_utc": pd.Timestamp(seen),
            })
    columns = ["match_id", "referee", "first_seen_utc"]
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows).sort_values("first_seen_utc")
    return frame.drop_duplicates(["match_id", "referee"], keep="first")[columns]
