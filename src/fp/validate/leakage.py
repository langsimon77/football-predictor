"""The as_of rule: a prediction may only use what was known at its lock time.

Two tools:
- lock_time(kickoff): when the daily run locks a match. This is the as_of for the
  backtest, so the backtest sees exactly what the live system would have seen.
- known_as_of(table, as_of): the rows of a table whose outcome was known by as_of.

Every feature table carries as_of_utc and source_max_utc (the latest
result_available_utc of any row used to build it). check_features() fails loudly
if any source_max_utc is after its as_of_utc.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

# Daily run time in UTC. Off the hour because GitHub delays top-of-hour cron jobs
# (PRD item 24). 04:41 UTC is 06:41 in Juba.
RUN_TIME_UTC = time(4, 41)
LOCK_MIN_HOURS = 24
LOCK_MAX_HOURS = 48


class LeakageError(AssertionError):
    """A feature used information from after its as_of time."""


def lock_time(kickoff_utc: pd.Series | pd.Timestamp) -> pd.Series | pd.Timestamp:
    """The scheduled daily run that locks a match kicking off at kickoff_utc.

    It is the latest run at or before kickoff minus 24 hours, so every lock falls
    between 24 and 48 hours before kickoff.
    """
    run_offset = pd.Timedelta(hours=RUN_TIME_UTC.hour, minutes=RUN_TIME_UTC.minute)
    # Shift so each run time lands on midnight, floor to the day, shift back.
    shifted = kickoff_utc - pd.Timedelta(hours=LOCK_MIN_HOURS) - run_offset
    floored = shifted.floor("D") if isinstance(shifted, pd.Timestamp) else shifted.dt.floor("D")
    return floored + run_offset


def known_as_of(table: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Rows whose outcome was known at as_of. Everything later is invisible."""
    return table[table["result_available_utc"] <= as_of]


def check_features(features: pd.DataFrame) -> None:
    """Raise LeakageError if any feature row used data from after its as_of."""
    for column in ("as_of_utc", "source_max_utc"):
        if column not in features:
            raise LeakageError(f"feature table is missing {column}")
    late = features["source_max_utc"] > features["as_of_utc"]
    if late.any():
        sample = features.loc[late].head(5).to_dict("records")
        raise LeakageError(f"{int(late.sum())} feature rows use future data, e.g. {sample}")
