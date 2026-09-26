"""Bayesian hierarchical Dixon-Coles (spec S5.1, Phase 2).

Goals, per match:
    home goals ~ Poisson(lam),  log lam = mu + home + att[home] + def[away]
    away goals ~ Poisson(nu),   log nu  = mu + att[away] + def[home]
    Dixon-Coles correction tau(rho) on 0-0, 1-0, 0-1, 1-1.

Hierarchy: att[k] ~ Normal(0, sigma_att) and def[k] ~ Normal(0, sigma_def), with
sigma_att and sigma_def learned from the data. The data decide how much to shrink.
Promoted clubs instead get Normal(mean, sd) from their second-tier season
(fp.models.promotion).

Optional shots-on-target layer (decision D1): shots on target follow
Poisson(exp(mu_s + home_s + b_att * att[shooter] + b_def * def[opponent])). They
share the same att and def, so they act as a second, less noisy reading of
team strength.

Time decay: each match's log-likelihood is multiplied by exp(-xi * age in days).
This is a tempered likelihood, not a generative model, so intervals are checked
for coverage in the backtest (PRD item 21).

Every refit starts from these fixed priors on all data in the window. Yesterday's
posterior is never used as today's prior, so no match is counted twice (PRD item 5).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt
from scipy.stats import poisson

MAX_GOALS = 10
DIAG_RHAT = 1.01
DIAG_ESS = 400


@dataclass
class BayesParams:
    xi: float = 0.002
    window_days: int = 1100
    use_sot: bool = False
    dynamic: bool = False     # random-walk challenger: strengths drift month by month
    centred: bool = True      # parameterisation; see build_model
    period_days: int = 30
    draws: int = 1000
    tune: int = 1000
    chains: int = 4
    target_accept: float = 0.9
    sampler: str = "nutpie"   # "nutpie" or "numpyro"; benchmarked in Phase 2
    seed: int = 2026


@dataclass
class Posterior:
    teams: list[str]
    mu: np.ndarray            # (S,)
    home: np.ndarray          # (S,)
    rho: np.ndarray           # (S,)
    att: np.ndarray           # (S, n_teams)
    def_: np.ndarray          # (S, n_teams)
    diagnostics: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        d = self.diagnostics
        return (d.get("rhat_max", 9) < DIAG_RHAT and d.get("ess_bulk_min", 0) > DIAG_ESS
                and d.get("divergences", 1) == 0)

    def index(self, team: str) -> int:
        return self.teams.index(team)

    def rates(self, home_id: str, away_id: str) -> tuple[np.ndarray, np.ndarray]:
        h, a = self.index(home_id), self.index(away_id)
        lam = np.exp(self.mu + self.home + self.att[:, h] + self.def_[:, a])
        nu = np.exp(self.mu + self.att[:, a] + self.def_[:, h])
        return lam, nu

    def score_matrices(self, home_id: str, away_id: str,
                       scale: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
        """One scoreline matrix per posterior draw: shape (S, 11, 11). `scale`
        multiplies the home and away scoring rates (team news, fp.news.impact)."""
        lam, nu = self.rates(home_id, away_id)
        lam, nu = lam * scale[0], nu * scale[1]
        g = np.arange(MAX_GOALS + 1)
        m = poisson.pmf(g[None, :], lam[:, None])[:, :, None] * \
            poisson.pmf(g[None, :], nu[:, None])[:, None, :]
        rho = self.rho
        m[:, 0, 0] *= 1 - lam * nu * rho
        m[:, 0, 1] *= 1 + lam * rho
        m[:, 1, 0] *= 1 + nu * rho
        m[:, 1, 1] *= 1 - rho
        m = np.clip(m, 0, None)
        return m / m.sum(axis=(1, 2), keepdims=True)


def _market_draws(mats: np.ndarray) -> dict[str, np.ndarray]:
    g = np.arange(MAX_GOALS + 1)
    total = g[:, None] + g[None, :]
    home = np.tril(np.ones((len(g), len(g))), -1).astype(bool)
    return {
        "p_home": mats[:, home].sum(axis=1),
        "p_draw": np.trace(mats, axis1=1, axis2=2),
        "p_away": mats[:, home.T].sum(axis=1),
        "p_over_1_5": mats[:, total > 1.5].sum(axis=1),
        "p_over_2_5": mats[:, total > 2.5].sum(axis=1),
        "p_over_3_5": mats[:, total > 3.5].sum(axis=1),
        "p_btts": mats[:, 1:, 1:].sum(axis=(1, 2)),
        "exp_goals_home": (mats.sum(axis=2) * g).sum(axis=1),
        "exp_goals_away": (mats.sum(axis=1) * g).sum(axis=1),
    }


def markets(post: Posterior, home_id: str, away_id: str, top_n: int = 5,
            scale: tuple[float, float] = (1.0, 1.0)) -> dict:
    """Posterior predictive markets plus 80% intervals.

    The point forecast averages the scoreline matrix over draws: the posterior
    predictive. Intervals are the 10th and 90th percentiles across draws.
    """
    mats = post.score_matrices(home_id, away_id, scale)
    mean = mats.mean(axis=0)
    per_draw = _market_draws(mats)
    point: dict = {k: float(v[0]) for k, v in _market_draws(mean[None]).items()}
    order = np.argsort(mean, axis=None)[::-1][:top_n]
    point["top_scorelines"] = [
        {"score": f"{i}-{j}", "p": round(float(mean[i, j]), 4)}
        for i, j in zip(*np.unravel_index(order, mean.shape), strict=True)
    ]
    point["matrix"] = mean  # posterior predictive scoreline table, rows = home goals
    point["intervals"] = {
        k: [round(float(np.percentile(v, 10)), 4), round(float(np.percentile(v, 90)), 4)]
        for k, v in per_draw.items() if k.startswith("p_")
    }
    return point


def _arrays(train: pd.DataFrame, teams: list[str], as_of: pd.Timestamp, p: BayesParams):
    idx = {t: i for i, t in enumerate(teams)}
    age = (as_of - train["kickoff_utc"]).dt.total_seconds().to_numpy() / 86400
    x = train["home_goals"].to_numpy(dtype=float)
    y = train["away_goals"].to_numpy(dtype=float)
    return {
        "hi": train["home_id"].map(idx).to_numpy(), "ai": train["away_id"].map(idx).to_numpy(),
        "x": x, "y": y, "w": np.exp(-p.xi * age),
        "m00": ((x == 0) & (y == 0)).astype(float), "m01": ((x == 0) & (y == 1)).astype(float),
        "m10": ((x == 1) & (y == 0)).astype(float), "m11": ((x == 1) & (y == 1)).astype(float),
        "xs": _column(train, "home_sot"), "ys": _column(train, "away_sot"),
    }


def _column(frame: pd.DataFrame, name: str) -> np.ndarray:
    """A numeric column, or zeros when absent (it is then unused)."""
    if name in frame:
        return frame[name].to_numpy(dtype=float)
    return np.zeros(len(frame))


def build_model(d: dict, n: int, prior_mean_att: np.ndarray, prior_sd_att: np.ndarray,
                prior_mean_def: np.ndarray, prior_sd_def: np.ndarray, promoted: np.ndarray,
                use_sot: bool, centred: bool = True) -> pm.Model:
    with pm.Model() as model:
        mu = pm.Normal("mu", 0.2, 0.5)
        home = pm.Normal("home", 0.25, 0.25)
        rho = pm.TruncatedNormal("rho", 0.0, 0.1, lower=-0.2, upper=0.2)
        sigma_att = pm.HalfNormal("sigma_att", 0.5)
        sigma_def = pm.HalfNormal("sigma_def", 0.5)
        # Two ways to write the same model. Centred (att ~ Normal(mean, sd)) samples
        # best when clubs have lots of data relative to the spread sigma; non-centred
        # (att = mean + sd * z) samples best when sigma is small. EPL attack suits the
        # first, La Liga defence the second, so fit_checked tries both.
        sd_att = pt.where(promoted, prior_sd_att, sigma_att)
        sd_def = pt.where(promoted, prior_sd_def, sigma_def)
        if centred:
            att_raw = pm.Normal("att_raw", prior_mean_att, sd_att, shape=n)
            def_raw = pm.Normal("def_raw", prior_mean_def, sd_def, shape=n)
        else:
            att_raw = prior_mean_att + sd_att * pm.Normal("z_att", 0, 1, shape=n)
            def_raw = prior_mean_def + sd_def * pm.Normal("z_def", 0, 1, shape=n)
        # Centre so each sums to zero. Otherwise mu and the average attack can trade
        # off against each other, and the sampler drifts along that ridge.
        att = pm.Deterministic("att", att_raw - pt.mean(att_raw))
        dfn = pm.Deterministic("def", def_raw - pt.mean(def_raw))

        eta_h = mu + home + att[d["hi"]] + dfn[d["ai"]]
        eta_a = mu + att[d["ai"]] + dfn[d["hi"]]
        lam, nu = pt.exp(eta_h), pt.exp(eta_a)
        tau = (1 - d["m00"] * lam * nu * rho + d["m01"] * lam * rho
               + d["m10"] * nu * rho - d["m11"] * rho)
        ll = (pt.log(pt.maximum(tau, 1e-10)) + d["x"] * eta_h - lam + d["y"] * eta_a - nu)
        pm.Potential("goals", pt.sum(d["w"] * ll))

        if use_sot:
            mu_s = pm.Normal("mu_s", 1.4, 0.5)
            home_s = pm.Normal("home_s", 0.1, 0.2)
            b_att = pm.Normal("b_att", 1.0, 0.5)
            b_def = pm.Normal("b_def", 1.0, 0.5)
            es_h = mu_s + home_s + b_att * att[d["hi"]] + b_def * dfn[d["ai"]]
            es_a = mu_s + b_att * att[d["ai"]] + b_def * dfn[d["hi"]]
            ll_s = d["xs"] * es_h - pt.exp(es_h) + d["ys"] * es_a - pt.exp(es_a)
            pm.Potential("shots_on_target", pt.sum(d["w"] * ll_s))
    return model


def fit(train: pd.DataFrame, as_of: pd.Timestamp, teams: list[str],
        promoted_priors: dict[str, tuple[float, float, float, float]] | None = None,
        params: BayesParams | None = None) -> Posterior:
    """Sample the posterior from matches in `train` (already filtered to as_of).

    teams: clubs that must be rated, such as this season's twenty, even with no
    match in the window yet. Every club in the window is rated as well.
    promoted_priors: team -> (mean att, sd att, mean def, sd def).
    """
    p = params or BayesParams()
    promoted_priors = promoted_priors or {}
    age = (as_of - train["kickoff_utc"]).dt.total_seconds() / 86400
    train = train[age <= p.window_days]
    if p.use_sot:
        train = train.dropna(subset=["home_sot", "away_sot"])
    teams = sorted(set(teams) | set(train["home_id"]) | set(train["away_id"]))
    d = _arrays(train, teams, as_of, p)
    n = len(teams)
    is_prom = np.array([t in promoted_priors for t in teams])
    pri = np.array([promoted_priors.get(t, (0.0, 1.0, 0.0, 1.0)) for t in teams])
    if p.dynamic:
        age = (as_of - train["kickoff_utc"]).dt.total_seconds().to_numpy() / 86400
        n_periods = int(p.window_days // p.period_days) + 1
        d["period"] = (n_periods - 1 - (age // p.period_days)).astype(int)
        model = build_dynamic_model(d, n, n_periods, pri[:, 0], pri[:, 1], pri[:, 2],
                                    pri[:, 3], is_prom)
        var_names = ["mu", "home", "rho", "att", "def", "sigma_att", "sigma_def", "tau_att",
                     "tau_def"]
    else:
        model = build_model(d, n, pri[:, 0], pri[:, 1], pri[:, 2], pri[:, 3], is_prom,
                            p.use_sot, p.centred)
        var_names = ["mu", "home", "rho", "att", "def", "sigma_att", "sigma_def"]

    start = time.time()
    with model:
        idata = pm.sample(
            draws=p.draws, tune=p.tune, chains=p.chains, target_accept=p.target_accept,
            nuts_sampler=p.sampler, random_seed=p.seed, progressbar=False,
            var_names=var_names,
        )
    seconds = time.time() - start
    summ = az.summary(idata, var_names=var_names, kind="diagnostics")
    # ArviZ 1 returns a DataTree; .to_dataset() gives the plain xarray Dataset.
    diverging = idata["sample_stats"].to_dataset().get("diverging")
    diag = {
        "rhat_max": float(summ["r_hat"].max()),
        "ess_bulk_min": float(summ["ess_bulk"].min()),
        "divergences": int(diverging.sum()) if diverging is not None else 0,
        "n_matches": len(train),
    }
    post = idata["posterior"].to_dataset().stack(sample=("chain", "draw"))
    return Posterior(
        teams=teams,
        mu=post["mu"].to_numpy(), home=post["home"].to_numpy(), rho=post["rho"].to_numpy(),
        att=post["att"].to_numpy().T, def_=post["def"].to_numpy().T,
        diagnostics=diag, seconds=seconds,
    )


def fit_checked(train: pd.DataFrame, as_of: pd.Timestamp, teams: list[str],
                promoted_priors: dict[str, tuple[float, float, float, float]] | None = None,
                params: BayesParams | None = None) -> Posterior:
    """Fit, and if diagnostics fail, retry once in the other parameterisation with
    twice the draws and a new seed. Same model, same posterior; only the sampler's
    path differs. The caller must still check .ok: a second failure means fall back."""
    p = params or BayesParams()
    post = fit(train, as_of, teams, promoted_priors, p)
    if post.ok:
        return post
    retry = BayesParams(**{**p.__dict__, "centred": not p.centred, "draws": 2 * p.draws,
                           "seed": p.seed + 1})
    second = fit(train, as_of, teams, promoted_priors, retry)
    second.diagnostics["retried"] = True
    second.seconds += post.seconds
    return second


def build_dynamic_model(d: dict, n: int, n_periods: int, prior_mean_att: np.ndarray,
                        prior_sd_att: np.ndarray, prior_mean_def: np.ndarray,
                        prior_sd_def: np.ndarray, promoted: np.ndarray) -> pm.Model:
    """Random-walk challenger (spec S5.1): no time-decay weights.

    att[period, club] = att[period - 1, club] + tau_att * noise, and the same for
    defence. The step size tau is learned. This is a true generative model, so its
    intervals need no tempering caveat.
    """
    with pm.Model() as model:
        mu = pm.Normal("mu", 0.2, 0.5)
        home = pm.Normal("home", 0.25, 0.25)
        rho = pm.TruncatedNormal("rho", 0.0, 0.1, lower=-0.2, upper=0.2)
        sigma_att = pm.HalfNormal("sigma_att", 0.5)
        sigma_def = pm.HalfNormal("sigma_def", 0.5)
        tau_att = pm.HalfNormal("tau_att", 0.05)
        tau_def = pm.HalfNormal("tau_def", 0.05)
        z0_att = pm.Normal("z0_att", 0, 1, shape=n)
        z0_def = pm.Normal("z0_def", 0, 1, shape=n)
        steps_att = pm.Normal("steps_att", 0, 1, shape=(n_periods - 1, n))
        steps_def = pm.Normal("steps_def", 0, 1, shape=(n_periods - 1, n))
        start_att = prior_mean_att + pt.where(promoted, prior_sd_att, sigma_att) * z0_att
        start_def = prior_mean_def + pt.where(promoted, prior_sd_def, sigma_def) * z0_def
        walk_att = pt.concatenate([start_att[None, :], start_att[None, :]
                                   + tau_att * pt.cumsum(steps_att, axis=0)], axis=0)
        walk_def = pt.concatenate([start_def[None, :], start_def[None, :]
                                   + tau_def * pt.cumsum(steps_def, axis=0)], axis=0)
        att = walk_att - pt.mean(walk_att, axis=1, keepdims=True)
        dfn = walk_def - pt.mean(walk_def, axis=1, keepdims=True)
        pm.Deterministic("att", att[-1])
        pm.Deterministic("def", dfn[-1])

        per = d["period"]
        eta_h = mu + home + att[per, d["hi"]] + dfn[per, d["ai"]]
        eta_a = mu + att[per, d["ai"]] + dfn[per, d["hi"]]
        lam, nu = pt.exp(eta_h), pt.exp(eta_a)
        tau = (1 - d["m00"] * lam * nu * rho + d["m01"] * lam * rho
               + d["m10"] * nu * rho - d["m11"] * rho)
        ll = (pt.log(pt.maximum(tau, 1e-10)) + d["x"] * eta_h - lam + d["y"] * eta_a - nu)
        pm.Potential("goals", pt.sum(ll))
    return model
