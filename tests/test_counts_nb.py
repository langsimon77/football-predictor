"""Corners and cards models: recover a known world, return valid distributions,
and widen the forecast when the referee is unknown."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fp.models import counts_nb as cn

AS_OF = pd.Timestamp("2026-06-01", tz="UTC")


def card_world(n_matches=900, alpha=8.0, seed=5):
    """Yellow cards from known discipline and referee effects, negative binomial."""
    rng = np.random.default_rng(seed)
    teams = [f"t{i}" for i in range(12)]
    refs = [f"r{i}" for i in range(8)]
    disc = dict(zip(teams, rng.normal(0, 0.15, 12), strict=True))
    ref_eff = dict(zip(refs, rng.normal(0, 0.2, 8), strict=True))
    rows = []
    for i in range(n_matches):
        h, a = rng.choice(teams, 2, replace=False)
        r = rng.choice(refs)
        mu = np.exp(np.log(4.0) + disc[h] + disc[a] + ref_eff[r])
        y = rng.negative_binomial(alpha, alpha / (alpha + mu))
        rows.append({"match_id": f"m{i}", "home": h, "away": a, "referee": r, "close": 0.0,
                     "fouls": 0.0, "derby": 0.0, "important": 0.0, "y": float(y),
                     "kickoff_utc": AS_OF - pd.Timedelta(days=int(n_matches - i))})
    frame = pd.DataFrame(rows)
    frame["close"] = rng.normal(0, 1, len(frame))
    frame["fouls"] = rng.normal(0, 1, len(frame))
    return frame, teams, alpha


@pytest.fixture(scope="module")
def fitted():
    frame, teams, alpha = card_world()
    p = cn.CountParams(target="cards", use_referee=True, xi=0.0, window_days=5000,
                       draws=500, tune=700, sampler="nutpie")
    return cn.fit_checked(frame, AS_OF, teams, p), frame, teams, alpha


def test_fit_passes_diagnostics(fitted):
    post, *_ = fitted
    assert post.ok, post.diagnostics


def test_dispersion_is_recovered(fitted):
    post, _, _, alpha = fitted
    lo, hi = np.percentile(post.draws["alpha"], [5, 95])
    assert lo < alpha < hi


def test_prediction_is_a_distribution(fitted):
    post, frame, _, _ = fitted
    out = cn.predict(post, frame.iloc[0].to_dict())
    assert out["pmf"].sum() == pytest.approx(1.0)
    assert out["over"][3.5] > out["over"][4.5] > out["over"][5.5]
    assert out["referee_known"]


def test_unknown_referee_widens_the_forecast(fitted):
    post, frame, _, _ = fitted
    row = frame.iloc[0].to_dict()
    known = cn.predict(post, row)
    unknown = cn.predict(post, {**row, "referee": None})
    k = np.arange(len(known["pmf"]))

    def var(pmf):
        mean = (pmf * k).sum()
        return float((pmf * (k - mean) ** 2).sum())

    assert not unknown["referee_known"]
    assert var(unknown["pmf"]) >= var(known["pmf"]) * 0.99
