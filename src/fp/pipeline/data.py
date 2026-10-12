"""`make data`: download, build, validate, and load everything into DuckDB.

Steps:
1. Download football-data.co.uk and openfootball files (cached, rate-limited).
2. Build the processed tables.
3. Validate every table with pandera. Any failure stops the run.
4. Run the freshness check.
5. Write Parquet files and a DuckDB database that views them.

`--trial` does steps 1 to 4 for the leagues on trial (fp.leagues) and writes their
tables to data/processed/trial/, apart from every live table.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

import duckdb
import pandas as pd
import pandera.pandas as pa

from fp import leagues
from fp.ingest import football_data_csv as fd
from fp.ingest import matches as build
from fp.ingest import openfootball
from fp.validate import freshness, schemas

DUCKDB_PATH = build.PROCESSED / "football.duckdb"
TRIAL_DIR = build.TRIAL_DIR

TABLES: dict[str, tuple[Callable[[], pd.DataFrame], Callable[[], pa.DataFrameSchema]]] = {
    "matches": (build.build_matches, schemas.matches_schema),
    "fixtures": (build.build_fixtures, schemas.fixtures_schema),
    "second_tier": (build.build_second_tier, schemas.second_tier_schema),
    "referee_appointments": (build.build_referee_appointments, schemas.referee_schema),
}


def download() -> None:
    openfootball.download_all()
    fd.download_all()
    fd.download_fixtures()


def build_trial(skip_download: bool = False) -> int:
    """The leagues on trial, validated and written to data/processed/trial/."""
    group = leagues.TRIAL
    if not skip_download:
        openfootball.download_all(group)
        fd.download_all(group)
    TRIAL_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "matches": (lambda: build.build_matches(group), schemas.matches_schema(group)),
        "fixtures": (lambda: build.build_fixtures(group=group), schemas.fixtures_schema(group)),
        "second_tier": (lambda: build.build_second_tier(group), schemas.second_tier_schema(group)),
    }
    frames = {}
    for name, (builder, schema) in tables.items():
        frame = schema.validate(builder(), lazy=True)
        frame.to_parquet(TRIAL_DIR / f"{name}.parquet", index=False)
        frames[name] = frame
        print(f"trial {name}: {len(frame):,} rows, valid")
    print(freshness.check(frames["matches"], frames["fixtures"]).summary())
    return 0


def main(skip_download: bool = False) -> int:
    if not skip_download:
        download()
    build.PROCESSED.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name, (builder, schema) in TABLES.items():
        frame = schema().validate(builder(), lazy=True)
        frame.to_parquet(build.PROCESSED / f"{name}.parquet", index=False)
        frames[name] = frame
        print(f"{name}: {len(frame):,} rows, valid")

    report = freshness.check(frames["matches"], frames["fixtures"])
    print(report.summary())

    with duckdb.connect(str(DUCKDB_PATH)) as con:
        for name in TABLES:
            path = (build.PROCESSED / f"{name}.parquet").as_posix()
            con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    print(f"DuckDB views written to {DUCKDB_PATH.relative_to(build.PROCESSED.parents[1])}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    offline = "--offline" in sys.argv
    sys.exit(build_trial(offline) if "--trial" in sys.argv else main(offline))
