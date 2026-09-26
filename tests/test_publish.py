"""Dashboard exports and the static page (Phase 6)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fp.models.bayes_dc import Posterior
from fp.publish import drivers, export, season, site

NOW = pd.Timestamp("2026-09-26 04:41", tz="UTC")


def posterior(att=(0.4, 0.0, -0.4, 0.0), s=400, seed=0):
    rng = np.random.default_rng(seed)
    n = len(att)
    return Posterior(teams=["a", "b", "c", "d"][:n], mu=np.full(s, 0.1), home=np.full(s, 0.25),
                     rho=np.full(s, -0.05),
                     att=np.array(att) + rng.normal(0, 0.02, (s, n)),
                     def_=-np.array(att) * 0.5 + rng.normal(0, 0.02, (s, n)))


def test_season_simulation_favours_the_strongest_club():
    post = posterior()
    played = pd.DataFrame({"home_id": ["a"], "away_id": ["b"], "home_goals": [2],
                           "away_goals": [0]})
    remaining = pd.DataFrame([(h, a) for h in "abcd" for a in "abcd" if h != a],
                             columns=["home_id", "away_id"])
    out = season.simulate(post, played, remaining, n_sims=2000).set_index("team_id")
    assert out.loc["a", "points"] == 3 and out.loc["a", "played"] == 1
    assert out["p_title"].sum() == np.float64(1.0) or abs(out["p_title"].sum() - 1) < 1e-9
    assert out["p_title"].idxmax() == "a"
    assert out["p_relegation"].idxmax() == "c"
    assert abs(out["p_relegation"].sum() - season.RELEGATED) < 1e-9


def test_drivers_are_plain_sentences_about_both_clubs():
    lines = drivers.drivers(posterior(), "a", "c", {"a": "Alpha", "c": "Gamma"}, "EPL",
                            elo_gap=250.0,
                            news={"home": {"status": "answered", "starters_out": 3,
                                           "threat_out": True}})
    assert len(lines) == 5
    assert lines[0].startswith("Team news: Alpha without 3+ regular starters")
    every = drivers.drivers(posterior(), "a", "c", {"a": "Alpha", "c": "Gamma"}, "EPL",
                            elo_gap=250.0, top=10)
    assert any("Elo rates Alpha 250 points higher" in s for s in every)
    assert all(chr(0x2013) not in s and chr(0x2014) not in s for s in every)


def test_window_includes_the_next_round_after_a_break():
    fixtures = pd.DataFrame({
        "match_id": ["soon", "break_1", "break_2", "later"],
        "league": ["EPL"] * 4,
        "round": ["R7", "R8", "R8", "R9"],
        "kickoff_utc": [NOW + pd.Timedelta(days=d) for d in (-1, 13, 14, 20)],
    })
    assert export.window(fixtures, NOW) == {"break_1", "break_2"}


def fixture_rows():
    return pd.DataFrame([{
        "match_id": "EPL_2627_arsenal_leeds", "league": "EPL", "home_name": "Arsenal",
        "away_name": "Leeds", "kickoff_utc": pd.Timestamp("2026-10-10 11:30", tz="UTC"),
        "locked": True, "p_home": 0.62, "p_draw": 0.24, "p_away": 0.14, "p_over_2_5": 0.44,
        "p_btts": 0.45, "exp_goals_home": 1.75, "exp_goals_away": 0.7,
        "exp_corners_home": 5.8, "exp_corners_away": 4.2, "exp_yellows": 3.4,
        "tiers": json.dumps({"1x2": "High"}),
        "news_adjustments": json.dumps([{"scale_home_goals": 1.0, "scale_away_goals": 0.88}]),
        "unanswered_questions": "[]"}])


def test_static_page_is_small_and_clean(tmp_path):
    page = site.write(fixture_rows(), NOW, tmp_path)
    text = page.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 100_000
    assert "13:30" in text          # Juba time, UTC+2
    assert "Leeds goals −12%" in text
    assert ">High<" in text and "Locked" in text
    assert chr(0x2013) not in text and chr(0x2014) not in text
    assert (tmp_path / "fixtures.csv").read_text().startswith("kickoff_juba,league")


def test_ranks_count_only_this_seasons_clubs():
    lines = drivers.drivers(posterior(att=(0.4, 0.2, -0.4, 0.0)), "b", "d",
                            {"b": "Beta", "d": "Delta"}, "EPL",
                            current={"b", "c", "d"}, top=10)
    assert any("Beta's attack ranks 1st of 3" in s for s in lines)  # "a" is not in the league
