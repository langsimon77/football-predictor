"""Stacking: weights obey the floor, find the better model, and move within limits."""

from __future__ import annotations

import numpy as np
import pytest

from fp.ensemble import stacking


def world(n=4000, seed=2):
    rng = np.random.default_rng(seed)
    true = rng.dirichlet([4, 2.5, 3], n)
    y = np.array([rng.choice(3, p=t) for t in true])
    noisy = true + rng.normal(0, 0.08, true.shape)
    noisy = np.clip(noisy, 0.02, None)
    noisy /= noisy.sum(axis=1, keepdims=True)
    flat = np.full_like(true, 1 / 3)
    return {"good": true, "noisy": noisy, "flat": flat}, y


def test_weights_sum_to_one_and_respect_the_floor():
    probs, y = world()
    s = stacking.fit(probs, y)
    assert s.weights.sum() == pytest.approx(1.0)
    assert (s.weights >= stacking.FLOOR - 1e-9).all()


def test_the_best_model_gets_the_most_weight():
    probs, y = world()
    s = stacking.fit(probs, y)
    assert s.models[int(np.argmax(s.weights))] == "good"
    assert s.weights[s.models.index("flat")] == pytest.approx(stacking.FLOOR, abs=0.02)


def test_combined_forecast_is_a_distribution():
    probs, y = world(n=500)
    s = stacking.fit(probs, y)
    q = s.combine(probs)
    assert np.allclose(q.sum(axis=1), 1)


def test_weekly_move_is_capped_and_floored():
    current = np.array([0.6, 0.3, 0.1])
    target = np.array([0.05, 0.05, 0.9])
    new = stacking.guarded_update(current, target, n_scored=200)
    assert np.abs(new - current).max() <= 0.10 + 1e-9
    assert new.sum() == pytest.approx(1.0)
    assert (new >= stacking.FLOOR - 1e-9).all()


def test_no_move_before_enough_live_predictions():
    current = np.array([0.5, 0.5])
    new = stacking.guarded_update(current, np.array([0.1, 0.9]), n_scored=59)
    assert np.allclose(new, current)
