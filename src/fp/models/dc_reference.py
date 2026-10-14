"""Reference Dixon-Coles model, adapted from MLGonzo/football_stats (dixon_coles.py).

The reference fits, per match,
    home goals ~ Poisson(lam), lam = exp(attack[home] + defence[away] + home_adv)
    away goals ~ Poisson(mu),  mu  = exp(attack[away] + defence[home])
with the Dixon-Coles low-score correction (rho) and match weights exp(-xi * time_diff),
time_diff in days before the most recent training match. Unlike the project's own
`dc_mle_v0` (fp.models.dixon_coles) it has no ridge penalty and no promoted-club
priors. It is kept as a separate predictor for comparison (Lang's request, 14 Oct
2026); it is not part of the daily run.

Changes from the reference, each deliberate:
- The identifiability constraint is sum(attack) = number of teams, for the actual
  team count; the reference hard-codes 20 teams (`sum(x[:20]) - 20`), which mixes in
  defence parameters or misses teams when a training window holds more or fewer.
- Deterministic starting values from the data (the reference starts at random values
  and a home advantage of 1.0).
- rho is bounded so the low-score correction stays positive, and the likelihood is
  computed in logs (Poisson log-pmf), vectorised, with an exact gradient.
- A failed optimisation raises DCReferenceFitError; its parameters are never used.
- Unseen teams raise UnseenTeamError instead of a bare KeyError, and a score matrix
  with a negative cell raises InvalidForecastError instead of being used.
- The score grid stops at 10 goals; the omitted mass is reported and spread back.
- No betting helpers: the reference imports bettools.py for Kelly staking, which
  this project does not use.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import poisson

from fp.models import dixon_coles as dc

MAX_GOALS = 10
MAX_OMITTED = 0.01  # more mass than this beyond 10 goals means absurd rates, not a forecast
RHO_BOUNDS = (-0.2, 0.2)
TAU_FLOOR = 1e-10
WINDOW_DAYS = 1100  # same history window as dc_mle_v0
REFERENCE_COLUMNS = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "time_diff"]


class DCReferenceFitError(RuntimeError):
    """The optimiser did not converge; the parameters must not be used."""


class UnseenTeamError(KeyError):
    """A team with no match in the training data cannot be rated by this model."""


class InvalidForecastError(ValueError):
    """The low-score correction turned a probability negative (extreme rates and rho,
    possible after very little data). The reference would pass it on silently."""


def to_reference_frame(matches: pd.DataFrame, as_of: pd.Timestamp,
                       window_days: int | None = WINDOW_DAYS) -> pd.DataFrame:
    """The project's match rows known at `as_of`, in the reference's schema.

    Needs home_id, away_id, home_goals, away_goals, kickoff_utc and
    result_available_utc. Only results known at `as_of` are kept (the same rule as
    fp.validate.leakage.known_as_of), so nothing from the future enters training.
    Rows without both goal counts are dropped. time_diff is in days before the most
    recent training match, as the reference expects.
    """
    need = ["home_id", "away_id", "home_goals", "away_goals", "kickoff_utc",
            "result_available_utc"]
    missing = [c for c in need if c not in matches]
    if missing:
        raise ValueError(f"match table lacks {missing}")
    known = matches[matches["result_available_utc"] <= as_of]
    known = known.dropna(subset=["home_goals", "away_goals"])
    if window_days is not None:
        known = known[known["kickoff_utc"] >= as_of - pd.Timedelta(days=window_days)]
    if known.empty:
        return pd.DataFrame(columns=REFERENCE_COLUMNS)
    latest = known["kickoff_utc"].max()
    return pd.DataFrame({
        "HomeTeam": known["home_id"].astype(str).to_numpy(),
        "AwayTeam": known["away_id"].astype(str).to_numpy(),
        "FTHG": known["home_goals"].astype(int).to_numpy(),
        "FTAG": known["away_goals"].astype(int).to_numpy(),
        "time_diff": ((latest - known["kickoff_utc"]).dt.total_seconds() / 86400).to_numpy(),
    })


@dataclass
class RefFit:
    teams: list[str]
    attack: dict[str, float]
    defence: dict[str, float]
    rho: float
    home_adv: float
    xi: float
    n_matches: int
    iterations: int

    def rates(self, home: str, away: str) -> tuple[float, float]:
        for team in (home, away):
            if team not in self.attack:
                raise UnseenTeamError(team)
        lam = np.exp(self.attack[home] + self.defence[away] + self.home_adv)
        mu = np.exp(self.attack[away] + self.defence[home])
        return float(lam), float(mu)

    def score_matrix(self, home: str, away: str) -> tuple[np.ndarray, float]:
        """(matrix, omitted): P(home i, away j) for 0..10 goals, rescaled to sum to 1,
        and the probability that fell outside the grid before rescaling.
        Rows are home goals, columns away goals."""
        lam, mu = self.rates(home, away)
        g = np.arange(MAX_GOALS + 1)
        m = np.outer(np.exp(poisson.logpmf(g, lam)), np.exp(poisson.logpmf(g, mu)))
        m[0, 0] *= 1 - lam * mu * self.rho
        m[0, 1] *= 1 + lam * self.rho
        m[1, 0] *= 1 + mu * self.rho
        m[1, 1] *= 1 - self.rho
        if not np.isfinite(m).all() or (m < 0).any():
            raise InvalidForecastError(f"invalid score matrix for {home} v {away}")
        total = float(m.sum())
        if total < 1 - MAX_OMITTED:
            raise InvalidForecastError(f"{1 - total:.1%} of the probability lies beyond "
                                       f"{MAX_GOALS} goals for {home} v {away}")
        return m / total, 1.0 - total

    def predict(self, home: str, away: str) -> dict:
        """Home, draw, away and the goals markets, in the project's format."""
        matrix, omitted = self.score_matrix(home, away)
        out = dc.markets(matrix)
        out["omitted_mass"] = omitted
        return out


def _negloglik(theta, hi, ai, x, y, w, n, const):
    a, d = theta[:n], theta[n:2 * n]
    rho, home = theta[-2], theta[-1]
    eta_h = a[hi] + d[ai] + home
    eta_a = a[ai] + d[hi]
    lam, mu = np.exp(eta_h), np.exp(eta_a)
    t, dth, dta, dtr = dc.tau(x, y, lam, mu, rho)
    ok = t > TAU_FLOOR
    t_safe = np.where(ok, t, TAU_FLOOR)
    ll = np.log(t_safe) + x * eta_h - lam + y * eta_a - mu - const
    g_h = w * (x - lam + np.where(ok, dth / t_safe, 0.0))
    g_a = w * (y - mu + np.where(ok, dta / t_safe, 0.0))
    grad = np.empty_like(theta)
    grad[:n] = -(np.bincount(hi, g_h, n) + np.bincount(ai, g_a, n))
    grad[n:2 * n] = -(np.bincount(ai, g_h, n) + np.bincount(hi, g_a, n))
    grad[-2] = -np.sum(w * np.where(ok, dtr / t_safe, 0.0))
    grad[-1] = -g_h.sum()
    return -np.sum(w * ll), grad


def fit(frame: pd.DataFrame, xi: float = 0.0018, maxiter: int = 1000) -> RefFit:
    """Weighted maximum likelihood with sum(attack) = number of teams."""
    missing = [c for c in REFERENCE_COLUMNS if c not in frame]
    if missing:
        raise ValueError(f"reference frame lacks {missing}")
    if frame[REFERENCE_COLUMNS].isna().any().any():
        raise ValueError("reference frame has missing values")
    if len(frame) == 0:
        raise DCReferenceFitError("no training matches")
    teams = sorted(set(frame["HomeTeam"]) | set(frame["AwayTeam"]))
    n = len(teams)
    index = {t: i for i, t in enumerate(teams)}
    hi = frame["HomeTeam"].map(index).to_numpy()
    ai = frame["AwayTeam"].map(index).to_numpy()
    x = frame["FTHG"].to_numpy(dtype=float)
    y = frame["FTAG"].to_numpy(dtype=float)
    w = np.exp(-xi * frame["time_diff"].to_numpy(dtype=float))
    const = gammaln(x + 1) + gammaln(y + 1)  # makes the value a true log-likelihood
    goals = max((x.mean() + y.mean()) / 2, 0.1)
    # Attack 1 for everyone satisfies the constraint; defence then matches the
    # average scoring rate; rho starts at 0 and home advantage at a modest 0.2.
    theta0 = np.concatenate([np.ones(n), np.full(n, np.log(goals) - 1.0), [0.0, 0.2]])
    a_row = np.concatenate([np.ones(n), np.zeros(n + 2)])
    constraint = {"type": "eq", "fun": lambda th: th[:n].sum() - n, "jac": lambda th: a_row}
    bounds = [(None, None)] * (2 * n) + [RHO_BOUNDS, (None, None)]
    result = minimize(_negloglik, theta0, args=(hi, ai, x, y, w, n, const), jac=True,
                      method="SLSQP", bounds=bounds, constraints=[constraint],
                      options={"maxiter": maxiter, "ftol": 1e-10})
    theta = result.x
    if not result.success or not np.isfinite(theta).all():
        raise DCReferenceFitError(f"optimiser failed after {result.nit} iterations: "
                                  f"{result.message}")
    if abs(theta[:n].sum() - n) > 1e-6:
        raise DCReferenceFitError("attack constraint not met")
    return RefFit(teams=teams, attack=dict(zip(teams, theta[:n].tolist(), strict=True)),
                  defence=dict(zip(teams, theta[n:2 * n].tolist(), strict=True)),
                  rho=float(theta[-2]), home_adv=float(theta[-1]), xi=xi,
                  n_matches=len(frame), iterations=int(result.nit))


def blend(p_existing: np.ndarray, p_ref: np.ndarray, weight: float) -> np.ndarray:
    """weight * existing + (1 - weight) * reference, rows of (home, draw, away).

    Both inputs must be valid probabilities; where the reference is missing (an
    unseen team), the existing forecast is used unchanged.
    """
    p_existing = np.asarray(p_existing, dtype=float)
    p_ref = np.asarray(p_ref, dtype=float)
    for name, p in (("existing", p_existing), ("reference", p_ref)):
        rows = p[~np.isnan(p).any(axis=1)]
        if (rows < 0).any() or not np.allclose(rows.sum(axis=1), 1, atol=1e-6):
            raise ValueError(f"{name} probabilities are not valid")
    if np.isnan(p_existing).any():
        raise ValueError("existing probabilities have gaps")
    out = np.where(np.isnan(p_ref).any(axis=1, keepdims=True), p_existing,
                   weight * p_existing + (1 - weight) * p_ref)
    if not (np.isfinite(out).all() and (out >= 0).all() and np.allclose(out.sum(1), 1)):
        raise ValueError("blended probabilities are not valid")
    return out


def main(argv: list[str] | None = None) -> int:
    """Try the predictor: `python -m fp.models.dc_reference EPL arsenal chelsea`.

    Fits on the league's results known now (data/processed/matches.parquet) and prints
    home, draw, away next to nothing else: it is a comparison tool, not a published
    forecast (reports/dc_reference_2026_10.md).
    """
    import argparse
    import sys

    from fp.ingest.matches import processed_dir

    ap = argparse.ArgumentParser()
    ap.add_argument("league")
    ap.add_argument("home_id")
    ap.add_argument("away_id")
    ap.add_argument("--xi", type=float, default=0.0018)
    args = ap.parse_args(argv)
    matches = pd.read_parquet(processed_dir(args.league) / "matches.parquet")
    lg = matches[matches["league"] == args.league]
    now = pd.Timestamp.now(tz="UTC")
    try:
        out = fit(to_reference_frame(lg, now), xi=args.xi).predict(args.home_id, args.away_id)
    except (UnseenTeamError, InvalidForecastError, DCReferenceFitError) as error:
        print(f"no forecast: {error}", file=sys.stderr)
        return 1
    print(f"{args.home_id} v {args.away_id}: home {out['p_home']:.3f}, draw {out['p_draw']:.3f}, "
          f"away {out['p_away']:.3f} (dc_ref, xi {args.xi})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
