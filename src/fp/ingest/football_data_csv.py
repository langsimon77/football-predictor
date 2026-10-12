"""Download and read the football-data.co.uk match CSVs.

Files: E0 (Premier League), SP1 (La Liga), E1 (Championship), SP2 (Segunda), and
for the leagues on trial I1 (Serie A), F1 (Ligue 1), I2 (Serie B), F2 (Ligue 2).
Second divisions feed the promoted-team priors.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fp import leagues
from fp.ingest.http import fetch

SOURCE = "football_data_co_uk"
BASE_URL = "https://football-data.co.uk"
FIRST_SEASON = 2016  # 2016/17, per PRD item 20
CURRENT_SEASON = 2026  # 2026/27


def season_code(start_year: int) -> str:
    """2026 -> '2627', the code the site uses in its URLs."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def seasons() -> list[int]:
    return list(range(FIRST_SEASON, CURRENT_SEASON + 1))


def download_division(division: str, start_year: int) -> Path:
    code = season_code(start_year)
    url = f"{BASE_URL}/mmz4281/{code}/{division}.csv"
    # Completed seasons never change, so any cached copy will do.
    return fetch(url, SOURCE, f"{division}_{code}.csv", refresh=start_year == CURRENT_SEASON)


def download_fixtures() -> Path:
    """Upcoming fixtures with pre-match odds, all divisions in one file."""
    return fetch(f"{BASE_URL}/fixtures.csv", SOURCE, "fixtures.csv")


def read_csv(path: Path) -> pd.DataFrame:
    """Read one file. Older files are Latin-1, newer ones UTF-8."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            frame = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    # Some files carry empty trailing rows and columns.
    frame = frame.dropna(how="all").loc[:, lambda f: ~f.columns.str.startswith("Unnamed")]
    return frame


def divisions(group: tuple[leagues.League, ...]) -> tuple[str, ...]:
    """Top divisions first, then second divisions: ("E0", "SP1", "E1", "SP2") when live."""
    return tuple(lg.division for lg in group) + tuple(lg.second for lg in group)


DIVISIONS = divisions(leagues.LIVE)


def download_all(group: tuple[leagues.League, ...] = leagues.LIVE) -> dict[tuple[str, int], Path]:
    paths = {}
    for start_year in seasons():
        for division in divisions(group):
            paths[(division, start_year)] = download_division(division, start_year)
    return paths
