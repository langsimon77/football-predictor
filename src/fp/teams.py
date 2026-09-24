"""Canonical team IDs.

Every source spells team names its own way ("Man United", "Manchester United FC").
data/manual/teams.csv gives each club one ID. data/manual/team_aliases.csv maps
each source's spelling to that ID. All code joins on team_id, never on a name.
"""

from __future__ import annotations

import unicodedata
from functools import cache

import pandas as pd

from fp import ROOT

TEAMS_CSV = ROOT / "data" / "manual" / "teams.csv"
ALIASES_CSV = ROOT / "data" / "manual" / "team_aliases.csv"


class UnknownTeamError(KeyError):
    """A source used a team name that has no alias yet."""


@cache
def teams() -> pd.DataFrame:
    return pd.read_csv(TEAMS_CSV)


@cache
def aliases() -> pd.DataFrame:
    return pd.read_csv(ALIASES_CSV)


def _normalise(name: str) -> str:
    # The same accented letter can be stored two ways in Unicode ("á" as one
    # character or as "a" plus an accent). NFC picks one form so they match.
    return unicodedata.normalize("NFC", name.strip())


@cache
def _lookup(source: str) -> dict[str, str]:
    rows = aliases().query("source == @source")
    return {_normalise(a): t for a, t in zip(rows["alias"], rows["team_id"], strict=True)}


def to_team_id(name: str, source: str) -> str:
    """Map one source spelling to its canonical team ID, or raise."""
    try:
        return _lookup(source)[_normalise(name)]
    except KeyError:
        raise UnknownTeamError(f"No alias for {name!r} from source {source!r}") from None


def map_series(names: pd.Series, source: str) -> pd.Series:
    """Map a column of names. Raises on the first unknown name."""
    return names.map(lambda n: to_team_id(n, source))
