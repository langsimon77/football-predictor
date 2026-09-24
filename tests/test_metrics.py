from __future__ import annotations

import numpy as np
import pytest

from fp.evaluate import metrics


def test_rps_perfect_and_worst():
    assert metrics.rps(np.array([[1.0, 0, 0]]), np.array([0]))[0] == 0
    assert metrics.rps(np.array([[0, 0, 1.0]]), np.array([0]))[0] == pytest.approx(1.0)


def test_rps_rewards_near_misses():
    """Forecasting a draw when home wins beats forecasting an away win."""
    draw = metrics.rps(np.array([[0, 1.0, 0]]), np.array([0]))[0]
    away = metrics.rps(np.array([[0, 0, 1.0]]), np.array([0]))[0]
    assert draw < away


def test_rps_hand_worked_example():
    # Forecast (0.5, 0.3, 0.2), home wins: ((0.5-1)^2 + (0.8-1)^2) / 2 = 0.145
    assert metrics.rps(np.array([[0.5, 0.3, 0.2]]), np.array([0]))[0] == pytest.approx(0.145)


def test_log_loss_matches_learn_md_example():
    p = np.array([[0.727, 0.174, 0.099]])
    assert metrics.log_loss(p, np.array([0]))[0] == pytest.approx(0.319, abs=1e-3)


def test_outcome_codes():
    assert list(metrics.outcome_1x2(np.array([2, 1, 0]), np.array([1, 1, 3]))) == [0, 1, 2]


def test_power_demargin_sums_to_one_and_favours_trimming_longshots():
    odds = np.array([[1.36, 5.70, 10.00]])  # Man City v Sunderland, Betfair closing
    p = metrics.demargin_power(odds)[0]
    assert p.sum() == pytest.approx(1.0)
    proportional = (1 / odds[0]) / (1 / odds[0]).sum()
    assert p[2] < proportional[2]  # the long shot loses more
    assert p[0] > proportional[0]


def test_power_demargin_handles_missing_odds():
    assert np.isnan(metrics.demargin_power(np.array([[np.nan, 3.0, 3.0]]))).all()
