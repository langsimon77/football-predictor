"""pandera schemas: every processed table is checked before anything uses it.

Checks required by spec S4: no duplicate matches, goals and counts non-negative,
kickoff times in UTC, every team mapped.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from fp import leagues
from fp.ingest.football_data_csv import CURRENT_SEASON, FIRST_SEASON, season_code
from fp.ingest.matches import COUNT_COLUMNS, ODDS_COLUMNS, left_out
from fp.teams import teams

Group = tuple[leagues.League, ...]
LEAGUES = [lg.code for lg in leagues.LIVE]
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


def _left_out(code: str, season: int) -> int:
    """Matches with no football result, which the builder leaves out."""
    prefix = f"{code}_{season_code(season)}_"
    return sum(m.startswith(prefix) for m in left_out())


def _complete_seasons_are_full(frame: pd.DataFrame) -> bool:
    """380 matches a season (306 in Ligue 1 since 2023/24), less any left out."""
    done = frame[frame["season"] < CURRENT_SEASON]
    sizes = done.groupby(["league", "season"]).size().reset_index(name="n")
    return all(n == leagues.season_length(str(lg), int(y)) - _left_out(str(lg), int(y))
               for lg, y, n in zip(sizes["league"], sizes["season"], sizes["n"], strict=True))


def _each_team_plays_each_other_once_at_home_at_most(frame: pd.DataFrame) -> bool:
    homes = frame.groupby(["league", "season", "home_id"]).size().reset_index(name="n")
    return all(n <= leagues.clubs(str(lg), int(y)) - 1
               for lg, y, n in zip(homes["league"], homes["season"], homes["n"], strict=True))


def _right_number_of_teams(frame: pd.DataFrame) -> bool:
    teams_in = frame.groupby(["league", "season"])["home_id"].nunique().reset_index(name="n")
    return all(n == leagues.clubs(str(lg), int(y)) for lg, y, n
               in zip(teams_in["league"], teams_in["season"], teams_in["n"], strict=True))


def matches_schema(group: Group = leagues.LIVE) -> pa.DataFrameSchema:
    columns = {
        "match_id": pa.Column(str, unique=True),
        "league": pa.Column(str, pa.Check.isin([lg.code for lg in group])),
        "division": pa.Column(str, pa.Check.isin([lg.division for lg in group])),
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
            pa.Check(_complete_seasons_are_full, error="a finished season lacks matches"),
            pa.Check(_each_team_plays_each_other_once_at_home_at_most,
                     error="a team has too many home games"),
            pa.Check(_right_number_of_teams, error="a season has the wrong number of teams"),
        ],
        strict=False,
        coerce=False,
    )


def _full_calendar(frame: pd.DataFrame) -> bool:
    sizes = frame.groupby("league").size()
    return all(n == leagues.season_length(str(lg), CURRENT_SEASON) for lg, n in sizes.items())


def fixtures_schema(group: Group = leagues.LIVE) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "match_id": pa.Column(str, unique=True),
            "league": pa.Column(str, pa.Check.isin([lg.code for lg in group])),
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
            pa.Check(_full_calendar, error="calendar is not a full season"),
        ],
    )


def second_tier_schema(group: Group = leagues.LIVE) -> pa.DataFrameSchema:
    columns = {
        "division": pa.Column(str, pa.Check.isin([lg.second for lg in group])),
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
