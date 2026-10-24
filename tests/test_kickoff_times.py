"""Kickoff times come from football-data.org wherever it has set one.

The cases behind it: on 24 Oct 2026 openfootball listed every La Liga match from
matchday 10 on a placeholder Sunday with no time, so no La Liga match could lock,
while football-data.org had set the real times by 13 Oct. openfootball's EPL file
also gave the 7 Nov round default Saturday 15:00 times. Lang chose on 24 Oct 2026
that football-data.org's time and date win when the two sources differ.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
import pytest
import requests

from fp import leagues
from fp.config import MissingSecretError
from fp.ingest import football_data_api as api
from fp.ingest import http
from fp.ingest import matches as build
from fp.pipeline import daily

LALIGA = leagues.get("LaLiga")
DAY = "2026-10-24"


def api_match(home, away, utc, status):
    return {"id": 1, "utcDate": utc, "status": status,
            "homeTeam": {"name": home}, "awayTeam": {"name": away},
            "score": {"fullTime": {"home": None, "away": None},
                      "halfTime": {"home": None, "away": None}}, "lastUpdated": "x"}


@pytest.fixture
def raw(tmp_path, monkeypatch):
    """A raw folder with one openfootball La Liga file and one football-data.org file,
    in the real formats and with the real club spellings. Madrid is UTC+2 until
    25 Oct 2026, then UTC+1."""
    monkeypatch.setattr(http, "RAW_DIR", tmp_path)
    of = tmp_path / "openfootball" / DAY
    of.mkdir(parents=True)
    of.joinpath("es.1_2627.json").write_text(json.dumps({"name": "La Liga", "matches": [
        # Both give a time and they differ: football-data.org's time and date win.
        {"round": "Matchday 9", "date": "2026-10-18", "time": "21:00",
         "team1": "Real Madrid CF", "team2": "Sevilla FC"},
        {"round": "Matchday 10", "date": "2026-10-24", "time": "17:00",
         "team1": "Athletic Club", "team2": "Getafe CF"},
        # Both give the same time: nothing changes.
        {"round": "Matchday 10", "date": "2026-10-24", "time": "18:30",
         "team1": "Valencia CF", "team2": "Villarreal CF"},
        # openfootball has a time, football-data.org has not set one: openfootball's stays.
        {"round": "Matchday 11", "date": "2026-10-30", "time": "21:00",
         "team1": "Villarreal CF", "team2": "RCD Espanyol de Barcelona"},
        # Blank in openfootball, set in football-data.org: filled, date moves to Friday.
        {"round": "Matchday 10", "date": "2026-10-25",
         "team1": "Deportivo Alavés", "team2": "Málaga CF"},
        # Blank in both (SCHEDULED carries a 00:00 placeholder): stays blank.
        {"round": "Matchday 10", "date": "2026-10-25",
         "team1": "Sevilla FC", "team2": "CA Osasuna"},
        # Blank, and the match was postponed: its old time must not be used.
        {"round": "Matchday 10", "date": "2026-10-25",
         "team1": "Getafe CF", "team2": "Rayo Vallecano de Madrid"},
    ]}), encoding="utf-8")

    folder = tmp_path / api.SOURCE / DAY
    folder.mkdir(parents=True)
    folder.joinpath("PD_2026.json").write_text(json.dumps({"competition": {"code": "PD"},
                                                           "matches": [
        api_match("Real Madrid CF", "Sevilla FC", "2026-10-19T19:00:00Z", "FINISHED"),
        api_match("Athletic Club", "Getafe CF", "2026-10-25T13:00:00Z", "TIMED"),
        api_match("Valencia CF", "Villarreal CF", "2026-10-24T16:30:00Z", "TIMED"),
        api_match("Villarreal CF", "RCD Espanyol de Barcelona", "2026-10-30T00:00:00Z",
                  "SCHEDULED"),
        api_match("Deportivo Alavés", "Málaga CF", "2026-10-23T19:00:00Z", "TIMED"),
        api_match("Sevilla FC", "CA Osasuna", "2026-10-25T00:00:00Z", "SCHEDULED"),
        api_match("Getafe CF", "Rayo Vallecano de Madrid", "2026-10-24T14:00:00Z", "POSTPONED"),
    ]}), encoding="utf-8")
    return tmp_path


def calendar():
    fx = build.build_fixtures(group=(LALIGA,))
    return fx.set_index("match_id")


def utc(text):
    return pd.Timestamp(text, tz="UTC")


def test_blank_time_is_filled_when_football_data_org_has_set_it(raw):
    r = calendar().loc["LaLiga_2627_alaves_malaga"]
    assert r["time_confirmed"]
    assert r["kickoff_utc"] == utc("2026-10-23 19:00")
    assert r["date"] == "2026-10-23"  # Friday in Madrid, not openfootball's placeholder
    assert r["kickoff_source"] == api.SOURCE


def test_football_data_org_wins_when_the_sources_differ(raw, caplog):
    with caplog.at_level(logging.INFO, logger="fp.ingest.matches"):
        fx = calendar()
    moved = fx.loc["LaLiga_2627_real_madrid_sevilla"]
    assert moved["kickoff_utc"] == utc("2026-10-19 19:00")  # openfootball: 18 Oct 19:00
    assert moved["date"] == "2026-10-19"
    assert moved["kickoff_source"] == api.SOURCE
    later = fx.loc["LaLiga_2627_athletic_bilbao_getafe"]
    assert later["kickoff_utc"] == utc("2026-10-25 13:00")  # openfootball: 24 Oct 15:00
    assert later["date"] == "2026-10-25"
    assert "2 kickoff times from football-data.org where openfootball differs" in caplog.text


def test_openfootball_time_stays_when_football_data_org_has_none_or_agrees(raw):
    fx = calendar()
    unset = fx.loc["LaLiga_2627_villarreal_espanyol"]
    assert unset["kickoff_utc"] == utc("2026-10-30 20:00")  # 21:00 Madrid
    assert unset["kickoff_source"] == "openfootball"
    same = fx.loc["LaLiga_2627_valencia_villarreal"]
    assert same["kickoff_utc"] == utc("2026-10-24 16:30")
    assert same["kickoff_source"] == "openfootball"


def test_placeholder_and_postponed_times_are_not_used(raw):
    fx = calendar()
    for mid in ("LaLiga_2627_sevilla_osasuna", "LaLiga_2627_getafe_rayo_vallecano"):
        assert not fx.loc[mid, "time_confirmed"]
        assert pd.isna(fx.loc[mid, "kickoff_utc"])
        assert pd.isna(fx.loc[mid, "kickoff_source"])
        assert fx.loc[mid, "date"] == "2026-10-25"


def test_every_row_keeps_the_schema_rule(raw):
    fx = calendar()
    assert (fx["time_confirmed"] == fx["kickoff_utc"].notna()).all()


def test_filled_match_can_lock_in_its_window(raw):
    """The first bug: with the fill, the 22 Oct run locks Friday's match."""
    fx = calendar().reset_index()
    cands = daily.candidates(fx, utc("2026-10-22 05:00"), pd.DataFrame())
    assert list(cands["match_id"]) == ["LaLiga_2627_alaves_malaga"]
    assert not cands["late_lock"].iloc[0]


def test_no_early_lock_on_an_openfootball_placeholder(raw):
    """The second bug: openfootball's 24 Oct 15:00 would put Athletic v Getafe 47 hours
    ahead at this run, so it would lock 69 hours before its real kickoff."""
    now = utc("2026-10-22 16:00")
    cands = daily.candidates(calendar().reset_index(), now, pd.DataFrame())
    assert "LaLiga_2627_athletic_bilbao_getafe" not in set(cands["match_id"])
    for path in (raw / api.SOURCE).rglob("*.json"):
        path.unlink()
    old = daily.candidates(calendar().reset_index(), now, pd.DataFrame())
    assert "LaLiga_2627_athletic_bilbao_getafe" in set(old["match_id"])


def test_without_a_cached_file_the_calendar_is_openfootball_only(raw):
    for path in (raw / api.SOURCE).rglob("*.json"):
        path.unlink()
    fx = calendar()
    assert fx["time_confirmed"].sum() == 4
    assert fx["kickoff_source"].dropna().eq("openfootball").all()
    assert fx.loc["LaLiga_2627_athletic_bilbao_getafe", "kickoff_utc"] == utc(
        "2026-10-24 15:00")


def test_unknown_club_is_skipped(tmp_path, caplog):
    path = tmp_path / "PD.json"
    path.write_text(json.dumps({"competition": {"code": "PD"}, "matches": [
        api_match("Nowhere FC", "Málaga CF", "2026-10-23T19:00:00Z", "TIMED"),
        api_match("Deportivo Alavés", "Málaga CF", "2026-10-23T19:00:00Z", "TIMED")]}),
        encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="fp.ingest.football_data_api"):
        times = api.set_kickoffs(path)
    assert list(times["home_id"]) == ["alaves"]
    assert "Nowhere FC" in caplog.text


@pytest.mark.parametrize(("error", "calls"), [
    (MissingSecretError("no token"), 1),         # no token: stop quietly
    (requests.ConnectionError("down"), 1),       # unreachable: the rest would time out too
    (requests.HTTPError("404"), 2),              # one competition failed: try the next
])
def test_download_never_stops_the_run(monkeypatch, error, calls):
    seen = []

    def fail(code, season=2026, refresh=True):
        seen.append(code)
        raise error
    monkeypatch.setattr(api, "download_matches", fail)
    api.download_all(leagues.LIVE)  # must not raise
    assert len(seen) == calls
