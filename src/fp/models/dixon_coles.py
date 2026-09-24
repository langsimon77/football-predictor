"""Dixon-Coles goals model, fitted by weighted maximum likelihood (Phase 1F).

Model, per match:
    home goals ~ Poisson(lam),  lam = exp(mu + home_adv + attack[home] + defence[away])
    away goals ~ Poisson(nu),   nu  = exp(mu + attack[away] + defence[home])
A correction tau adjusts the four low scores 0-0, 1-0, 0-1, 1-1 through rho.

Each past match gets weight exp(-xi * days before as_of), so recent form counts
more. A ridge penalty pulls each team towards a prior mean: zero (league average)
for most teams, and a lower "promoted team" level for newly promoted clubs.
This is the fast stand-in for the Bayesian model of Phase 2, whose hierarchical
priors do the same job more carefully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_GOALS = 10
TAU_FLOOR = 1e-10
RHO_BOUNDS = (-0.25, 0.25)


@dataclass
class DCParams:
    # Defaults tuned on 2021/22 and 2022/23 (reports/backtest_1f.md).
    xi: float = 0.002          # time decay per day; half-life = ln 2 / xi = 347 days
    ridge: float = 10.0        # prior precision on attack and defence (log scale)
    window_days: int = 1100    # ignore matches older than about three seasons


@dataclass
class DCFit:
    teams: list[str]
    mu: float
    home_adv: float
    rho: float
    attack: dict[str, float]
    defence: dict[str, float]
    n_matches: int
    converged: bool
    params: DCParams = field(default_factory=DCParams)

    def rates(self, home_id: str, away_id: str) -> tuple[float, float]:
        lam = np.exp(self.mu + self.home_adv + self.attack[home_id] + self.defence[away_id])
        nu = np.exp(self.mu + self.attack[away_id] + self.defence[home_id])
        return float(lam), float(nu)

    def score_matrix(self, home_id: str, away_id: str) -> np.ndarray:
        return score_matrix(*self.rates(home_id, away_id), self.rho)


def tau(x: np.ndarray, y: np.ndarray, lam: np.ndarray, nu: np.ndarray, rho: float):
    """Dixon-Coles low-score correction and its derivatives.

    Returns tau and d tau / d eta_home, d eta_away, d rho, where eta = log rate.
    """
    t = np.ones_like(lam)
    dh = np.zeros_like(lam)
    da = np.zeros_like(lam)
    dr = np.zeros_like(lam)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    ln = lam * nu
    t[m00] = 1 - ln[m00] * rho
    dh[m00] = da[m00] = -ln[m00] * rho
    dr[m00] = -ln[m00]
    t[m01] = 1 + lam[m01] * rho
    dh[m01] = lam[m01] * rho
    dr[m01] = lam[m01]
    t[m10] = 1 + nu[m10] * rho
    da[m10] = nu[m10] * rho
    dr[m10] = nu[m10]
    t[m11] = 1 - rho
    dr[m11] = -1.0
    return t, dh, da, dr


def _objective(theta, hi, ai, x, y, w, n, ridge, prior_a, prior_d):
    mu, home, rho = theta[0], theta[1], theta[2]
    a, d = theta[3 : 3 + n], theta[3 + n :]
    eta_h = mu + home + a[hi] + d[ai]
    eta_a = mu + a[ai] + d[hi]
    lam, nu = np.exp(eta_h), np.exp(eta_a)

    t, dth, dta, dtr = tau(x, y, lam, nu, rho)
    ok = t > TAU_FLOOR
    t_safe = np.where(ok, t, TAU_FLOOR)
    ll = np.log(t_safe) + x * eta_h - lam + y * eta_a - nu
    penalty = 0.5 * ridge * (np.sum((a - prior_a) ** 2) + np.sum((d - prior_d) ** 2))
    nll = -np.sum(w * ll) + penalty

    g_h = w * (x - lam + np.where(ok, dth / t_safe, 0.0))
    g_a = w * (y - nu + np.where(ok, dta / t_safe, 0.0))
    g_r = np.sum(w * np.where(ok, dtr / t_safe, 0.0))
    grad = np.empty_like(theta)
    grad[0] = -(g_h.sum() + g_a.sum())
    grad[1] = -g_h.sum()
    grad[2] = -g_r
    grad[3 : 3 + n] = -(np.bincount(hi, g_h, n) + np.bincount(ai, g_a, n)) + ridge * (a - prior_a)
    grad[3 + n :] = -(np.bincount(ai, g_h, n) + np.bincount(hi, g_a, n)) + ridge * (d - prior_d)
    return nll, grad


def fit(
    train: pd.DataFrame,
    as_of: pd.Timestamp,
    params: DCParams | None = None,
    prior_means: dict[str, tuple[float, float]] | None = None,
    extra_teams: list[str] | tuple[str, ...] = (),
) -> DCFit:
    """Fit on matches in `train` (already filtered to what was known at as_of).

    train needs home_id, away_id, home_goals, away_goals, kickoff_utc.
    prior_means maps team_id -> (attack, defence) prior means; default (0, 0).
    extra_teams: teams to rate even if they have no match in the window
    (for example a promoted club before its first top-flight game).
    """
    params = params or DCParams()
    prior_means = prior_means or {}
    age_days = (as_of - train["kickoff_utc"]).dt.total_seconds() / 86400
    train = train[age_days <= params.window_days]
    age_days = age_days[age_days <= params.window_days]

    teams = sorted(set(train["home_id"]) | set(train["away_id"]) | set(extra_teams))
    index = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    hi = train["home_id"].map(index).to_numpy()
    ai = train["away_id"].map(index).to_numpy()
    x = train["home_goals"].to_numpy(dtype=float)
    y = train["away_goals"].to_numpy(dtype=float)
    w = np.exp(-params.xi * age_days.to_numpy())
    prior_a = np.array([prior_means.get(t, (0.0, 0.0))[0] for t in teams])
    prior_d = np.array([prior_means.get(t, (0.0, 0.0))[1] for t in teams])

    goals = (x.sum() + y.sum()) / max(2 * len(x), 1)
    theta0 = np.concatenate([[np.log(max(goals, 0.1)), 0.25, -0.05], prior_a, prior_d])
    bounds = [(None, None), (None, None), RHO_BOUNDS] + [(None, None)] * (2 * n)
    result = minimize(
        _objective, theta0, jac=True, method="L-BFGS-B", bounds=bounds,
        args=(hi, ai, x, y, w, n, params.ridge, prior_a, prior_d),
        options={"maxiter": 1000},
    )
    theta = result.x
    return DCFit(
        teams=teams,
        mu=float(theta[0]),
        home_adv=float(theta[1]),
        rho=float(theta[2]),
        attack=dict(zip(teams, theta[3 : 3 + n].tolist(), strict=True)),
        defence=dict(zip(teams, theta[3 + n :].tolist(), strict=True)),
        n_matches=len(train),
        converged=bool(result.success),
        params=params,
    )


@cache
def _goal_range() -> np.ndarray:
    return np.arange(MAX_GOALS + 1)


def score_matrix(lam: float, nu: float, rho: float) -> np.ndarray:
    """P(home scores i, away scores j) for i, j in 0..10, with the low-score correction.

    Rescaled to sum to 1: the tiny probability above 10 goals is spread back.
    """
    g = _goal_range()
    m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, nu))
    m[0, 0] *= 1 - lam * nu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + nu * rho
    m[1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    return m / m.sum()


def markets(matrix: np.ndarray, top_n: int = 5) -> dict:
    """Every goals market derived from one scoreline matrix."""
    g = _goal_range()
    total = g[:, None] + g[None, :]
    home = np.tril(matrix, -1).sum()   # home goals > away goals: below the diagonal
    draw = np.trace(matrix)
    order = np.argsort(matrix, axis=None)[::-1][:top_n]
    top = [
        {"score": f"{i}-{j}", "p": round(float(matrix[i, j]), 4)}
        for i, j in zip(*np.unravel_index(order, matrix.shape), strict=True)
    ]
    return {
        "p_home": float(home),
        "p_draw": float(draw),
        "p_away": float(1 - home - draw),
        "p_over_1_5": float(matrix[total > 1.5].sum()),
        "p_over_2_5": float(matrix[total > 2.5].sum()),
        "p_over_3_5": float(matrix[total > 3.5].sum()),
        "p_btts": float(matrix[1:, 1:].sum()),
        "exp_goals_home": float((g[:, None] * matrix).sum()),
        "exp_goals_away": float((g[None, :] * matrix).sum()),
        "top_scorelines": top,
    }
