"""pandera schemas: every processed table is checked before anything uses it.

Checks required by spec S4: no duplicate matches, goals and counts non-negative,
kickoff times in UTC, every team mapped.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from fp.ingest.football_data_csv import CURRENT_SEASON, FIRST_SEASON
from fp.ingest.matches import COUNT_COLUMNS, ODDS_COLUMNS
from fp.teams import teams

LEAGUES = ["EPL", "LaLiga"]
# Decimal odds columns, without the Asian handicap lines (those are goal margins).
ODDS_OUT = [c for c in ODDS_COLUMNS.values() if not c.startswith("ah_line")]


def _is_utc(series: pd.Series) -> bool:
    return isinstance(series.dtype, pd.DatetimeTZDtype) and str(series.dtype.tz) == "UTC"


def _utc(nullable: bool = False) -> pa.Column:
    """A timezone-aware UTC timestamp column, any precision. Naive times fail:
    they could be UK or Spanish local time in disguise."""
    return pa.Column(None, pa.Check(_is_utc, error="must be timezone-aware UTC"), nullable=nullable)


def _team_ids() -> list[str]:
    return list(teams()["team_id"])


def _count(nullable: bool = False) -> pa.Column:
    return pa.Column("Int64", pa.Check.ge(0), nullable=nullable)


def _odds() -> pa.Column:
    return pa.Column(float, pa.Check.gt(1.0), nullable=True)


def _complete_seasons_have_380(frame: pd.DataFrame) -> bool:
    done = frame[frame["season"] < CURRENT_SEASON]
    return bool((done.groupby(["league", "season"]).size() == 380).all())


def _each_team_at_most_19_home_games(frame: pd.DataFrame) -> bool:
    return bool((frame.groupby(["league", "season", "home_id"]).size() <= 19).all())


def _twenty_teams_per_season(frame: pd.DataFrame) -> bool:
    return bool((frame.groupby(["league", "season"])["home_id"].nunique() == 20).all())


def matches_schema() -> pa.DataFrameSchema:
    columns = {
        "match_id": pa.Column(str, unique=True),
        "league": pa.Column(str, pa.Check.isin(LEAGUES)),
        "division": pa.Column(str, pa.Check.isin(["E0", "SP1"])),
        "season": pa.Column(int, pa.Check.in_range(FIRST_SEASON, CURRENT_SEASON)),
        "home_id": pa.Column(str, pa.Check.isin(_team_ids())),
        "away_id": pa.Column(str, pa.Check.isin(_team_ids())),
        "kickoff_utc": _utc(),
        "kickoff_source": pa.Column(
            str, pa.Check.isin(["football_data_co_uk", "openfootball", "date_only"])
        ),
        "result_available_utc": _utc(),
        "home_xg": pa.Column(float, pa.Check.ge(0), nullable=True),
        "away_xg": pa.Column(float, pa.Check.ge(0), nullable=True),
        "referee": pa.Column(object, nullable=True),
    }
    columns.update({c: _count() for c in COUNT_COLUMNS})
    columns.update({c: _odds() for c in ODDS_OUT})
    columns["ah_line_pre"] = pa.Column(float, nullable=True)
    columns["ah_line_close"] = pa.Column(float, nullable=True)
    return pa.DataFrameSchema(
        columns,
        checks=[
            pa.Check(lambda f: f["home_id"] != f["away_id"], error="a team plays itself"),
            pa.Check(
                lambda f: f["result_available_utc"] > f["kickoff_utc"],
                error="result known before kickoff",
            ),
            pa.Check(_complete_seasons_have_380, error="a finished season lacks 380 matches"),
            pa.Check(_each_team_at_most_19_home_games, error="a team has over 19 home games"),
            pa.Check(_twenty_teams_per_season, error="a season does not have 20 teams"),
        ],
        strict=False,
        coerce=False,
    )


def fixtures_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "match_id": pa.Column(str, unique=True),
            "league": pa.Column(str, pa.Check.isin(LEAGUES)),
            "home_id": pa.Column(str, pa.Check.isin(_team_ids())),
            "away_id": pa.Column(str, pa.Check.isin(_team_ids())),
            "kickoff_utc": _utc(nullable=True),
            "time_confirmed": pa.Column(bool),
            "status": pa.Column(str, pa.Check.isin(["played", "scheduled"])),
            "home_goals": _count(nullable=True),
            "away_goals": _count(nullable=True),
        },
        checks=[
            pa.Check(
                lambda f: (f["status"] != "played") | f["home_goals"].notna(),
                error="a played fixture has no score",
            ),
            pa.Check(
                lambda f: f["time_confirmed"] == f["kickoff_utc"].notna(),
                error="kickoff present without a confirmed time, or the reverse",
            ),
            pa.Check(lambda f: f.groupby("league").size() == 380, error="calendar is not 380"),
        ],
    )


def second_tier_schema() -> pa.DataFrameSchema:
    columns = {
        "division": pa.Column(str, pa.Check.isin(["E1", "SP2"])),
        "home_name": pa.Column(str),
        "away_name": pa.Column(str),
        "result_available_utc": _utc(),
    }
    columns.update({c: _count(nullable=True) for c in COUNT_COLUMNS})
    return pa.DataFrameSchema(columns)


def referee_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema({
        "match_id": pa.Column(str),
        "referee": pa.Column(str),
        "first_seen_utc": _utc(),
    })
