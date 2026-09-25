"""The corners and cards fallback store: round trips exactly and refuses failed fits."""

from __future__ import annotations

import numpy as np
import pytest

from fp.models import counts_nb as cn
from fp.pipeline import counts_live


def fake_cards_posterior(ok: bool = True) -> cn.CountPosterior:
    rng = np.random.default_rng(1)
    s, n, r = 300, 4, 3
    return cn.CountPosterior(
        target="cards", teams=["a", "b", "c", "d"], referees=["r1", "r2", "r3"],
        draws={"intercept": rng.normal(1.4, 0.02, s), "disc": rng.normal(0, 0.1, (s, n)),
               "b": rng.normal(0, 0.05, (s, 4)), "sigma_disc": np.abs(rng.normal(0.1, 0.01, s)),
               "ref": rng.normal(0, 0.1, (s, r)), "sigma_ref": np.abs(rng.normal(0.1, 0.01, s)),
               "alpha": np.abs(rng.normal(30, 2, s))},
        scales={"close": (-1.0, 0.8), "fouls": (24.0, 2.5)}, poisson=False,
        diagnostics={"rhat_max": 1.003 if ok else 1.2, "ess_bulk_min": 900, "divergences": 0},
    )


ROW = {"home": "a", "away": "b", "referee": "r2", "close": -0.5, "fouls": 25.0,
       "derby": 1.0, "important": 0.0}


def test_round_trip_gives_identical_forecasts(tmp_path):
    post = fake_cards_posterior()
    counts_live.save(post, "EPL", tmp_path)
    loaded = counts_live.load("EPL", "cards", tmp_path)
    assert loaded is not None
    before, after = cn.predict(post, ROW), cn.predict(loaded, ROW)
    assert after["exp_total"] == pytest.approx(before["exp_total"])
    assert np.allclose(after["pmf"], before["pmf"])


def test_failed_posterior_is_never_stored(tmp_path):
    with pytest.raises(ValueError, match="refusing"):
        counts_live.save(fake_cards_posterior(ok=False), "EPL", tmp_path)


def test_missing_store_returns_none(tmp_path):
    assert counts_live.load("LaLiga", "cards", tmp_path) is None
