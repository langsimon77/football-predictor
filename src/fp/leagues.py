"""Every league the project knows, in one table.

status "live": downloaded every day, forecast, and published.
status "trial": downloaded and backtested only. Nothing is forecast or published,
and no live table holds a trial row. Lang chose Serie A and Ligue 1 as the next
leagues on 12 Oct 2026; they stay on trial until Lang approves publishing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    code: str  # our name, used in match IDs: "EPL"
    name: str  # for people: "Premier League"
    division: str  # football-data.co.uk top division
    second: str  # football-data.co.uk second division, for promoted-team priors
    openfootball: str  # openfootball file code
    time_zone: str  # local time of the openfootball kickoff times
    fdorg: str  # football-data.org competition code
    status: str  # "live" or "trial"


ALL = (
    League("EPL", "Premier League", "E0", "E1", "en.1", "Europe/London", "PL", "live"),
    League("LaLiga", "La Liga", "SP1", "SP2", "es.1", "Europe/Madrid", "PD", "live"),
    League("SerieA", "Serie A", "I1", "I2", "it.1", "Europe/Rome", "SA", "trial"),
    League("Ligue1", "Ligue 1", "F1", "F2", "fr.1", "Europe/Paris", "FL1", "trial"),
)

LIVE = tuple(lg for lg in ALL if lg.status == "live")
TRIAL = tuple(lg for lg in ALL if lg.status == "trial")
BY_CODE = {lg.code: lg for lg in ALL}
BY_DIVISION = {lg.division: lg for lg in ALL}


def get(code: str) -> League:
    return BY_CODE[code]


def clubs(code: str, season: int) -> int:
    """Ligue 1 has had 18 clubs since 2023/24. Every other league-season here has 20."""
    return 18 if code == "Ligue1" and season >= 2023 else 20


# Seasons stopped early by COVID-19: the number of matches actually played.
CUT_SHORT = {("Ligue1", 2019): 279}


def season_length(code: str, season: int) -> int:
    """Matches in a full season, or in a season stopped early."""
    n = clubs(code, season)
    return CUT_SHORT.get((code, season), n * (n - 1))


def codes_in(values: Iterable[str]) -> list[str]:
    """League codes present in a column, in this table's order (EPL first).

    Code that pools leagues loops over this, so a live table gives exactly the
    live leagues and a trial table exactly the trial ones.
    """
    present = set(values)
    return [lg.code for lg in ALL if lg.code in present]
