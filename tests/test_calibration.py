"""Calibration maps must fix timid forecasts, leave good ones alone, and keep every
market consistent with the scoreline table."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import check_grad

from fp.ensemble import calibration as cal
from fp.models import dixon_coles as dc


def timid_world(n=6000, seed=3, squeeze=0.7):
    """Outcomes drawn from true probabilities; the forecaster reports a squeezed
    version (true ** squeeze, renormalised), like our Dixon-Coles models."""
    rng = np.random.default_rng(seed)
    true = rng.dirichlet([4, 2.5, 3], n)
    y = np.array([rng.choice(3, p=t) for t in true])
    timid = true ** squeeze
    timid /= timid.sum(axis=1, keepdims=True)
    return true, timid, y


def test_power_calibration_undoes_a_known_squeeze():
    _, timid, y = timid_world()
    fitted = cal.PowerCalibration.fit(timid, y)
    assert fitted.alpha == pytest.approx(1 / 0.7, rel=0.1)
    assert cal._nll(fitted.apply(timid), y) < cal._nll(timid, y)


def test_dirichlet_calibration_improves_timid_forecasts():
    _, timid, y = timid_world()
    fitted = cal.DirichletCalibration.fit(timid, y)
    assert cal._nll(fitted.apply(timid), y) < cal._nll(timid, y)


def test_calibration_leaves_honest_forecasts_nearly_alone():
    true, _, y = timid_world()
    fitted = cal.PowerCalibration.fit(true, y)
    assert fitted.alpha == pytest.approx(1.0, abs=0.08)


def test_outputs_are_probabilities():
    _, timid, y = timid_world(n=500)
    for c in (cal.PowerCalibration.fit(timid, y), cal.DirichletCalibration.fit(timid, y)):
        q = c.apply(timid)
        assert np.allclose(q.sum(axis=1), 1, atol=1e-9)
        assert (q >= 0).all()


def test_dirichlet_gradient_is_correct():
    _, timid, y = timid_world(n=300)
    args = (np.log(timid), np.eye(3)[y], 0.01)
    theta = np.concatenate([np.eye(3).ravel(), np.zeros(3)]) + 0.05
    err = check_grad(lambda t: cal.dirichlet_objective(t, *args)[0],
                     lambda t: cal.dirichlet_objective(t, *args)[1], theta)
    assert err < 1e-5


def test_rescaled_matrix_matches_calibrated_1x2():
    m = dc.score_matrix(1.6, 1.1, -0.08)
    target = np.array([0.55, 0.25, 0.20])
    out = dc.markets(cal.rescale_matrix(m, target))
    assert [out["p_home"], out["p_draw"], out["p_away"]] == pytest.approx(target.tolist())


def test_save_and_load_round_trip(tmp_path):
    _, timid, y = timid_world(n=500)
    c = cal.DirichletCalibration.fit(timid, y)
    cal.save(c, tmp_path / "c.json", fitted_on="test")
    back = cal.load(tmp_path / "c.json")
    assert np.allclose(back.apply(timid), c.apply(timid))


def test_calibration_slope_detects_timidity():
    true, timid, y = timid_world()
    won = (y == 0).astype(float)
    assert cal.calibration_slope(timid[:, 0], won) > 1.1
    assert cal.calibration_slope(true[:, 0], won) == pytest.approx(1.0, abs=0.1)
