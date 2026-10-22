"""Where the Europe pipeline reads and writes. Set EURO_SOURCES and EURO_WORK to override."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
# The four public sources (fetch_sources.py), outside Git like all raw data.
SOURCES = Path(os.environ.get("EURO_SOURCES", REPO / "data" / "raw" / "euro_sources"))
# Intermediate files (pickles), outside Git.
WORK = Path(os.environ.get("EURO_WORK", REPO / "data" / "interim" / "euro"))
# Outputs read by the Model Lab build (committed by the daily run).
OUT = Path(os.environ.get("EURO_OUT", REPO / "data" / "euro"))
# The run date (EURO_RUN_DATE, default today in UTC): forecasts are made on it from results
# known by the end of the day before (CUTOFF).
from datetime import date, datetime, timedelta, timezone  # noqa: E402

RUN_DATE = date.fromisoformat(os.environ["EURO_RUN_DATE"]) if os.environ.get("EURO_RUN_DATE") else datetime.now(timezone.utc).date()
CUTOFF = (RUN_DATE - timedelta(days=1)).isoformat()
RUN_ISO = RUN_DATE.isoformat()
for p in (SOURCES, WORK, OUT):
    p.mkdir(parents=True, exist_ok=True)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
