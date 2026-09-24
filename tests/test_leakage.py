"""The as_of rule (spec S4): no feature may use data from after its lock time."""

from __future__ import annotations

import pandas as pd
import pytest

from fp.validate import leakage

UTC = "UTC"


@pytest.mark.parametrize(
    "kickoff",
    [
        "2026-09-20 13:00",  # Sunday afternoon
        "2026-10-09 19:00",  # Friday night
        "2026-10-10 04:00",  # before the run time
        "2026-10-10 04:41",  # exactly on a run time
        "2026-10-10 04:42",  # one minute after
        "2026-12-26 12:30",
    ],
)
def test_every_lock_falls_24_to_48_hours_before_kickoff(kickoff):
    k = pd.Timestamp(kickoff, tz=UTC)
    lock = leakage.lock_time(k)
    hours = (k - lock) / pd.Timedelta(hours=1)
    assert 24 <= hours < 48
    assert (lock.hour, lock.minute) == (leakage.RUN_TIME_UTC.hour, leakage.RUN_TIME_UTC.minute)


def test_worked_example_from_learn_md():
    """Man City v Sunderland, 13:00 UTC Sun 20 Sep 2026, locks on Saturday morning."""
    lock = leakage.lock_time(pd.Timestamp("2026-09-20 13:00", tz=UTC))
    assert lock == pd.Timestamp("2026-09-19 04:41", tz=UTC)


def test_lock_time_works_on_a_column():
    kickoffs = pd.Series(pd.to_datetime(["2026-09-20 13:00", "2026-10-09 19:00"], utc=True))
    locks = leakage.lock_time(kickoffs)
    assert ((kickoffs - locks) >= pd.Timedelta(hours=24)).all()


def test_known_as_of_hides_results_that_came_in_after_the_lock():
    table = pd.DataFrame({
        "match_id": ["brighton_arsenal", "earlier"],
        "result_available_utc": pd.to_datetime(["2026-09-19 17:00", "2026-09-14 22:00"], utc=True),
    })
    visible = leakage.known_as_of(table, pd.Timestamp("2026-09-19 04:41", tz=UTC))
    assert list(visible["match_id"]) == ["earlier"]


def test_check_features_passes_clean_rows():
    features = pd.DataFrame({
        "as_of_utc": pd.to_datetime(["2026-09-19 04:41"], utc=True),
        "source_max_utc": pd.to_datetime(["2026-09-17 22:00"], utc=True),
    })
    leakage.check_features(features)


def test_check_features_catches_a_future_input():
    features = pd.DataFrame({
        "as_of_utc": pd.to_datetime(["2026-09-19 04:41"], utc=True),
        "source_max_utc": pd.to_datetime(["2026-09-19 17:00"], utc=True),
    })
    with pytest.raises(leakage.LeakageError, match="future"):
        leakage.check_features(features)


def test_check_features_requires_timestamps():
    with pytest.raises(leakage.LeakageError, match="missing"):
        leakage.check_features(pd.DataFrame({"x": [1]}))
