"""Fast results (approved by Lang on 12 Oct 2026)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fp.ingest import football_data_api as api
from fp.ingest import results_feed as rf
from fp.models import bayes_dc
from fp.pipeline import daily

NOW = pd.Timestamp("2026-10-12 09:00", tz="UTC")
KO = pd.Timestamp("2026-10-10 11:30", tz="UTC")


def fixtures():
    return pd.DataFrame([
        {"match_id": "EPL_2627_arsenal_leeds", "league": "EPL", "season": 2026,
         "round": "Matchday 6", "date": "2026-10-10", "kickoff_utc": KO, "time_confirmed": True,
         "home_id": "arsenal", "away_id": "leeds", "home_goals": np.nan, "away_goals": np.nan,
         "status": "scheduled"},
        {"match_id": "EPL_2627_coventry_newcastle", "league": "EPL", "season": 2026,
         "round": "Matchday 6", "date": "2026-10-12", "kickoff_utc": KO + pd.Timedelta(days=2),
         "time_confirmed": True, "home_id": "coventry", "away_id": "newcastle",
         "home_goals": np.nan, "away_goals": np.nan, "status": "scheduled"},
        {"match_id": "LaLiga_2627_levante_sevilla", "league": "LaLiga", "season": 2026,
         "round": "Matchday 8", "date": "2026-10-09", "kickoff_utc": KO - pd.Timedelta(days=1),
         "time_confirmed": True, "home_id": "levante", "away_id": "sevilla",
         "home_goals": 1.0, "away_goals": 1.0, "status": "played"},
    ])


def api_file(tmp_path, code, matches):
    path = tmp_path / f"{code}.json"
    path.write_text(json.dumps({"competition": {"code": code}, "matches": matches}))
    return path


def match(i, home, away, status, ft):
    return {"id": i, "utcDate": "2026-10-10T11:30:00Z", "status": status,
            "homeTeam": {"name": home}, "awayTeam": {"name": away},
            "score": {"fullTime": {"home": ft[0], "away": ft[1]},
                      "halfTime": {"home": None, "away": None}}, "lastUpdated": "x"}


def test_read_matches_keeps_scores(tmp_path):
    p = api_file(tmp_path, "PL", [match(1, "Arsenal FC", "Leeds United FC", "FINISHED", (2, 1)),
                                  match(2, "Coventry City FC", "Newcastle United FC", "TIMED",
                                        (None, None))])
    f = api.read_matches(p)
    assert f.loc[0, "home_goals"] == 2 and f.loc[0, "away_goals"] == 1
    assert np.isnan(f.loc[1, "home_goals"])


def test_api_scores_map_finished_matches_only(tmp_path, monkeypatch):
    files = {"PL": api_file(tmp_path, "PL", [
        match(1, "Arsenal FC", "Leeds United FC", "FINISHED", (2, 1)),
        match(2, "Coventry City FC", "Newcastle United FC", "TIMED", (None, None))]),
        "PD": api_file(tmp_path, "PD", [])}
    monkeypatch.setattr(api, "download_matches", lambda code, season, refresh=True: files[code])
    s = rf.api_scores(fixtures())
    assert list(s["match_id"]) == ["EPL_2627_arsenal_leeds"]
    assert (s["home_goals"].iloc[0], s["away_goals"].iloc[0]) == (2, 1)


def test_manual_entries_ignore_blank_rows(tmp_path):
    p = tmp_path / "manual.csv"
    p.write_text("match_id,home_goals,away_goals,home_corners,away_corners,home_yellows,"
                 "away_yellows,home_reds,away_reds,entered_utc,note\n"
                 "EPL_2627_arsenal_leeds,3,0,7,2,1,3,0,0,2026-10-10T14:00Z,\n"
                 "EPL_2627_coventry_newcastle,,,,,,,,,,not played yet\n")
    m = rf.manual_scores(p)
    assert list(m["match_id"]) == ["EPL_2627_arsenal_leeds"]
    assert m["home_corners"].iloc[0] == 7 and m["source"].iloc[0] == "manual"


def test_order_of_trust_and_the_full_row_wins():
    manual = pd.DataFrame([{"match_id": "EPL_2627_arsenal_leeds", "home_goals": 3,
                            "away_goals": 0, "home_corners": 7, "source": "manual"}])
    fast = pd.DataFrame([{"match_id": "EPL_2627_arsenal_leeds", "home_goals": 2,
                          "away_goals": 1, "source": "football_data_org"}])
    of = rf.openfootball_scores(fixtures())
    full = pd.DataFrame({"match_id": ["LaLiga_2627_levante_sevilla"], "home_goals": [1],
                         "away_goals": [1], "home_sot": [4], "league": ["LaLiga"],
                         "season": [2026], "home_id": ["levante"], "away_id": ["sevilla"],
                         "kickoff_utc": [KO], "result_available_utc": [KO]})
    rows = rf.score_only_rows(full, fixtures(), [manual, fast, of])
    got = rows.set_index("match_id")
    assert list(got.index) == ["EPL_2627_arsenal_leeds"]       # Levante v Sevilla is full
    assert got.loc["EPL_2627_arsenal_leeds", "home_goals"] == 3  # Lang's entry beats the API
    assert got.loc["EPL_2627_arsenal_leeds", "result_source"] == "manual"
    assert got.loc["EPL_2627_arsenal_leeds", "result_available_utc"] == KO + pd.Timedelta(hours=3)
    assert np.isnan(got.loc["EPL_2627_arsenal_leeds", "home_sot"])


def test_cross_check_reports_a_difference():
    full = pd.DataFrame({"match_id": ["m1"], "home_goals": [2], "away_goals": [1],
                         "home_corners": [5]})
    mine = pd.DataFrame({"match_id": ["m1"], "home_goals": [2], "away_goals": [1],
                         "home_corners": [6], "source": ["manual"]})
    problems = rf.cross_check(full, [mine])
    assert problems == ["m1: home_corners is 5 in football-data.co.uk but 6 in manual"]


def test_record_results_uses_fast_rows_until_the_full_row(tmp_path):
    locked = pd.DataFrame({"match_id": ["EPL_2627_arsenal_leeds"]})
    empty = pd.DataFrame(columns=["match_id", "home_goals", "away_goals", "home_corners",
                                  "away_corners", "home_yellows", "away_yellows", "home_reds",
                                  "away_reds", "result_available_utc"])
    fast = pd.DataFrame([{"match_id": "EPL_2627_arsenal_leeds", "home_goals": 2.0,
                          "away_goals": 1.0, "result_source": "football_data_org",
                          "result_available_utc": KO + pd.Timedelta(hours=3)}])
    res = daily.record_results(empty, fixtures(), locked, NOW, tmp_path / "r.parquet", fast)
    assert res["source"].tolist() == ["football_data_org"]
    assert str(res["home_goals"].dtype) == "Int64" and res["home_goals"].iloc[0] == 2
    early = daily.record_results(empty, fixtures(), locked, KO + pd.Timedelta(hours=1),
                                 tmp_path / "r2.parquet", fast)
    assert early.empty  # not known until three hours after kickoff


def tiny_league(missing_sot_last: bool):
    rng = np.random.default_rng(3)
    teams = ["a", "b", "c", "d"]
    rows = []
    for k in range(40):
        h, a = rng.choice(teams, 2, replace=False)
        rows.append({"home_id": h, "away_id": a, "home_goals": int(rng.poisson(1.4)),
                     "away_goals": int(rng.poisson(1.1)), "home_sot": int(rng.poisson(4)),
                     "away_sot": int(rng.poisson(3)),
                     "kickoff_utc": NOW - pd.Timedelta(days=100 - k)})
    frame = pd.DataFrame(rows)
    frame[["home_sot", "away_sot"]] = frame[["home_sot", "away_sot"]].astype("Int64")
    if missing_sot_last:
        frame.loc[len(frame) - 1, ["home_sot", "away_sot"]] = pd.NA
    return frame, teams


def shots_potential(frame, teams):
    p = bayes_dc.BayesParams(use_sot=True)
    d = bayes_dc._arrays(frame, teams, NOW, p)
    n = len(teams)
    model = bayes_dc.build_model(d, n, np.zeros(n), np.ones(n), np.zeros(n), np.ones(n),
                                 np.zeros(n, dtype=bool), True)
    pot = next(v for v in model.potentials if v.name == "shots_on_target")
    # Evaluate at fixed parameter values, not at random draws of the parameters.
    pot = model.replace_rvs_by_values([pot])[0]
    fn = model.compile_fn(pot, inputs=model.value_vars, on_unused_input="ignore")
    return float(fn(model.initial_point(random_seed=1))), d  # same point for every data set


def test_missing_shots_add_nothing_to_the_shots_part():
    full, teams = tiny_league(False)
    gap, teams = tiny_league(True)
    with_row, d = shots_potential(gap, teams)
    without_row, _ = shots_potential(gap.iloc[:-1], teams)
    assert d["ms"][-1] == 0 and d["xs"][-1] == 0 and d["ms"][:-1].all()
    assert np.isfinite(with_row)
    assert abs(with_row - without_row) < 1e-9
    # The complete data set keeps every shots term.
    _, d_full = shots_potential(full, teams)
    assert d_full["ms"].all()
