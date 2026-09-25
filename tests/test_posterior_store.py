"""The fallback store keeps only posteriors that passed their diagnostics (spec S5.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fp.models import bayes_dc, posterior_store

AS_OF = pd.Timestamp("2026-10-08 04:41", tz="UTC")


def fake_posterior(ok: bool) -> bayes_dc.Posterior:
    rng = np.random.default_rng(0)
    s, n = 200, 3
    diag = {"rhat_max": 1.002 if ok else 1.05, "ess_bulk_min": 900, "divergences": 0}
    return bayes_dc.Posterior(
        teams=["a", "b", "c"], mu=rng.normal(0.2, 0.02, s), home=rng.normal(0.25, 0.02, s),
        rho=rng.normal(-0.05, 0.01, s), att=rng.normal(0, 0.2, (s, n)),
        def_=rng.normal(0, 0.2, (s, n)), diagnostics=diag,
    )


def test_round_trip_gives_identical_forecasts(tmp_path):
    post = fake_posterior(ok=True)
    posterior_store.save(post, "EPL", AS_OF, tmp_path)
    loaded, meta = posterior_store.load("EPL", tmp_path)
    assert meta["as_of_utc"] == AS_OF.isoformat()
    before = bayes_dc.markets(post, "a", "b")
    after = bayes_dc.markets(loaded, "a", "b")
    assert after["p_home"] == pytest.approx(before["p_home"])
    assert after["intervals"] == before["intervals"]


def test_failed_posterior_is_never_stored(tmp_path):
    with pytest.raises(ValueError, match="refusing"):
        posterior_store.save(fake_posterior(ok=False), "EPL", AS_OF, tmp_path)


def test_missing_store_returns_none(tmp_path):
    assert posterior_store.load("LaLiga", tmp_path) is None
