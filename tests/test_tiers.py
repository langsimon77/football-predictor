"""Tier rules (spec S7): favoured probability, one-step demotion, flag caps."""

from __future__ import annotations

import numpy as np

from fp.ensemble import tiers

TH = tiers.Thresholds(market="1x2", high=0.60, low=0.45, width_max=0.16, disagree_max=0.07)


def test_favoured_probability_sets_the_starting_tier():
    got = tiers.assign(TH, np.array([0.70, 0.60, 0.50, 0.45, 0.40]), np.zeros(5))
    assert got.tolist() == ["High", "High", "Medium", "Medium", "Low"]


def test_wide_interval_or_disagreement_drops_one_tier():
    fav = np.array([0.70, 0.70, 0.50, 0.40])
    got = tiers.assign(TH, fav, np.zeros(4), width=np.array([0.20, 0.10, 0.10, 0.20]),
                       disagree=np.array([0.01, 0.10, 0.10, 0.01]))
    assert got.tolist() == ["Medium", "Medium", "Low", "Low"]


def test_both_uncertainty_inputs_still_drop_only_one_tier():
    got = tiers.assign(TH, np.array([0.70]), np.zeros(1), width=np.array([0.3]),
                       disagree=np.array([0.3]))
    assert got.tolist() == ["Medium"]


def test_missing_inputs_never_demote():
    got = tiers.assign(TH, np.array([0.70]), np.zeros(1), width=np.array([np.nan]))
    assert got.tolist() == ["High"]


def test_one_flag_caps_at_medium_and_two_force_low():
    got = tiers.assign(TH, np.array([0.80, 0.50, 0.80, 0.50]), np.array([1, 1, 2, 2]))
    assert got.tolist() == ["Medium", "Medium", "Low", "Low"]


def test_fit_uses_quantiles_and_round_trips(tmp_path):
    rng = np.random.default_rng(0)
    fav = rng.uniform(0.34, 0.90, 3000)
    th = tiers.fit("1x2", fav, width=rng.uniform(0.1, 0.2, 3000))
    assert th.low < th.high
    assert th.high == round(float(np.quantile(fav, 0.75)), 2)
    assert th.disagree_max is None
    tiers.save([th], tmp_path / "t.json", fitted_on="test")
    assert tiers.load(tmp_path / "t.json")["1x2"] == th


def test_values_on_a_cut_point_are_not_moved_by_rounding():
    width = np.array([0.52 - 0.36])  # 0.16000000000000003 in floating point
    got = tiers.assign(TH, np.array([0.60]), np.zeros(1), width=width)
    assert got.tolist() == ["High"]
