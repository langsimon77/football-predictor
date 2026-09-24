"""`make data`: download, build, validate, and load everything into DuckDB.

Steps:
1. Download football-data.co.uk and openfootball files (cached, rate-limited).
2. Build the processed tables.
3. Validate every table with pandera. Any failure stops the run.
4. Run the freshness check.
5. Write Parquet files and a DuckDB database that views them.
"""

from __future__ import annotations

import logging
import sys

import duckdb

from fp.ingest import football_data_csv as fd
from fp.ingest import matches as build
from fp.ingest import openfootball
from fp.validate import freshness, schemas

DUCKDB_PATH = build.PROCESSED / "football.duckdb"

TABLES = {
    "matches": (build.build_matches, schemas.matches_schema),
    "fixtures": (build.build_fixtures, schemas.fixtures_schema),
    "second_tier": (build.build_second_tier, schemas.second_tier_schema),
    "referee_appointments": (build.build_referee_appointments, schemas.referee_schema),
}


def download() -> None:
    openfootball.download_all()
    fd.download_all()
    fd.download_fixtures()


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
    sys.exit(main(skip_download="--offline" in sys.argv))
