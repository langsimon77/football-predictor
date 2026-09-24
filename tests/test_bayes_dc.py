"""Bayesian Dixon-Coles: the spec S13 simulation test and output checks.

The simulation test samples a real NUTS posterior, so it takes tens of seconds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fp.models import bayes_dc
from tests.test_dixon_coles import simulate

AS_OF = pd.Timestamp("2026-06-01", tz="UTC")


@pytest.fixture(scope="module")
def recovered():
    frame, truth = simulate(n_teams=20, seasons=2, seed=11)
    teams = sorted(truth["attack"])
    params = bayes_dc.BayesParams(xi=0.0, window_days=5000, seed=1)
    post = bayes_dc.fit(frame, AS_OF, teams, params=params)
    return post, truth, teams


def test_simulation_recovers_truth_within_90pct_intervals(recovered):
    """Spec S13: true values inside their 90% intervals at least 85% of the time.

    Team effects are only identified relative to the league mean (mu absorbs any
    shift), so both truth and posterior are centred before comparing.
    """
    post, truth, teams = recovered
    hits = []
    for name, draws in (("attack", post.att), ("defence", post.def_)):
        centred = draws - draws.mean(axis=1, keepdims=True)
        true = np.array([truth[name][t] for t in teams])
        true = true - true.mean()
        lo, hi = np.percentile(centred, [5, 95], axis=0)
        hits.extend((lo <= true) & (true <= hi))
    coverage = float(np.mean(hits))
    assert coverage >= 0.85, f"coverage {coverage:.0%}"


def test_simulation_diagnostics_pass(recovered):
    post, _, _ = recovered
    assert post.ok, post.diagnostics


def test_markets_are_valid_probabilities(recovered):
    post, _, teams = recovered
    out = bayes_dc.markets(post, teams[0], teams[1])
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-6)
    assert 0 < out["p_over_2_5"] < 1
    lo, hi = out["intervals"]["p_home"]
    assert lo <= out["p_home"] <= hi
    assert len(out["top_scorelines"]) == 5
