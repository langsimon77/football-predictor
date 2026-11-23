"""xg_mode in the Bayesian model: graph-level checks only, no MCMC.

Each test compiles the named Potentials at model.initial_point() and compares numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytensor
import pytest

from fp.models import bayes_dc

AS_OF = pd.Timestamp("2026-11-01", tz="UTC")
TEAMS = [f"t{i}" for i in range(6)]


def frame(n=40, seed=3, xg=True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    home = rng.integers(0, 6, n)
    away = (home + rng.integers(1, 6, n)) % 6
    df = pd.DataFrame({
        "kickoff_utc": AS_OF - pd.to_timedelta(rng.integers(1, 300, n), unit="D"),
        "home_id": [TEAMS[i] for i in home], "away_id": [TEAMS[i] for i in away],
        "home_goals": rng.poisson(1.5, n), "away_goals": rng.poisson(1.1, n),
    })
    if xg:
        df["home_xg"] = rng.gamma(4, 0.4, n)
        df["away_xg"] = rng.gamma(4, 0.3, n)
    return df


def build(df: pd.DataFrame, xg_mode: str | None = None, xi: float = 0.002):
    p = bayes_dc.BayesParams(xi=xi)
    d = bayes_dc._arrays(df, TEAMS, AS_OF, p)
    n = len(TEAMS)
    args = (d, n, np.zeros(n), np.ones(n), np.zeros(n), np.ones(n), np.zeros(n, dtype=bool),
            False)
    return bayes_dc.build_model(*args) if xg_mode is None else \
        bayes_dc.build_model(*args, xg_mode=xg_mode)


def value(model, name: str, point: dict | None = None) -> float:
    ip = point or model.initial_point()
    pot = next(v for v in model.potentials if v.name == name)
    # The Potential is written in terms of random variables; swap them for value variables
    # so the compiled function is deterministic at the given point.
    (out,) = model.replace_rvs_by_values([pot])
    fn = pytensor.function(model.value_vars, out, on_unused_input="ignore")
    return float(fn(*[ip[v.name] for v in model.value_vars]))


def test_none_matches_today():
    df = frame()
    a, b = build(df), build(df, "none")
    assert a.compile_logp()(a.initial_point()) == b.compile_logp()(b.initial_point())
    assert [v.name for v in b.potentials] == ["goals"]


def test_joint_without_xg_adds_zero():
    df = frame(xg=False)
    j, n = build(df, "joint"), build(df, "none")
    assert value(j, "xg") == 0.0
    assert value(j, "goals") == value(n, "goals")


def test_blend_without_xg_equals_today():
    df = frame(xg=False)
    assert value(build(df, "blend"), "goals") == value(build(df, "none"), "goals")


def test_arrays_xg_keys():
    df = frame()
    df.loc[0, "home_xg"] = np.nan
    d = bayes_dc._arrays(df, TEAMS, AS_OF, bayes_dc.BayesParams())
    assert d["mx"][0] == 0.0 and d["xh"][0] == 0.0 and d["mx"][1:].all()
    assert "mx" in bayes_dc._arrays(frame(xg=False), TEAMS, AS_OF, bayes_dc.BayesParams())


def _blend_single(goals, xg, rho_u=0.7):
    df = pd.DataFrame({
        "kickoff_utc": [AS_OF], "home_id": ["t0"], "away_id": ["t1"],
        "home_goals": [goals[0]], "away_goals": [goals[1]],
        "home_xg": [xg[0]], "away_xg": [xg[1]],
    })
    m = build(df, "blend", xi=0.0)
    ip = m.initial_point()
    ip["rho_interval__"] = np.array(rho_u)  # off-centre so tau is not 1
    rho = -0.2 + 0.4 / (1 + np.exp(-rho_u))
    return value(m, "goals", ip), rho, np.exp(0.2 + 0.25), np.exp(0.2)


def test_blend_uses_half_goals_half_xg():
    got, _rho, lam, nu = _blend_single((2, 0), (1.0, 1.0))
    # counts (1.5, 0.5); a 2-0 score is outside the tau corrections, so tau = 1
    assert got == pytest.approx(1.5 * 0.45 - lam + 0.5 * 0.2 - nu, rel=1e-9)


def test_blend_tau_uses_real_score():
    got, rho, lam, nu = _blend_single((1, 0), (0.2, 0.2))
    # counts (0.6, 0.1); tau takes the 1-0 branch from the real score
    expected = np.log(1 + nu * rho) + 0.6 * 0.45 - lam + 0.1 * 0.2 - nu
    assert got == pytest.approx(expected, rel=1e-9)


def test_partial_xg_rows_add_nothing():
    df = frame(n=40)
    half = df.copy()
    half.loc[half.index[::2], ["home_xg", "away_xg"]] = np.nan
    only = df.loc[half.index[1::2]].reset_index(drop=True)
    assert value(build(half, "joint"), "xg") == pytest.approx(value(build(only, "joint"), "xg"))
    # joint leaves the goals term alone
    assert value(build(half, "joint"), "goals") == value(build(half, "none"), "goals")


def test_blend_partial_xg_rows():
    df = frame(n=40)
    half = df.copy()
    half.loc[half.index[::2], ["home_xg", "away_xg"]] = np.nan
    xg_rows = df.loc[half.index[1::2]].reset_index(drop=True)
    nan_rows = df.loc[half.index[::2]].drop(columns=["home_xg", "away_xg"]).reset_index(drop=True)
    # Row terms add up, so blend(all) - blend(xG rows) is the NaN rows, which are plain goals.
    diff = value(build(half, "blend"), "goals") - value(build(xg_rows, "blend"), "goals")
    assert diff == pytest.approx(value(build(nan_rows, "none"), "goals"))


def test_joint_xg_term_matches_formula():
    df = frame()
    m = build(df, "joint")
    d = bayes_dc._arrays(df, TEAMS, AS_OF, bayes_dc.BayesParams())
    # at the initial point att = def = 0, mu_x = 0.3, home_x = 0.1
    eh, ea = 0.3 + 0.1, 0.3
    expected = np.sum(d["w"] * (d["xh"] * eh - np.exp(eh) + d["xa"] * ea - np.exp(ea)))
    assert value(m, "xg") == pytest.approx(expected)


def test_joint_xg_term_nonzero_strengths():
    df = frame()
    m = build(df, "joint")
    ip = m.initial_point()
    rng = np.random.default_rng(9)
    att_raw, def_raw = rng.normal(0, 0.4, 6), rng.normal(0, 0.4, 6)
    ip.update(att_raw=att_raw, def_raw=def_raw, mu_x=np.array(0.5), home_x=np.array(0.3),
              c_att=np.array(1.4), c_def=np.array(0.7))
    att, dfn = att_raw - att_raw.mean(), def_raw - def_raw.mean()
    d = bayes_dc._arrays(df, TEAMS, AS_OF, bayes_dc.BayesParams())
    hi, ai = d["hi"], d["ai"]
    ex_h = 0.5 + 0.3 + 1.4 * att[hi] + 0.7 * dfn[ai]
    ex_a = 0.5 + 1.4 * att[ai] + 0.7 * dfn[hi]
    expected = np.sum(d["w"] * d["mx"] * (d["xh"] * ex_h - np.exp(ex_h)
                                          + d["xa"] * ex_a - np.exp(ex_a)))
    assert value(m, "xg", ip) == pytest.approx(expected)


def test_bad_mode_rejected():
    with pytest.raises(ValueError):
        build(frame(), "nope")


def test_fit_checked_retry_keeps_xg_mode(monkeypatch):
    seen = []

    def fake_fit(train, as_of, teams, promoted_priors=None, params=None):
        seen.append(params.xg_mode)
        return bayes_dc.Posterior(teams=[], mu=np.zeros(1), home=np.zeros(1), rho=np.zeros(1),
                                  att=np.zeros((1, 1)), def_=np.zeros((1, 1)),
                                  diagnostics={"rhat_max": 9})

    monkeypatch.setattr(bayes_dc, "fit", fake_fit)
    bayes_dc.fit_checked(frame(), AS_OF, TEAMS, params=bayes_dc.BayesParams(xg_mode="blend"))
    assert seen == ["blend", "blend"]


def fake_sample(seen):
    import xarray as xr

    def sample(**kw):
        seen["var_names"] = list(kw["var_names"])
        rng = np.random.default_rng(0)
        chains, draws, n = 2, 20, len(TEAMS)
        data = {}
        for name in kw["var_names"]:
            shape = (chains, draws, n) if name in ("att", "def") else (chains, draws)
            data[name] = (("chain", "draw") + (("t",) if len(shape) == 3 else ()),
                          1.0 + rng.normal(0, 0.1, shape))
        if "c_att" in data:
            data["c_att"] = (("chain", "draw"), np.full((chains, draws), 1.25))
        stats = xr.Dataset({"diverging": (("chain", "draw"), np.zeros((chains, draws), bool))})
        return xr.DataTree.from_dict({"posterior": xr.Dataset(data), "sample_stats": stats})
    return sample


def run_fit(monkeypatch, mode):
    seen = {}
    summary_names = []
    real_summary = bayes_dc.az.summary

    def summary(idata, var_names=None, **kw):
        summary_names.append(list(var_names))
        return real_summary(idata, var_names=var_names, **kw)
    monkeypatch.setattr(bayes_dc.pm, "sample", fake_sample(seen))
    monkeypatch.setattr(bayes_dc.az, "summary", summary)
    post = bayes_dc.fit(frame(), AS_OF, TEAMS, params=bayes_dc.BayesParams(xg_mode=mode))
    return post, seen["var_names"], summary_names[0]


def test_joint_fit_saves_xg_link_and_keeps_the_gate_on_the_old_list(monkeypatch):
    post, sampled, gated = run_fit(monkeypatch, "joint")
    base = ["mu", "home", "rho", "att", "def", "sigma_att", "sigma_def"]
    assert gated == base
    assert sampled == [*base, "mu_x", "home_x", "c_att", "c_def"]
    for name in ("xg_mu_x", "xg_home_x", "xg_c_att", "xg_c_def"):
        assert isinstance(post.diagnostics[name], float)
    assert post.diagnostics["xg_c_att"] == pytest.approx(1.25)


@pytest.mark.parametrize("mode", ["none", "blend"])
def test_other_modes_sample_and_log_nothing_extra(monkeypatch, mode):
    post, sampled, gated = run_fit(monkeypatch, mode)
    assert sampled == gated
    assert not [k for k in post.diagnostics if k.startswith("xg_")]
