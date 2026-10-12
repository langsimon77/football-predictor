"""League table and the leagues on trial (Serie A and Ligue 1, chosen by Lang 12 Oct 2026)."""

from __future__ import annotations

import pandas as pd
import pytest

from fp import leagues
from fp.ingest import football_data_csv as fd
from fp.ingest import matches as build
from fp.ingest.http import cached_copies
from fp.validate import schemas


def test_live_leagues_are_unchanged():
    assert [lg.code for lg in leagues.LIVE] == ["EPL", "LaLiga"]
    assert fd.DIVISIONS == ("E0", "SP1", "E1", "SP2")


def test_trial_leagues():
    assert [lg.code for lg in leagues.TRIAL] == ["SerieA", "Ligue1"]
    assert fd.divisions(leagues.TRIAL) == ("I1", "F1", "I2", "F2")


def test_every_league_code_is_unique():
    for field in ("code", "division", "second", "openfootball", "fdorg"):
        values = [getattr(lg, field) for lg in leagues.ALL]
        assert len(values) == len(set(values)), field


def test_season_lengths():
    assert leagues.season_length("EPL", 2026) == 380
    assert leagues.season_length("Ligue1", 2022) == 380
    assert leagues.season_length("Ligue1", 2023) == 306  # 18 clubs from 2023/24
    assert leagues.season_length("Ligue1", 2019) == 279  # stopped by COVID-19


def test_left_out_matches_are_well_formed():
    table = pd.read_csv(build.LEFT_OUT_CSV)
    assert table["match_id"].is_unique
    assert set(table["kind"]) <= {"stopped", "ruling"}
    assert table["source"].str.startswith("https://").all()
    assert {m.split("_")[0] for m in table["match_id"]} <= set(leagues.BY_CODE)


@pytest.fixture(scope="module")
def trial_matches() -> pd.DataFrame:
    if not cached_copies(fd.SOURCE, "I1_2627.csv"):
        pytest.skip("trial data not downloaded; run `python -m fp.pipeline.data --trial`")
    return build.build_matches(leagues.TRIAL)


def test_trial_matches_pass_the_checks(trial_matches):
    schemas.matches_schema(leagues.TRIAL).validate(trial_matches, lazy=True)


def test_trial_tables_leave_out_matches_with_no_football_result(trial_matches):
    assert not trial_matches["match_id"].isin(build.left_out()).any()
    sizes = trial_matches.groupby(["league", "season"]).size()
    assert sizes[("Ligue1", 2016)] == 379  # Bastia v Lyon
    assert sizes[("Ligue1", 2025)] == 305  # Nantes v Toulouse
    assert sizes[("SerieA", 2016)] == 379  # Sassuolo v Pescara


def test_live_checks_reject_trial_rows(trial_matches):
    import pandera.errors

    with pytest.raises(pandera.errors.SchemaErrors):
        schemas.matches_schema().validate(trial_matches.head(50), lazy=True)
