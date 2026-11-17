"""Basketball B6: range widths that adapt
(data/audit/preregistration_basketball_b6_width_2026_11.md).

W0: fixed bell curve (B1). W1: bell curve, width = SD of the model's own errors over the last
N games of the league, earlier days only. W2: Student-t with the W1 width, matched on variance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

MIN_ERRORS = 60  # pre-registration, section 2


@dataclass(frozen=True)
class Width:
    method: str          # "W0", "W1" or "W2"
    window: int = 0      # N, rolling games (W1, W2)
    df: float = 0.0      # Student-t degrees of freedom (W2)

    def label(self) -> str:
        if self.method == "W0":
            return "W0"
        if self.method == "W1":
            return f"W1 N={self.window}"
        return f"W2 N={self.window} df={self.df:g}"


GRID = ([Width("W0")]
        + [Width("W1", n) for n in (100, 200, 400)]
        + [Width("W2", n, df) for n in (100, 200, 400) for df in (5, 10, 30)])


def rolling_sd(errors: np.ndarray, day: np.ndarray, window: int, start_sd: float,
               min_errors: int = MIN_ERRORS) -> np.ndarray:
    """For each game, the SD (root mean square) of the last `window` errors from strictly
    earlier days; `start_sd` until `min_errors` such errors exist. `day` must be sorted."""
    errors = np.asarray(errors, float)
    day = np.asarray(day)
    out = np.full(len(errors), float(start_sd))
    # first index of each game's day: errors before it are from earlier days
    first = np.searchsorted(day, day, side="left")
    ok = ~np.isnan(errors)
    cum_idx = np.cumsum(ok)  # number of known errors up to and including i
    known = np.flatnonzero(ok)
    sq = errors[known] ** 2
    csq = np.concatenate([[0.0], np.cumsum(sq)])
    for i in range(len(errors)):
        n_before = cum_idx[first[i] - 1] if first[i] > 0 else 0
        if n_before < min_errors:
            continue
        lo = max(0, n_before - window)
        out[i] = np.sqrt((csq[n_before] - csq[lo]) / (n_before - lo))
    return out


def _scale(sd: np.ndarray, df: float) -> np.ndarray:
    return sd * np.sqrt((df - 2) / df)


def crps(x, mu, sd, w: Width) -> np.ndarray:
    x, mu, sd = (np.asarray(a, float) for a in np.broadcast_arrays(x, mu, sd))
    if w.method in ("W0", "W1"):
        z = (x - mu) / sd
        return sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
    nu = w.df
    s = _scale(sd, nu)
    z = (x - mu) / s
    # closed form CRPS of the Student-t (Gneiting and Raftery 2007; Jordan et al. 2019)
    from scipy.special import beta
    b = beta(0.5, nu - 0.5) / beta(0.5, nu / 2) ** 2
    term = (z * (2 * stats.t.cdf(z, nu) - 1)
            + 2 * stats.t.pdf(z, nu) * (nu + z**2) / (nu - 1)
            - 2 * np.sqrt(nu) * b / (nu - 1))
    return s * term


def inside_90(x, mu, sd, w: Width) -> np.ndarray:
    x, mu, sd = (np.asarray(a, float) for a in np.broadcast_arrays(x, mu, sd))
    if w.method == "W2":
        half = stats.t.ppf(0.95, w.df) * _scale(sd, w.df)
    else:
        half = stats.norm.ppf(0.95) * sd
    return np.abs(x - mu) <= half


def p_above(mu, sd, w: Width, line: float = 0.0) -> np.ndarray:
    """Chance the outcome is above `line` (home covers / over)."""
    mu, sd = np.broadcast_arrays(np.asarray(mu, float), np.asarray(sd, float))
    if w.method == "W2":
        return stats.t.sf((line - mu) / _scale(sd, w.df), w.df)
    return stats.norm.sf((line - mu) / sd)
