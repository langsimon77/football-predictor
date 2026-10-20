"""Club results across Europe for the Champions League model (Lang approved the
goals markets only, 14 Oct 2026; work restarted 20 Oct 2026).

Two kinds of rows, one club ID per club:
- domestic league matches from football-data.co.uk: the main files (E0, SP1, I1, F1,
  D1, N1, P1, B1, T1, SC0, G1) and the results-only files of eight more leagues (AUT,
  SWZ, DNK, NOR, SWE, POL, ROU, RUS), 2016/17 onward;
- UEFA club competition matches from openfootball (fp.ingest.uefa).

Club IDs: the project's team IDs for English, Spanish, Italian and French clubs;
"<country>_<name>" for the rest. data/manual/uefa_club_aliases.csv joins every
European spelling to its ID (377 spellings, 342 clubs, checked by hand on 20 Oct 2026).
Clubs from leagues without a free source (for example Croatia or Ukraine) are rated
from their European matches only.

Domestic results count as known at the end of their match day, UTC (no kickoff time
in most files); European results three hours after kickoff.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

import pandas as pd

from fp import ROOT
from fp.ingest import football_data_csv as fd
from fp.ingest import uefa
from fp.ingest.http import cached_copies, fetch
from fp.ingest.matches import _latest
from fp.teams import to_team_id

ALIASES_CSV = ROOT / "data" / "manual" / "uefa_club_aliases.csv"
MAIN = {"E0": "ENG", "SP1": "ESP", "I1": "ITA", "F1": "FRA", "D1": "GER", "N1": "NED",
        "P1": "POR", "B1": "BEL", "T1": "TUR", "SC0": "SCO", "G1": "GRE"}
EXTRA = {"AUT": "AUT", "SWZ": "SUI", "DNK": "DEN", "NOR": "NOR", "SWE": "SWE", "POL": "POL",
         "ROU": "ROU", "RUS": "RUS"}
BIG4 = {"ENG", "ESP", "ITA", "FRA"}
# One club under two names in one source: the Romanian file switches spelling for
# Universitatea Craiova during 2020/21 (U Craiova 1948 is a different club).
DOMESTIC_MERGES = {("ROU", "U Craiova"): "Univ. Craiova"}
FIRST_DATE = pd.Timestamp("2016-07-01")
COLUMNS = ["match_id", "competition", "kind", "season", "date", "kickoff_utc",
           "result_available_utc", "home_id", "away_id", "home_goals", "away_goals",
           "neutral", "round"]


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def domestic_id(country: str, name: str) -> str:
    name = name.strip()
    if country in BIG4:
        return to_team_id(name, fd.SOURCE)
    return f"{country.lower()}_{slug(DOMESTIC_MERGES.get((country, name), name))}"


@cache
def _aliases() -> dict[tuple[str, str], str]:
    a = pd.read_csv(ALIASES_CSV)
    return {(c, unicodedata.normalize("NFC", n)): i
            for c, n, i in zip(a["country"], a["uefa_name"], a["club_id"], strict=True)}


def uefa_id(country: str, name: str) -> str:
    """The club ID of a European spelling; raises KeyError for an unknown one."""
    return _aliases()[(country, unicodedata.normalize("NFC", name.strip()))]


def season_of(day: pd.Timestamp) -> int:
    return day.year if day.month >= 7 else day.year - 1


def download_domestic() -> None:
    for div in MAIN:
        for y in fd.seasons():
            fd.download_division(div, y)
    for code in EXTRA:
        fetch(f"{fd.BASE_URL}/new/{code}.csv", fd.SOURCE, f"new_{code}.csv")


def _frame(rows: pd.DataFrame, competition: str, country: str, home: str, away: str,
           hg: str, ag: str) -> pd.DataFrame:
    day = pd.to_datetime(rows["Date"], dayfirst=True, format="mixed")
    out = pd.DataFrame({
        "competition": competition, "kind": "domestic",
        "date": day.dt.date, "season": day.map(season_of),
        "home_id": [domestic_id(country, n) for n in rows[home]],
        "away_id": [domestic_id(country, n) for n in rows[away]],
        "home_goals": pd.to_numeric(rows[hg], errors="coerce"),
        "away_goals": pd.to_numeric(rows[ag], errors="coerce"),
        "neutral": False, "round": None,
    })
    utc = day.dt.tz_localize("UTC")
    out["kickoff_utc"] = utc + pd.Timedelta(hours=12)  # order only; no time in most files
    out["result_available_utc"] = utc + pd.Timedelta(days=1)
    return out


def domestic_matches() -> pd.DataFrame:
    frames = []
    for div, country in MAIN.items():
        for y in fd.seasons():
            raw = fd.read_csv(_latest(fd.SOURCE, f"{div}_{fd.season_code(y)}.csv"))
            raw = raw.dropna(subset=["HomeTeam", "AwayTeam"])
            frames.append(_frame(raw, div, country, "HomeTeam", "AwayTeam", "FTHG", "FTAG"))
    for code, country in EXTRA.items():
        raw = fd.read_csv(cached_copies(fd.SOURCE, f"new_{code}.csv")[-1])
        raw = raw.dropna(subset=["Home", "Away"])
        raw = raw[pd.to_datetime(raw["Date"], dayfirst=True, format="mixed") >= FIRST_DATE]
        frames.append(_frame(raw, code, country, "Home", "Away", "HG", "AG"))
    out = pd.concat(frames, ignore_index=True).dropna(subset=["home_goals", "away_goals"])
    return _finish(out)


def european_matches(current_season: int = fd.CURRENT_SEASON) -> pd.DataFrame:
    """Every UEFA club competition match in openfootball's completed seasons. The
    current season comes from football-data.org (openfootball has no 2026/27 files)."""
    raw = uefa.load(range(fd.FIRST_SEASON, current_season), current_season)
    day = pd.to_datetime(raw["date"])
    out = pd.DataFrame({
        "competition": raw["competition"], "kind": "europe", "season": raw["season"],
        "date": raw["date"], "neutral": raw["neutral"], "round": raw["round"],
        "home_id": [uefa_id(c, n) for c, n in zip(raw["home_country"], raw["home_name"],
                                                   strict=True)],
        "away_id": [uefa_id(c, n) for c, n in zip(raw["away_country"], raw["away_name"],
                                                   strict=True)],
        "home_goals": raw["home_goals"].astype("Float64"),
        "away_goals": raw["away_goals"].astype("Float64"),
    })
    kick = raw["kickoff_utc"]
    out["kickoff_utc"] = kick.where(kick.notna(), day.dt.tz_localize("UTC")
                                    + pd.Timedelta(hours=19))
    out["result_available_utc"] = out["kickoff_utc"] + pd.Timedelta(hours=3)
    out.loc[kick.isna(), "result_available_utc"] = (day[kick.isna()].dt.tz_localize("UTC")
                                                    + pd.Timedelta(days=1))
    return _finish(out)


def _finish(out: pd.DataFrame) -> pd.DataFrame:
    out["match_id"] = [f"{c}_{fd.season_code(int(s))}_{h}_{a}_{d}" for c, s, h, a, d in
                       zip(out["competition"], out["season"], out["home_id"], out["away_id"],
                           out["date"], strict=True)]
    out["kickoff_utc"] = pd.to_datetime(out["kickoff_utc"], utc=True)
    out["result_available_utc"] = pd.to_datetime(out["result_available_utc"], utc=True)
    return out[COLUMNS].sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)


def all_matches(current_season: int = fd.CURRENT_SEASON) -> pd.DataFrame:
    return pd.concat([domestic_matches(), european_matches(current_season)],
                     ignore_index=True).sort_values(["kickoff_utc", "match_id"]
                                                    ).reset_index(drop=True)
