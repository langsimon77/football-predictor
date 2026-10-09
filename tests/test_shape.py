"""Goals shape fix shape_v1 (approved by Lang on 9 Oct 2026)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.stats import poisson

from fp.models import shape
from fp.models.bayes_dc import Posterior
from fp.pipeline import daily

NOW = pd.Timestamp("2026-10-09 06:00", tz="UTC")


def test_poisson_case_matches_independent_poisson():
    lam, nu = np.array([1.7, 0.9]), np.array([0.8, 1.4])
    m = shape.shaped(lam, nu, shape.POISSON)
    g = np.arange(11)
    want = poisson.pmf(g, lam[0])[:, None] * poisson.pmf(g, nu[0])[None, :]
    # Same up to the 0-to-10 goal cut-off (mass beyond 10 is about 2e-6 here).
    assert np.allclose(m[0], want / want.sum(), atol=1e-5)
    assert np.allclose(m.sum(axis=(1, 2)), 1)


def test_com_poisson_keeps_the_mean_and_narrows_the_spread():
    for v in (0.8, 1.0, 1.3):
        p = shape.cmp_pmf(np.array([0.6, 1.4, 2.5]), v)
        k = np.arange(11)
        mean = (p * k).sum(1)
        var = (p * k**2).sum(1) - mean**2
        assert np.allclose(mean, [0.6, 1.4, 2.5], atol=1e-6)
        if v > 1:
            assert (var < mean).all()
        if v < 1:
            assert (var > mean).all()


def test_stretch_widens_the_gap_and_keeps_the_product():
    sh = shape.Shape(s=0.2)
    m = shape.shaped(np.array([2.0]), np.array([1.0]), sh)[0]
    k = np.arange(11)
    eh, ea = (m.sum(1) * k).sum(), (m.sum(0) * k).sum()
    assert eh > 2.0 and ea < 1.0
    assert abs(eh * ea - 2.0) < 1e-3


def test_fit_recovers_known_numbers():
    rng = np.random.default_rng(1)
    n = 6000
    lam, nu = rng.uniform(0.8, 2.4, n), rng.uniform(0.5, 1.6, n)
    truth = shape.Shape(vh=1.25, va=1.2, rho=-0.02, s=0.05)
    m = shape.shaped(lam, nu, truth).reshape(n, -1)
    cells = np.array([rng.choice(121, p=row) for row in m])
    got = shape.fit(lam, nu, cells // 11, cells % 11)
    assert abs(got.vh - 1.25) < 0.08 and abs(got.va - 1.2) < 0.08
    assert abs(got.s - 0.05) < 0.06


def ledger_frame():
    base = {"lock_utc": NOW - pd.Timedelta(days=3), "kickoff_utc": NOW - pd.Timedelta(days=2)}
    return pd.DataFrame([
        {**base, "match_id": "m1", "model_name": "dc_bayes_v1", "flags": "[]",
         "exp_goals_home": 1.5, "exp_goals_away": 1.0},
        {**base, "match_id": "m2", "model_name": "dc_bayes_v1", "flags": json.dumps(["shape_v1"]),
         "exp_goals_home": 1.9, "exp_goals_away": 0.8},
        {**base, "match_id": "m2", "model_name": "dc_bayes_v1_noshape", "flags": "[]",
         "exp_goals_home": 2.0, "exp_goals_away": 0.7},
    ])


def matches_frame():
    return pd.DataFrame({
        "match_id": ["m1", "m2", "old"], "home_goals": [2, 1, 0], "away_goals": [0, 1, 0],
        "kickoff_utc": [NOW - pd.Timedelta(days=2)] * 2 + [NOW - pd.Timedelta(days=900)],
        "result_available_utc": [NOW - pd.Timedelta(days=1)] * 3})


def test_history_uses_the_plain_forecast(tmp_path):
    h = shape.history(matches_frame(), ledger_frame(), NOW, backtest=tmp_path / "none.parquet")
    got = h.set_index("match_id")
    assert set(got.index) == {"m1", "m2"}          # "old" is outside the 730 days
    assert got.loc["m1", "lam"] == 1.5              # locked before the fix: plain row
    assert got.loc["m2", "lam"] == 2.0              # after: the no-shape copy, not the fix


def test_current_refits_once_a_month(tmp_path, monkeypatch):
    store = tmp_path / "shape.json"
    calls = []
    monkeypatch.setattr(shape, "history", lambda *a, **k: pd.DataFrame(
        {"lam": np.full(400, 1.4), "nu": np.full(400, 1.1), "hg": np.tile([0, 1, 2, 3], 100),
         "ag": np.tile([1, 0, 1, 2], 100)}))
    real_fit = shape.fit
    monkeypatch.setattr(shape, "fit", lambda *a, **k: calls.append(1) or real_fit(*a, **k))
    first = shape.current(pd.DataFrame(), pd.DataFrame(), NOW, store)
    again = shape.current(pd.DataFrame(), pd.DataFrame(), NOW + pd.Timedelta(days=5), store)
    assert first == again and len(calls) == 1
    shape.current(pd.DataFrame(), pd.DataFrame(), pd.Timestamp("2026-11-01 06:00", tz="UTC"),
                  store)
    data = json.loads(store.read_text())
    assert len(calls) == 2 and data["current"]["month"] == "2026-11"
    assert [e["month"] for e in data["history"]] == ["2026-10", "2026-11"]


def posterior():
    rng = np.random.default_rng(0)
    s, att = 400, np.array([0.4, -0.3])
    return Posterior(teams=["a", "b"], mu=np.full(s, 0.1), home=np.full(s, 0.25),
                     rho=np.full(s, -0.05), att=att + rng.normal(0, 0.03, (s, 2)),
                     def_=-att * 0.5 + rng.normal(0, 0.03, (s, 2)))


def test_apply_point_is_the_tested_method():
    post = posterior()
    from fp.models import bayes_dc
    plain = bayes_dc.markets(post, "a", "b")
    lam, nu = post.rates("a", "b")
    sh = shape.Shape(1.25, 1.2, -0.01, -0.04)
    got = shape.apply(plain, lam, nu, sh)
    want = shape.shaped(np.array([plain["exp_goals_home"]]), np.array([plain["exp_goals_away"]]),
                        sh)[0]
    assert abs(got["p_home"] - np.tril(want, -1).sum()) < 1e-9
    assert set(got["intervals"]) == set(plain["intervals"])
    lo, hi = got["intervals"]["p_home"]
    assert lo < got["p_home"] < hi


def test_build_rows_locks_the_fix_and_a_plain_copy():
    mat = np.outer(poisson.pmf(np.arange(11), 1.5), poisson.pmf(np.arange(11), 1.0))
    models = {"EPL": SimpleNamespace(
        dc_fit=SimpleNamespace(score_matrix=lambda h, a: mat / mat.sum(), converged=True),
        tracker=SimpleNamespace(gap=lambda h, a: 50.0),
        curve=SimpleNamespace(probs=lambda gap: np.array([[0.5, 0.27, 0.23]])),
        promoted=set(), games_played={}, bayes=posterior(), bayes_fallback=False)}
    cands = pd.DataFrame([{"match_id": "EPL_2627_a_b", "league": "EPL", "season": 2026,
                           "home_id": "a", "away_id": "b", "kickoff_utc": NOW + pd.Timedelta(
                               hours=30), "late_lock": False, "relock_reason": None}])
    sh = shape.Shape(1.25, 1.2, -0.01, -0.04)
    rows = daily.build_rows(cands, models, NOW, False, sh=sh).set_index("model_name")
    assert {"dc_bayes_v1", "dc_bayes_v1_noshape", "elo_v0", "dc_mle_v0"} <= set(rows.index)
    primary, plain = rows.loc["dc_bayes_v1"], rows.loc["dc_bayes_v1_noshape"]
    assert "shape_v1" in json.loads(primary["flags"])
    assert {"shadow", "no_shape"} <= set(json.loads(plain["flags"]))
    assert primary["p_btts"] > plain["p_btts"]      # fewer blanks with less spread
    assert abs(primary[["p_home", "p_draw", "p_away"]].sum() - 1) < 1e-9
    off = daily.build_rows(cands, models, NOW, False).set_index("model_name")
    assert "dc_bayes_v1_noshape" not in off.index
    assert abs(off.loc["dc_bayes_v1", "p_home"] - plain["p_home"]) < 1e-12
