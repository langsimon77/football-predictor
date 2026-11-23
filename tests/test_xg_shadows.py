"""xG shadow rows (pre-registration data/audit/preregistration_xg_2026_11.md, step 3).

Fake posteriors only: no real sampling runs here.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from fp.models import bayes_dc, shape
from fp.models.bayes_dc import Posterior
from fp.pipeline import daily, trial

NOW = pd.Timestamp("2026-11-23 04:41", tz="UTC")
MATCH = "EPL_2627_a_b"
JOINT, BLEND = daily.XG_MODELS["joint"], daily.XG_MODELS["blend"]
GOOD = {"rhat_max": 1.0, "ess_bulk_min": 1000, "divergences": 0}
P_COLS = ["p_home", "p_draw", "p_away", "p_over_2_5", "p_btts"]


def posterior(seed=0, home=0.25):
    rng = np.random.default_rng(seed)
    s, att = 400, np.array([0.4, -0.3])
    return Posterior(teams=["a", "b"], mu=np.full(s, 0.1), home=np.full(s, home),
                     rho=np.full(s, -0.05), att=att + rng.normal(0, 0.03, (s, 2)),
                     def_=-att * 0.5 + rng.normal(0, 0.03, (s, 2)), diagnostics=dict(GOOD))


def league_models(xg=None):
    mat = np.outer(poisson.pmf(np.arange(11), 1.5), poisson.pmf(np.arange(11), 1.0))
    return {"EPL": SimpleNamespace(
        dc_fit=SimpleNamespace(score_matrix=lambda h, a: mat / mat.sum(), converged=True),
        tracker=SimpleNamespace(gap=lambda h, a: 50.0),
        curve=SimpleNamespace(probs=lambda gap: np.array([[0.5, 0.27, 0.23]])),
        promoted=set(), games_played={}, bayes=posterior(), bayes_fallback=False,
        xg=xg if xg is not None else {})}


def cands():
    return pd.DataFrame([{"match_id": MATCH, "league": "EPL", "season": 2026,
                          "home_id": "a", "away_id": "b",
                          "kickoff_utc": NOW + pd.Timedelta(hours=30),
                          "late_lock": False, "relock_reason": None}])


SH = shape.Shape(1.25, 1.2, -0.01, -0.04)


def arms():
    return {"joint": posterior(seed=1, home=0.30), "blend": posterior(seed=2, home=0.20)}


def test_xg_rows_locked_as_shadow():
    xg = arms()
    rows = daily.build_rows(cands(), league_models(xg), NOW, False, sh=SH)
    rows = rows.set_index("model_name")
    for mode, name in daily.XG_MODELS.items():
        row = rows.loc[name]
        assert row["prediction_id"] == f"{MATCH}:{name}"
        flags = json.loads(row["flags"])
        assert "shadow" in flags and "xg" in flags
        assert shape.RULE not in flags                  # no shape fix on xG rows
        assert row["lock_utc"] == rows.loc["dc_bayes_v1", "lock_utc"]
        want = daily.bayes_markets(xg[mode], "a", "b", (1.0, 1.0), None)[1]
        for col in P_COLS:
            assert row[col] == pytest.approx(want[col])
        assert json.loads(row["intervals"]) == want["intervals"]


def test_failed_arm_locks_nothing():
    xg = {"joint": arms()["joint"]}
    rows = daily.build_rows(cands(), league_models(xg), NOW, False, sh=SH)
    names = set(rows["model_name"])
    assert JOINT in names and BLEND not in names


def test_xg_rows_use_news_scale(monkeypatch):
    monkeypatch.setattr(daily.impact, "scales", lambda h, a: (1.1, 0.9, False))
    monkeypatch.setattr(daily.impact, "record", lambda h, a, src: {"rule": "test"})
    news = SimpleNamespace(
        manager_flags=set(),
        by_match={MATCH: SimpleNamespace(home=None, away=None, source="test",
                                         unanswered=lambda mid: [])})
    xg = arms()
    rows = daily.build_rows(cands(), league_models(xg), NOW, False, news=news, sh=SH)
    rows = rows.set_index("model_name")
    for mode, name in daily.XG_MODELS.items():
        want = bayes_dc.markets(xg[mode], "a", "b", scale=(1.1, 0.9))
        for col in P_COLS:
            assert rows.loc[name, col] == pytest.approx(want[col])
        # Same flag pattern as the no-shape control row: no news_adjusted.
        assert "news_adjusted" not in json.loads(rows.loc[name, "flags"])
    assert "news_adjusted" in json.loads(rows.loc["dc_bayes_v1", "flags"])


def test_published_row_unchanged():
    with_xg = daily.build_rows(cands(), league_models(arms()), NOW, False, sh=SH)
    without = daily.build_rows(cands(), league_models(), NOW, False, sh=SH)
    a = with_xg[with_xg["model_name"] == "dc_bayes_v1"].reset_index(drop=True)
    b = without[without["model_name"] == "dc_bayes_v1"].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    # The xG rows are the only extra rows.
    assert set(with_xg["model_name"]) - set(without["model_name"]) == {JOINT, BLEND}


def test_arm_whose_markets_raise_locks_nothing():
    broken = posterior(seed=5)
    broken.teams = ["a", "b"]
    broken.att = broken.att[:, :1]                      # index b out of range: markets raise
    xg = {"joint": broken, "blend": arms()["blend"]}
    rows = daily.build_rows(cands(), league_models(xg), NOW, False, sh=SH)
    names = set(rows["model_name"])
    assert JOINT not in names and BLEND in names
    without = daily.build_rows(cands(), league_models(), NOW, False, sh=SH)
    pd.testing.assert_frame_equal(
        rows[rows["model_name"] == "dc_bayes_v1"].reset_index(drop=True),
        without[without["model_name"] == "dc_bayes_v1"].reset_index(drop=True))


def test_xg_rows_without_shape_fix():
    rows = daily.build_rows(cands(), league_models(arms()), NOW, False)
    assert {JOINT, BLEND} <= set(rows["model_name"])


def test_trial_keeps_xg_rows():
    rows = daily.build_rows(cands(), league_models(arms()), NOW, False, sh=SH)
    out = trial.trim(rows).set_index("model_name")
    assert {JOINT, BLEND} <= set(out.index)
    for name in (JOINT, BLEND):  # treated like the no-shape shadow row
        assert pd.notna(out.loc[name, "exp_goals_home"])
        assert pd.isna(out.loc[name, "p_over_2_5"])
        assert "trial" in json.loads(out.loc[name, "flags"])


def fit_league_env(monkeypatch, tmp_path, xg_fit):
    """Stub every model fit in fit_league; xg_fit(params) handles the xG arms."""
    t = NOW - pd.Timedelta(days=3)
    matches = pd.DataFrame([{"league": "EPL", "season": 2026, "home_id": "a", "away_id": "b",
                             "kickoff_utc": t, "result_available_utc": t}])
    fixtures = pd.DataFrame([{"league": "EPL", "home_id": "a"}, {"league": "EPL",
                                                                   "home_id": "b"}])
    monkeypatch.setattr(daily.dc, "fit", lambda *a, **k: SimpleNamespace(converged=True))

    class Tracker:
        def __init__(self, *a):
            pass

        def advance_to(self, now):
            pass

        def ensure_season(self, season):
            pass
    monkeypatch.setattr(daily.elo, "EloTracker", Tracker)
    monkeypatch.setattr(daily.elo, "curve_as_of", lambda tracker, now: None)
    monkeypatch.setattr(daily, "promoted_priors", lambda *a: {})
    main = posterior()
    calls = []

    def fit_checked(known, now, teams, priors, params):
        calls.append(params.xg_mode)
        return main if params.xg_mode == "none" else xg_fit(params)
    monkeypatch.setattr(daily.bayes_dc, "fit_checked", fit_checked)
    saved = []
    monkeypatch.setattr(daily.posterior_store, "save", lambda post, *a, **k: saved.append(post))
    prior = SimpleNamespace(for_season=lambda tbs, season: {})
    models = daily.fit_league(matches, fixtures, "EPL", NOW, prior, 2026,
                              second_tier=pd.DataFrame(), promo=object(), with_bayes=True,
                              store=tmp_path)
    return models, main, calls, saved


def test_xg_fit_error_does_not_block(monkeypatch, tmp_path):
    def boom(params):
        raise RuntimeError("sampler crashed")
    models, main, calls, saved = fit_league_env(monkeypatch, tmp_path, boom)
    assert models.bayes is main and not models.bayes_fallback
    assert models.xg == {}
    assert calls == ["none", "joint", "blend"]
    assert saved == [main]


def test_xg_fit_keeps_only_passing_arms_and_saves_none(monkeypatch, tmp_path):
    good, bad = posterior(seed=3), posterior(seed=4)
    bad.diagnostics = {**GOOD, "rhat_max": 1.5}

    def fit(params):
        assert params.use_sot == daily.BAYES_PARAMS.use_sot
        assert params.sampler == daily.BAYES_PARAMS.sampler
        return good if params.xg_mode == "joint" else bad
    models, main, _, saved = fit_league_env(monkeypatch, tmp_path, fit)
    assert models.xg == {"joint": good}
    assert saved == [main]                              # xG posteriors never stored
