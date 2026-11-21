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


def test_basketball_candidates_and_settle():
    games = pd.DataFrame([
        {"game_id": "g1", "league": "ACB", "tip_utc": "2026-11-22 18:00",
         "home_name": "Real Madrid",
         "away_name": "Joventut", "p_home": 0.86},
        {"game_id": "g2", "league": "NBL", "tip_utc": "2026-11-22 06:00", "home_name": "Brisbane",
         "away_name": "Sydney", "p_home": 0.35},
        {"game_id": "g3", "league": "ACB", "tip_utc": "2026-11-22 18:00", "home_name": "A",
         "away_name": "B", "p_home": float("nan")}])
    c = tp.basketball_candidates(games, high=0.74, low=0.60).set_index("match_id")
    assert list(c.index) == ["g1", "g2"]                 # no chance, no pick
    assert c.loc["g1", "tier"] == "High" and c.loc["g1", "side"] == "home"
    assert c.loc["g2", "side"] == "away" and c.loc["g2", "prob"] == pytest.approx(0.65)
    assert c.loc["g2", "tier"] == "Medium"
    assert "Sydney to win" in c.loc["g2", "pick"]
    res = pd.DataFrame([{"match_id": "g1", "home_pts": 90, "away_pts": 95},
                        {"match_id": "g2", "home_pts": 70, "away_pts": 80}])
    st = tp.settle(c.reset_index(), res).set_index("match_id")["status"]
    assert st["g1"] == "lost" and st["g2"] == "won"


def test_basketball_and_football_mix_in_products(cand):
    games = pd.DataFrame([{"game_id": "g1", "league": "ACB", "tip_utc": "2026-11-22 18:00",
                           "home_name": "X", "away_name": "Y", "p_home": 0.90}])
    both = pd.concat([cand, tp.basketball_candidates(games, 0.74, 0.60)], ignore_index=True)
    prem = tp.premium(both)
    assert prem.iloc[0]["match_id"] == "g1"              # strongest High pick first
    assert prem.match_id.is_unique


def test_nbl_kept_out_of_diamond_and_coupons(cand):
    games = pd.DataFrame([{"game_id": "n1", "league": "NBL", "tip_utc": "2026-11-22 06:00",
                           "home_name": "X", "away_name": "Y", "p_home": 0.95}])
    both = pd.concat([cand, tp.basketball_candidates(games, 0.74, 0.60)], ignore_index=True)
    assert "n1" in set(tp.premium(both).match_id)          # Premium keeps it
    assert "n1" not in set(tp.diamond(both).match_id)
    assert all(leg["match_id"] != "n1" for c in tp.coupons(both) for leg in c["legs"])


def test_top3_bankers_full_card(cand):
    t3 = tp.top3(cand)
    assert list(t3.match_id) == ["m4", "m1", "m2"]        # likeliest first, Medium or better
    assert set(tp.bankers(cand).tier) == {"High"}
    assert len(tp.bankers(cand)) == 3                      # no cap: every High game
    fc = tp.full_card(cand)
    assert fc.groupby("match_id").size().max() <= 2
    # m1 has result (High) and goals (Low): only Medium or better, so one pick
    assert (fc.match_id == "m1").sum() == 1


def test_full_card_two_families_not_two_goal_lines():
    rows = [{"match_id": "x", "league": "EPL", "kickoff_utc": "2026-11-22 15:00",
             "home_id": "a", "away_id": "b", "p_home": 0.70, "p_draw": 0.2, "p_away": 0.1,
             "p_over_1_5": 0.85, "p_over_2_5": 0.70,
             "tiers": json.dumps({"rule": "tiers_v1", "1x2": "High", "over_1_5": "High",
                                  "over_2_5": "High"})}]
    fc = tp.full_card(tp.candidates(pd.DataFrame(rows)))
    assert sorted(fc.market) == ["1x2", "over_1_5"]       # one goals pick, one result pick


def test_correct_scores_and_settle():
    fc = pd.DataFrame([
        {"match_id": "a", "league": "EPL", "kickoff_utc": "t", "home_id": "h", "away_id": "w",
         "top_scorelines": json.dumps([{"score": "1-1", "p": 0.11}, {"score": "2-1", "p": 0.12}])},
        {"match_id": "b", "league": "EPL", "kickoff_utc": "t", "home_id": "h", "away_id": "w",
         "top_scorelines": json.dumps([{"score": "0-0", "p": 0.14}])},
        {"match_id": "c", "league": "EPL", "kickoff_utc": "t", "home_id": "h", "away_id": "w",
         "top_scorelines": None}])
    cs = tp.correct_scores(fc, n=5)
    assert list(cs.match_id) == ["b", "a"] and list(cs.side) == ["0-0", "2-1"]
    res = pd.DataFrame([{"match_id": "a", "home_goals": 2, "away_goals": 1},
                        {"match_id": "b", "home_goals": 1, "away_goals": 0}])
    st = tp.settle(cs, res).set_index("match_id")["status"]
    assert st["a"] == "won" and st["b"] == "lost"


def test_accumulators_named_by_size(cand):
    acc = tp.accumulators(cand, sizes=(3,))
    assert [a["name"] for a in acc] == ["3-fold"]
    assert acc[0]["prob"] == pytest.approx(0.80 * 0.70 * 0.66)


def test_bb_markets_match_live():
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("make_tips", root / "scripts" / "make_tips.py")
    mt = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root / "basketball"))
    spec.loader.exec_module(mt)
    live = importlib.import_module("live")
    assert {k: tuple(v) for k, v in live.MARKETS.items()} == mt.BB_MARKETS
