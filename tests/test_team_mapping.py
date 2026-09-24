"""Team mapping tests (Phase 0 acceptance check).

Data tests need the raw downloads. Run `make data` first.
They skip, not fail, when files are absent. CI downloads everything before testing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fp import teams
from fp.ingest import football_data_csv as fd
from fp.ingest.http import cached_copies

SOURCE = "football_data_co_uk"
TOP_TIER = {"E0": "E1", "SP1": "SP2"}  # top division -> second division


def load(division: str, start_year: int) -> pd.DataFrame:
    copies = cached_copies(fd.SOURCE, f"{division}_{fd.season_code(start_year)}.csv")
    if not copies:
        pytest.skip("raw CSVs not downloaded; run `make audit`")
    return fd.read_csv(copies[-1])


def names_in(frame: pd.DataFrame) -> set[str]:
    return set(frame["HomeTeam"]) | set(frame["AwayTeam"])


def test_team_ids_are_unique():
    assert teams.teams()["team_id"].is_unique


def test_every_alias_points_to_a_known_team():
    known = set(teams.teams()["team_id"])
    assert set(teams.aliases()["team_id"]) <= known


def test_no_alias_maps_to_two_teams_within_a_source():
    dupes = teams.aliases().duplicated(subset=["source", "alias"], keep=False)
    assert not dupes.any(), teams.aliases()[dupes]


def test_every_team_has_a_short_name_that_fits_on_a_phone():
    assert (teams.teams()["short_name"].str.len() <= 12).all()


def test_unknown_name_raises():
    with pytest.raises(teams.UnknownTeamError):
        teams.to_team_id("Real Madrid Castilla", SOURCE)


@pytest.mark.parametrize("division", sorted(TOP_TIER))
@pytest.mark.parametrize("start_year", fd.seasons())
def test_every_top_tier_name_maps(division, start_year):
    frame = load(division, start_year)
    ids = {teams.to_team_id(n, SOURCE) for n in names_in(frame)}
    assert len(ids) == 20, f"{division} {start_year}: expected 20 teams, got {len(ids)}"


@pytest.mark.parametrize("division", sorted(TOP_TIER))
@pytest.mark.parametrize("start_year", fd.seasons()[1:])
def test_promoted_teams_keep_their_id_across_divisions(division, start_year):
    """A newly promoted team must appear under the same alias in last season's second tier.

    This proves promoted-team priors will join the right second-tier history.
    """
    this_season = names_in(load(division, start_year))
    last_season = names_in(load(division, start_year - 1))
    second_tier_last = names_in(load(TOP_TIER[division], start_year - 1))
    promoted = this_season - last_season
    assert len(promoted) == 3, f"{division} {start_year}: {sorted(promoted)}"
    assert promoted <= second_tier_last, sorted(promoted - second_tier_last)


def test_fixtures_file_names_map():
    copies = cached_copies(fd.SOURCE, "fixtures.csv")
    if not copies:
        pytest.skip("fixtures.csv not downloaded; run `make audit`")
    frame = fd.read_csv(copies[-1])
    frame = frame[frame["Div"].isin(list(TOP_TIER))]
    for name in names_in(frame):
        teams.to_team_id(name, SOURCE)


OPENFOOTBALL = {"E0": "en.1", "SP1": "es.1"}


def load_openfootball(division: str, start_year: int) -> pd.DataFrame:
    from fp.ingest import openfootball

    code = OPENFOOTBALL[division]
    copies = cached_copies(openfootball.SOURCE, f"{code}_{fd.season_code(start_year)}.json")
    if not copies:
        pytest.skip("openfootball files not downloaded; run `make audit`")
    return openfootball.read(copies[-1], code)


@pytest.mark.parametrize("division", sorted(TOP_TIER))
@pytest.mark.parametrize("start_year", fd.seasons())
def test_both_sources_agree_on_the_twenty_clubs(division, start_year):
    """openfootball and football-data.co.uk must name the same 20 clubs every season."""
    of = load_openfootball(division, start_year)
    of_ids = {teams.to_team_id(n, "openfootball") for n in set(of["team1"]) | set(of["team2"])}
    fd_ids = {teams.to_team_id(n, SOURCE) for n in names_in(load(division, start_year))}
    assert of_ids == fd_ids, {"only_openfootball": of_ids - fd_ids, "only_fd": fd_ids - of_ids}


@pytest.mark.parametrize("division", sorted(TOP_TIER))
def test_current_season_results_agree_across_sources(division):
    """Every 2026/27 match played so far has the same date and score in both sources."""
    year = fd.CURRENT_SEASON
    of = load_openfootball(division, year).dropna(subset=["home_goals"])
    of = pd.DataFrame({
        "home": of["team1"].map(lambda n: teams.to_team_id(n, "openfootball")),
        "away": of["team2"].map(lambda n: teams.to_team_id(n, "openfootball")),
        "date": pd.to_datetime(of["date"]).dt.date,
        "score": list(zip(of["home_goals"], of["away_goals"], strict=True)),
    })
    fdc = load(division, year)
    fdc = pd.DataFrame({
        "home": teams.map_series(fdc["HomeTeam"], SOURCE),
        "away": teams.map_series(fdc["AwayTeam"], SOURCE),
        "date": pd.to_datetime(fdc["Date"], dayfirst=True).dt.date,
        "score": list(zip(fdc["FTHG"].astype(int), fdc["FTAG"].astype(int), strict=True)),
    })
    merged = fdc.merge(
        of, on=["home", "away"], how="outer", suffixes=("_fd", "_of"), indicator=True
    )
    assert (merged["_merge"] == "both").all(), merged[merged["_merge"] != "both"]
    assert (merged["date_fd"] == merged["date_of"]).all()
    assert (merged["score_fd"] == merged["score_of"]).all()


@pytest.mark.parametrize("code", ["PL", "PD"])
def test_football_data_org_names_map(code):
    """Runs where the API is reachable (GitHub's runner). This Mac's network times out."""
    from fp.ingest import football_data_api

    copies = cached_copies(football_data_api.SOURCE, f"{code}_{fd.CURRENT_SEASON}.json")
    if not copies:
        pytest.skip("football-data.org files not downloaded here")
    frame = football_data_api.read_matches(copies[-1])
    names = set(frame["home_name"]) | set(frame["away_name"])
    ids = {teams.to_team_id(n, football_data_api.SOURCE) for n in names}
    assert len(ids) == 20
