from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fp.models import elo


def league(rows, season=2025):
    frame = pd.DataFrame(rows, columns=["home_id", "away_id", "home_goals", "away_goals", "day"])
    frame["season"] = season
    frame["result_available_utc"] = pd.to_datetime(frame["day"], utc=True)
    return frame


def test_win_moves_ratings_by_equal_and_opposite_amounts():
    m = league([("a", "b", 1, 0, "2025-08-20")])
    t = elo.EloTracker(m, {2025: {"a", "b"}})
    t.advance_to(pd.Timestamp("2025-08-21", tz="UTC"))
    assert t.ratings["a"] > 1500 > t.ratings["b"]
    assert t.ratings["a"] - 1500 == pytest.approx(1500 - t.ratings["b"])


def test_bigger_margin_moves_ratings_more():
    small = elo.EloTracker(league([("a", "b", 1, 0, "2025-08-20")]), {2025: {"a", "b"}})
    big = elo.EloTracker(league([("a", "b", 4, 0, "2025-08-20")]), {2025: {"a", "b"}})
    for t in (small, big):
        t.advance_to(pd.Timestamp("2025-08-21", tz="UTC"))
    assert big.ratings["a"] > small.ratings["a"]


def test_tracker_never_uses_results_after_as_of():
    m = league([("a", "b", 3, 0, "2025-08-20"), ("b", "a", 5, 0, "2025-08-27")])
    t = elo.EloTracker(m, {2025: {"a", "b"}})
    t.advance_to(pd.Timestamp("2025-08-25", tz="UTC"))
    assert t.ratings["a"] > 1500  # the 27 Aug thrashing is still invisible
    assert len(t.history) == 1


def test_promoted_team_takes_the_relegated_average():
    m = pd.concat([
        league([("a", "b", 1, 0, "2025-08-20"), ("c", "b", 2, 0, "2025-08-27")], 2025),
        league([("a", "p", 1, 1, "2026-08-20")], 2026),
    ])
    t = elo.EloTracker(m, {2025: {"a", "b", "c"}, 2026: {"a", "c", "p"}})
    t.advance_to(pd.Timestamp("2026-01-01", tz="UTC"))
    b_final = t.ratings["b"]
    t.ensure_season(2026)
    assert t.ratings["p"] == pytest.approx(1500 + 0.75 * (b_final - 1500))


def test_curve_gives_valid_probabilities_and_favours_the_stronger_side():
    rng = np.random.default_rng(1)
    gaps = rng.normal(60, 120, 3000)
    p_home = 1 / (1 + np.exp(-(gaps / 200)))
    outcomes = np.where(rng.random(3000) < p_home * 0.75, 2,
                        np.where(rng.random(3000) < 0.5, 1, 0))
    curve = elo.fit_curve(gaps, outcomes)
    probs = curve.probs(np.array([-200.0, 0.0, 200.0]))
    assert np.allclose(probs.sum(axis=1), 1)
    assert (probs >= 0).all()
    assert probs[2, 0] > probs[1, 0] > probs[0, 0]  # home win rises with the gap
