"""As-of features must not move when a result from after the lock is added (PRD item 7)."""

from __future__ import annotations

import pandas as pd
import pytest

from fp.features import rolling
from fp.ingest.http import cached_copies


@pytest.fixture(scope="module")
def matches() -> pd.DataFrame:
    if not cached_copies("football_data_co_uk", "E0_2627.csv"):
        pytest.skip("raw data not downloaded; run `make data`")
    from fp.ingest import matches as build
    return build.build_matches()


def test_features_pass_the_leakage_check(matches):
    frame = rolling.match_features(matches)  # raises LeakageError if any row leaks
    assert (frame["source_max_utc"] <= frame["lock_utc"]).all()


def test_a_later_thrashing_does_not_change_earlier_features(matches):
    """Man City v Sunderland locked Sat 19 Sep 04:41 UTC. Pretend City lost 0-9 at
    Brighton that Saturday afternoon: City's features for Sunday must not change."""
    target = "EPL_2627_man_city_sunderland"
    before = rolling.match_features(matches).set_index("match_id").loc[target]
    fake = matches[matches["match_id"] == "EPL_2627_brighton_arsenal"].copy()
    fake["match_id"] = "EPL_2627_brighton_man_city_fake"
    fake["away_id"] = "man_city"
    fake[["home_goals", "home_corners", "home_shots"]] = [9, 20, 40]
    after = rolling.match_features(pd.concat([matches, fake], ignore_index=True))
    after = after.set_index("match_id").loc[target]
    for col in ("home_corners_for", "home_shots_for", "home_fouls", "elo_gap"):
        assert after[col] == pytest.approx(before[col])


def test_standings_count_three_points_for_a_win():
    games = pd.DataFrame({
        "home_id": ["a", "b"], "away_id": ["b", "a"], "home_goals": [2, 1],
        "away_goals": [0, 1],
        "result_available_utc": pd.to_datetime(["2026-08-01", "2026-08-08"], utc=True),
    })
    table = rolling.standings_at(games, pd.Timestamp("2026-08-10", tz="UTC"))
    assert table.loc["a", "points"] == 4 and table.loc["b", "points"] == 1
    assert table.loc["a", "position"] == 1
