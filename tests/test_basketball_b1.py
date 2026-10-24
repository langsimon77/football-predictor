"""Basketball phase B1: data parsing, Elo, the points model, scores, and no peeking."""
from __future__ import annotations

import importlib
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from fp import ROOT

sys.path.insert(0, str(ROOT / "basketball"))
data = importlib.import_module("data")
models = importlib.import_module("models")

DASH = chr(0x2013)  # Wikipedia's dash; the repository bans the character itself


# ---------------------------------------------------------------- data parsing


@pytest.mark.parametrize(("value", "target"), [
    (f"[[2026{DASH}27 Melbourne United season|Melbourne United]]", "Melbourne United"),
    ("{{nowrap|[[Fundación CB Granada|Coviran Granada]]}}", "Fundación CB Granada"),
    ("'''[[Hapoel Tel Aviv B.C.|Hapoel IBI Tel Aviv]] {{#invoke:bka|icon|ISR}}'''",
     "Hapoel Tel Aviv B.C."),
    ("[[Perth Wildcats]]", "Perth Wildcats"),
    ("Perth Wildcats", None),
])
def test_link_target(value, target):
    assert data.link_target(value) == target


def test_club_id_is_plain_ascii():
    assert data.club_id("BC Žalgiris") == "bc_zalgiris"
    assert data.club_id("FC Bayern Munich (basketball)") == "fc_bayern_munich_basketball"


def test_boxes_keep_round_sections_and_read_quarters():
    text = f"""== Round 1 ==
{{{{basketballbox collapsible
 | date = 3 November 2023 | time = 19:30
 | team1 = '''[[2023{DASH}24 New Zealand Breakers season|New Zealand Breakers]]'''
 | scoreA = '''91''' | scoreB = 81
 | teamB = [[2023{DASH}24 Cairns Taipans season|Cairns Taipans]]
 | Q1 = 20{DASH}20 | Q2 = 25{DASH}20 | Q3 = 20{DASH}21 | Q4 = 16{DASH}20 | OT = 10{DASH}0
}}}}
== Grand Final ==
{{{{basketballbox collapsible
 | date = 1 March 2024 | teamA = [[Sydney Kings]] | scoreA = 90
 | teamB = [[Perth Wildcats]] | scoreB = 80
}}}}"""
    regular, final = data.parse_boxes(text, "NBL", 2023)
    assert regular["regular_season"] and not final["regular_season"]
    assert regular["home_link"] == "New Zealand Breakers"  # from team1, the editors' slip
    assert (regular["home_pts"], regular["away_pts"]) == (91, 81)
    assert (regular["home_reg"], regular["away_reg"]) == (81, 81)  # level after 40 minutes
    assert regular["overtime"] and regular["date"] == "2023-11-03"


def test_results_grid_codes_and_scores():
    text = f"""| team1=JOV  | name_JOV=[[Joventut Badalona|Asisa Joventut]]
| team2=BAR  | name_BAR={{{{nowrap|[[FC Barcelona Bàsquet|Barça]]}}}}
| match_JOV_BAR=[[Catalan basketball derby|84{DASH}72]]
| match_BAR_JOV='''90'''{DASH}80
| match_JOV_JOV="""
    names, cells = data.parse_grid(text)
    assert names == {"JOV": "Joventut Badalona", "BAR": "FC Barcelona Bàsquet"}
    assert cells == {("JOV", "BAR"): (84, 72), ("BAR", "JOV"): (90, 80)}


# ---------------------------------------------------------------- models


def games(rows):
    """rows: (day offset, season, home, away, home points, away points)."""
    start = date(2020, 10, 1)
    g = pd.DataFrame([{"date": start + timedelta(days=d), "season": s, "home_id": h,
                       "away_id": a, "home_pts": float(hp), "away_pts": float(ap)}
                      for d, s, h, a, hp, ap in rows])
    return g.sort_values("date", kind="stable").reset_index(drop=True)


def test_elo_update_and_same_day_rule():
    g = games([(0, 1, "a", "b", 90, 80), (0, 1, "a", "c", 70, 75), (1, 1, "a", "b", 80, 80 + 1)])
    out = models.elo_run(g, models.EloSettings(k=20, home=0, carry=1.0, mov=False))
    assert out["elo_diff"].iloc[0] == 0 and out["elo_diff"].iloc[1] == 0  # both from day-0 ratings
    # Day 0: a beat b (+10) and lost to c (-10), so a is back to 1500; b 1490.
    assert out["elo_diff"].iloc[2] == pytest.approx(10.0)


def test_elo_season_carry_over_pulls_to_1500():
    g = games([(0, 1, "a", "b", 90, 80), (300, 2, "a", "b", 90, 80)])
    out = models.elo_run(g, models.EloSettings(k=20, home=0, carry=0.5, mov=False))
    assert out["elo_diff"].iloc[1] == pytest.approx(10.0)  # 20 apart, halved by carry-over


def synthetic(seed=1, noise=1.0, seasons=3):
    rng = np.random.default_rng(seed)
    clubs = [f"c{i}" for i in range(8)]
    att = dict(zip(clubs, rng.normal(0, 5, 8), strict=True))
    dfn = dict(zip(clubs, rng.normal(0, 5, 8), strict=True))
    rows = []
    for s in range(seasons):
        for r in range(28):
            perm = rng.permutation(clubs)
            for h, a in zip(perm[::2], perm[1::2], strict=True):
                rows.append((200 * s + 3 * r, s, h, a,
                             80 + 3 + att[h] - dfn[a] + rng.normal(0, noise),
                             80 + att[a] - dfn[h] + rng.normal(0, noise)))
    return games(rows), att, dfn


def test_points_model_recovers_known_ratings():
    g, att, dfn = synthetic(noise=1.0)
    pred = models.points_run(g, models.PointsSettings(half_life=100_000, penalty=0.01))
    last = g.index[-4:]
    true_home = [83 + att[h] - dfn[a] for h, a in zip(g.loc[last, "home_id"],
                                                       g.loc[last, "away_id"], strict=True)]
    assert np.allclose(pred.loc[last, "m_home"], true_home, atol=0.5)


@pytest.mark.parametrize("run", ["elo", "points"])
def test_walk_forward_never_peeks(run):
    g, _, _ = synthetic(seed=2, noise=8.0, seasons=2)
    changed = g.copy()
    day = g["date"].iloc[len(g) // 2]
    on_day = changed["date"] == day
    changed.loc[on_day, "home_pts"] += 40  # rewrite that day's results
    fit = (lambda x: models.elo_run(x, models.EloSettings(20, 100, 0.75, True)).to_numpy()) \
        if run == "elo" else \
        (lambda x: models.points_run(x, models.PointsSettings(120, 3)).to_numpy())
    before, after = fit(g), fit(changed)
    upto = (g["date"] <= day).to_numpy()
    assert np.allclose(before[upto], after[upto], equal_nan=True)  # that day and earlier: same
    assert not np.allclose(before[~upto], after[~upto])           # later days: changed


# ---------------------------------------------------------------- scores


def test_crps_normal_known_values():
    assert models.crps_normal(np.array([0.0]), np.array([0.0]), 1.0)[0] == pytest.approx(
        2 / np.sqrt(2 * np.pi) - 1 / np.sqrt(np.pi))
    far = models.crps_normal(np.array([10.0]), np.array([0.0]), 1.0)[0]
    assert far == pytest.approx(10 - 1 / np.sqrt(np.pi), abs=1e-6)  # far away: about the distance


def test_calibration_slope_near_one_for_honest_forecasts():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.2, 0.8, 20_000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    assert models.calibration_slope(p, y) == pytest.approx(1.0, abs=0.08)


def test_bootstrap_is_repeatable_and_resamples_days():
    diff = np.array([1.0, 1.0, -1.0, 3.0])
    day = np.array(["d1", "d1", "d2", "d3"])
    a, b = models.bootstrap_mean(diff, day), models.bootstrap_mean(diff, day)
    assert a == b and a[0] == pytest.approx(1.0)
    assert a[1] <= a[0] <= a[2]
    flat = models.bootstrap_mean(np.full(4, 0.5), day)
    assert flat[1] == pytest.approx(0.5) and flat[2] == pytest.approx(0.5)


def test_naive_total_uses_recent_games_or_falls_back():
    rows = [(d, 1, "a", "b", 80, 80) for d in range(0, 30)]      # 30 games, total 160
    rows += [(200, 2, "a", "b", 100, 100)]                       # new season, after a gap
    g = games(rows)
    mean = models.naive_total_mean(g, days=60, min_games=20, fallback=100)
    assert np.isnan(mean[0])                                     # nothing before day 0
    assert mean[-1] == pytest.approx(160.0)                      # gap: last 100 games instead
