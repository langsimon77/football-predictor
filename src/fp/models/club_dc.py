"""Dixon-Coles goals model for clubs across Europe (Champions League project, goals
markets only, approved by Lang 14 Oct 2026).

Per match:
    home goals ~ Poisson(lam), lam = exp(mu + h + A[c_home] + a[home] + D[c_away] + d[away])
    away goals ~ Poisson(nu),  nu  = exp(mu + A[c_away] + a[away] + D[c_home] + d[home])
with the Dixon-Coles low-score correction (rho). c_x is the club's country (its
league's level, A and D), a and d the club's difference from that level. h is the home
advantage: one value for domestic matches, another for European ones, none at a
neutral ground (finals). League levels are learned from European matches between
clubs of different countries; a club from a league without domestic data shares its
country's level and is rated from its European matches.

Weights exp(-xi * days before the fit) and a 1,100-day window, as the live fast model
(fp.models.dixon_coles). Ridge penalties: club differences towards 0 (precision 10,
as live); league levels towards 0 (precision 1 [A], weak, so the data set them).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from fp.models import dixon_coles as dc

XI = 0.002
WINDOW_DAYS = 1100
RIDGE_CLUB = 10.0
RIDGE_LEAGUE = 1.0
RHO_BOUNDS = (-0.25, 0.25)
TAU_FLOOR = 1e-10


@dataclass
class ClubFit:
    clubs: list[str]
    countries: list[str]
    mu: float
    home_domestic: float
    home_europe: float
    rho: float
    attack: dict[str, float]   # club total: league level + club difference
    defence: dict[str, float]
    league_attack: dict[str, float]
    league_defence: dict[str, float]
    n_matches: int
    converged: bool

    def rates(self, home: str, away: str, neutral: bool = False,
              europe: bool = True) -> tuple[float, float]:
        h = 0.0 if neutral else (self.home_europe if europe else self.home_domestic)
        lam = np.exp(self.mu + h + self.attack[home] + self.defence[away])
        nu = np.exp(self.mu + self.attack[away] + self.defence[home])
        return float(lam), float(nu)

    def markets(self, home: str, away: str, neutral: bool = False) -> dict:
        lam, nu = self.rates(home, away, neutral)
        return dc.markets(dc.score_matrix(lam, nu, self.rho))


def _objective(theta, hi, ai, hc, ac, x, y, w, home_kind, n, k):
    mu, h_dom, h_eu, rho = theta[0], theta[1], theta[2], theta[3]
    a, d = theta[4:4 + n], theta[4 + n:4 + 2 * n]
    la, ld = theta[4 + 2 * n:4 + 2 * n + k], theta[4 + 2 * n + k:]
    h = np.where(home_kind == 1, h_dom, np.where(home_kind == 2, h_eu, 0.0))
    eta_h = mu + h + la[hc] + a[hi] + ld[ac] + d[ai]
    eta_a = mu + la[ac] + a[ai] + ld[hc] + d[hi]
    lam, nu = np.exp(eta_h), np.exp(eta_a)
    t, dth, dta, dtr = dc.tau(x, y, lam, nu, rho)
    ok = t > TAU_FLOOR
    t_safe = np.where(ok, t, TAU_FLOOR)
    ll = np.log(t_safe) + x * eta_h - lam + y * eta_a - nu
    pen = 0.5 * RIDGE_CLUB * (a @ a + d @ d) + 0.5 * RIDGE_LEAGUE * (la @ la + ld @ ld)
    g_h = w * (x - lam + np.where(ok, dth / t_safe, 0.0))
    g_a = w * (y - nu + np.where(ok, dta / t_safe, 0.0))
    grad = np.empty_like(theta)
    grad[0] = -(g_h.sum() + g_a.sum())
    grad[1] = -g_h[home_kind == 1].sum()
    grad[2] = -g_h[home_kind == 2].sum()
    grad[3] = -np.sum(w * np.where(ok, dtr / t_safe, 0.0))
    grad[4:4 + n] = -(np.bincount(hi, g_h, n) + np.bincount(ai, g_a, n)) + RIDGE_CLUB * a
    grad[4 + n:4 + 2 * n] = -(np.bincount(ai, g_h, n) + np.bincount(hi, g_a, n)) + RIDGE_CLUB * d
    grad[4 + 2 * n:4 + 2 * n + k] = (-(np.bincount(hc, g_h, k) + np.bincount(ac, g_a, k))
                                     + RIDGE_LEAGUE * la)
    grad[4 + 2 * n + k:] = (-(np.bincount(ac, g_h, k) + np.bincount(hc, g_a, k))
                            + RIDGE_LEAGUE * ld)
    return -np.sum(w * ll) + pen, grad


def fit(matches: pd.DataFrame, as_of: pd.Timestamp, country_of: dict[str, str],
        extra_clubs: tuple[str, ...] = ()) -> ClubFit:
    """Fit on matches whose results were known at as_of (fp.ingest.europe columns).
    country_of maps every club ID to its country code."""
    known = matches[(matches["result_available_utc"] <= as_of)
                    & (matches["kickoff_utc"] >= as_of - pd.Timedelta(days=WINDOW_DAYS))]
    known = known.dropna(subset=["home_goals", "away_goals"])
    clubs = sorted(set(known["home_id"]) | set(known["away_id"]) | set(extra_clubs))
    countries = sorted({country_of[c] for c in clubs})
    ci = {c: i for i, c in enumerate(clubs)}
    li = {c: i for i, c in enumerate(countries)}
    hi = known["home_id"].map(ci).to_numpy()
    ai = known["away_id"].map(ci).to_numpy()
    hc = np.array([li[country_of[c]] for c in known["home_id"]], dtype=int)
    ac = np.array([li[country_of[c]] for c in known["away_id"]], dtype=int)
    x = known["home_goals"].to_numpy(dtype=float)
    y = known["away_goals"].to_numpy(dtype=float)
    age = (as_of - known["kickoff_utc"]).dt.total_seconds().to_numpy() / 86400
    w = np.exp(-XI * age)
    kind = np.where(known["neutral"].to_numpy(dtype=bool), 0,
                    np.where(known["kind"].to_numpy() == "europe", 2, 1))
    n, k = len(clubs), len(countries)
    goals = max((x.mean() + y.mean()) / 2, 0.1)
    theta0 = np.concatenate([[np.log(goals), 0.25, 0.25, -0.05], np.zeros(2 * n + 2 * k)])
    bounds = [(None, None)] * 3 + [RHO_BOUNDS] + [(None, None)] * (2 * n + 2 * k)
    res = minimize(_objective, theta0, jac=True, method="L-BFGS-B", bounds=bounds,
                   args=(hi, ai, hc, ac, x, y, w, kind, n, k), options={"maxiter": 3000})
    th = res.x
    a, d = th[4:4 + n], th[4 + n:4 + 2 * n]
    la, ld = th[4 + 2 * n:4 + 2 * n + k], th[4 + 2 * n + k:]
    att = {c: float(la[li[country_of[c]]] + a[ci[c]]) for c in clubs}
    dfn = {c: float(ld[li[country_of[c]]] + d[ci[c]]) for c in clubs}
    return ClubFit(clubs=clubs, countries=countries, mu=float(th[0]),
                   home_domestic=float(th[1]), home_europe=float(th[2]), rho=float(th[3]),
                   attack=att, defence=dfn,
                   league_attack=dict(zip(countries, la.tolist(), strict=True)),
                   league_defence=dict(zip(countries, ld.tolist(), strict=True)),
                   n_matches=len(known), converged=bool(res.success))


def countries(matches: pd.DataFrame, alias_country: dict[str, str]) -> dict[str, str]:
    """Each club's country: from the European alias table, else from its domestic league."""
    from fp.ingest.europe import EXTRA, MAIN

    league_country = {**MAIN, **EXTRA}
    out: dict[str, str] = dict(alias_country)
    # A club's domestic league wins over the country tag in the European files
    # (Monaco plays in Ligue 1 but is tagged MCO there).
    dom = matches[matches["kind"] == "domestic"]
    for col in ("home_id", "away_id"):
        out.update(dict(zip(dom[col], dom["competition"].map(league_country), strict=True)))
    return out
