from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

from fp.models import dixon_coles as dc

AS_OF = pd.Timestamp("2026-06-01", tz="UTC")


def simulate(n_teams=20, seasons=3, rho=-0.08, seed=7):
    """Double round-robin seasons from known strengths, with the DC correction."""
    rng = np.random.default_rng(seed)
    teams = [f"t{i}" for i in range(n_teams)]
    attack = rng.normal(0, 0.3, n_teams)
    defence = rng.normal(0, 0.25, n_teams)
    attack -= attack.mean()
    defence -= defence.mean()
    mu, home = 0.25, 0.25
    rows = []
    day = AS_OF - pd.Timedelta(days=365 * seasons)
    for _ in range(seasons):
        for h in range(n_teams):
            for a in range(n_teams):
                if h == a:
                    continue
                lam = np.exp(mu + home + attack[h] + defence[a])
                nu = np.exp(mu + attack[a] + defence[h])
                m = dc.score_matrix(lam, nu, rho)
                k = rng.choice(m.size, p=m.ravel())
                i, j = np.unravel_index(k, m.shape)
                rows.append((teams[h], teams[a], i, j, day))
                day += pd.Timedelta(hours=11)
    frame = pd.DataFrame(rows, columns=["home_id", "away_id", "home_goals", "away_goals",
                                        "kickoff_utc"])
    truth = dict(mu=mu, home=home, rho=rho, attack=dict(zip(teams, attack, strict=True)),
                 defence=dict(zip(teams, defence, strict=True)))
    return frame, truth


def test_gradient_matches_numerical_gradient():
    frame, _ = simulate(n_teams=6, seasons=1)
    teams = sorted(set(frame.home_id))
    idx = {t: i for i, t in enumerate(teams)}
    hi, ai = frame.home_id.map(idx).to_numpy(), frame.away_id.map(idx).to_numpy()
    x, y = frame.home_goals.to_numpy(float), frame.away_goals.to_numpy(float)
    w = np.linspace(0.5, 1.0, len(x))
    n = len(teams)
    prior = np.zeros(n)
    args = (hi, ai, x, y, w, n, 2.0, prior, prior)
    theta = np.random.default_rng(0).normal(0, 0.1, 3 + 2 * n)
    theta[2] = -0.05
    err = check_grad(lambda t: dc._objective(t, *args)[0], lambda t: dc._objective(t, *args)[1],
                     theta)
    assert err < 1e-4


def test_fit_recovers_known_strengths():
    frame, truth = simulate()
    fit = dc.fit(frame, AS_OF, dc.DCParams(xi=0.0, ridge=0.1, window_days=5000))
    assert fit.converged
    teams = sorted(truth["attack"])
    est_a = np.array([fit.attack[t] for t in teams])
    est_d = np.array([fit.defence[t] for t in teams])
    true_a = np.array([truth["attack"][t] for t in teams])
    true_d = np.array([truth["defence"][t] for t in teams])
    assert np.corrcoef(est_a, true_a)[0, 1] > 0.9
    assert np.corrcoef(est_d, true_d)[0, 1] > 0.85
    assert fit.home_adv == pytest.approx(truth["home"], abs=0.08)
    assert fit.rho == pytest.approx(truth["rho"], abs=0.08)


def test_score_matrix_is_a_distribution():
    m = dc.score_matrix(1.6, 1.1, -0.1)
    assert m.min() >= 0
    assert m.sum() == pytest.approx(1.0)


def test_markets_are_consistent():
    out = dc.markets(dc.score_matrix(1.6, 1.1, -0.1))
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-9)
    assert out["p_over_1_5"] > out["p_over_2_5"] > out["p_over_3_5"]
    assert 0 < out["p_btts"] < 1
    assert out["exp_goals_home"] == pytest.approx(1.6, abs=0.05)
    assert len(out["top_scorelines"]) == 5


def test_ridge_pulls_an_unseen_team_to_its_prior():
    frame, _ = simulate(n_teams=6, seasons=1)
    fit = dc.fit(frame, AS_OF, prior_means={"new": (-0.3, 0.3)}, extra_teams=["new"])
    assert fit.attack["new"] == pytest.approx(-0.3, abs=1e-3)
    assert fit.defence["new"] == pytest.approx(0.3, abs=1e-3)
