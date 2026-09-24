"""The validation must reject bad data, not just accept good data (spec S4)."""

from __future__ import annotations

import pandas as pd
import pandera.errors
import pytest

from fp.ingest import matches as build
from fp.ingest.http import cached_copies
from fp.validate import schemas


@pytest.fixture(scope="module")
def matches() -> pd.DataFrame:
    if not cached_copies("football_data_co_uk", "E0_2627.csv"):
        pytest.skip("raw data not downloaded; run `make data`")
    return build.build_matches()


def test_real_data_passes(matches):
    schemas.matches_schema().validate(matches, lazy=True)


def rejects(frame: pd.DataFrame) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        schemas.matches_schema().validate(frame, lazy=True)


def test_duplicate_match_rejected(matches):
    rejects(pd.concat([matches, matches.tail(1)], ignore_index=True))


def test_negative_goals_rejected(matches):
    bad = matches.copy()
    bad.loc[0, "home_goals"] = -1
    rejects(bad)


def test_naive_kickoff_rejected(matches):
    bad = matches.copy()
    bad["kickoff_utc"] = bad["kickoff_utc"].dt.tz_localize(None)
    rejects(bad)


def test_unmapped_team_rejected(matches):
    bad = matches.copy()
    bad.loc[0, "home_id"] = "real_madrid_castilla"
    rejects(bad)


def test_result_known_before_kickoff_rejected(matches):
    bad = matches.copy()
    bad.loc[0, "result_available_utc"] = bad.loc[0, "kickoff_utc"]
    rejects(bad)


def test_missing_match_in_finished_season_rejected(matches):
    rejects(matches[matches["match_id"] != matches.loc[0, "match_id"]].reset_index(drop=True))


def test_impossible_odds_rejected(matches):
    bad = matches.copy()
    bad.loc[0, "odds_avg_close_home"] = 0.0
    rejects(bad)


def test_every_result_is_known_three_hours_after_kickoff(matches):
    gap = matches["result_available_utc"] - matches["kickoff_utc"]
    assert (gap >= build.RESULT_DELAY).all()


def test_placeholder_zero_odds_are_cleaned(matches):
    """Barcelona v Girona, 18 Oct 2025, has 0.0 Pinnacle closing O/U odds in the source."""
    row = matches.set_index("match_id").loc["LaLiga_2526_barcelona_girona"]
    assert pd.isna(row["odds_pin_close_over25"])
