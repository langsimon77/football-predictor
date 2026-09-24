"""Phase 0 data audit: download football-data.co.uk and openfootball files, print coverage.

Run with `make audit`. Every number in docs/DATA_SOURCES.md section 2 comes from this.
"""

from __future__ import annotations

import pandas as pd

from fp.ingest import football_data_csv as fd
from fp.ingest import openfootball

# Columns the models need, plus the odds columns used as benchmarks.
KEY_COLUMNS = [
    "Time", "Referee", "HxG", "HS", "HST", "HF", "HC", "HY", "HR",
    "PSH", "PSCH", "BFEH", "BFECH", "AvgH", "AvgCH", "AvgC>2.5", "AHCh",
]


def coverage(division: str, start_year: int, frame: pd.DataFrame) -> dict:
    dates = pd.to_datetime(frame["Date"], dayfirst=True, format="mixed")
    row = {
        "div": division,
        "season": fd.season_code(start_year),
        "matches": len(frame),
        "first": dates.min().date(),
        "last": dates.max().date(),
    }
    for column in KEY_COLUMNS:
        row[column] = f"{frame[column].notna().mean():.0%}" if column in frame else "-"
    return row


def main() -> None:
    openfootball.download_all()
    paths = fd.download_all()
    fixtures = fd.read_csv(fd.download_fixtures())
    rows = [coverage(d, y, fd.read_csv(p)) for (d, y), p in sorted(paths.items())]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(pd.DataFrame(rows).to_string(index=False))

    upcoming = fixtures[fixtures["Div"].isin(["E0", "SP1"])]
    print(f"\nfixtures.csv: {len(upcoming)} EPL and La Liga rows")
    columns = ["Div", "Date", "Time", "HomeTeam", "AwayTeam", "Referee"]
    print(upcoming[columns].to_string(index=False))


if __name__ == "__main__":
    main()
