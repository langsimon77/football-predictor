import json

import pandas as pd
import pytest

from fp.tips import picks as tp


def _match(mid, ph, pd_, pa, p25, tier_1x2, tier_25, kick="2026-11-22 15:00"):
    return {"match_id": mid, "league": "EPL", "kickoff_utc": kick, "home_id": "a",
            "away_id": "b", "p_home": ph, "p_draw": pd_, "p_away": pa, "p_over_2_5": p25,
            "tiers": json.dumps({"rule": "tiers_v1", "1x2": tier_1x2,
                                 "over_2_5": tier_25})}


@pytest.fixture
def cand():
    rows = [_match("m1", 0.70, 0.18, 0.12, 0.40, "High", "Low"),
            _match("m2", 0.20, 0.25, 0.55, 0.66, "Medium", "High"),
            _match("m3", 0.40, 0.30, 0.30, 0.52, "Low", "Low"),
            _match("m4", 0.80, 0.12, 0.08, 0.50, "High", "Low")]
    return tp.candidates(pd.DataFrame(rows))


def test_candidates_pick_likelier_side(cand):
    m1 = cand[cand.match_id == "m1"].set_index("market")
    assert m1.loc["1x2", "side"] == "home"
    assert m1.loc["over_2_5", "side"] == "under"
    assert m1.loc["over_2_5", "prob"] == pytest.approx(0.60)
    assert m1.loc["1x2", "fair_odds"] == pytest.approx(1.43)


def test_free_tips_one_per_match_and_skip_low(cand):
    free = tp.free_tips(cand)
    assert set(free.match_id) == {"m1", "m2", "m4"}   # m3 only has Low picks
    assert free.match_id.is_unique


def test_premium_high_only_sorted(cand):
    prem = tp.premium(cand)
    assert set(prem.tier) == {"High"}
    assert list(prem.match_id) == ["m4", "m1", "m2"]


def test_diamond_respects_min_odds(cand):
    d = tp.diamond(cand, tp.Settings(diamond_min_odds=1.30))
    assert list(d.match_id) == ["m1"]        # m4 at 0.80 has fair odds 1.25


def test_coupon_probability_is_product(cand):
    cps = {c["name"]: c for c in tp.coupons(cand)}
    assert cps["Double"]["prob"] == pytest.approx(0.80 * 0.70)
    assert cps["Treble"]["prob"] == pytest.approx(0.80 * 0.70 * 0.66)
    assert len({leg["match_id"] for leg in cps["Treble"]["legs"]}) == 3


def test_settle(cand):
    res = pd.DataFrame([{"match_id": "m1", "home_goals": 2, "away_goals": 0},
                        {"match_id": "m4", "home_goals": 1, "away_goals": 1}])
    st = tp.settle(cand[cand.market == "1x2"], res).set_index("match_id")["status"]
    assert st["m1"] == "won" and st["m4"] == "lost" and st["m2"] == "pending"
    st25 = tp.settle(cand[cand.market == "over_2_5"], res).set_index("match_id")["status"]
    assert st25["m1"] == "won"               # under 2.5, two goals


def test_coupon_settles_lost_if_any_leg_lost(cand):
    double = tp.coupons(cand)[0]
    res = pd.DataFrame([{"match_id": "m4", "home_goals": 0, "away_goals": 1},
                        {"match_id": "m1", "home_goals": 3, "away_goals": 0}])
    assert tp.settle_coupon(double, res) == "lost"
