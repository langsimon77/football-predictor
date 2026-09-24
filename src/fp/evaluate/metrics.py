"""Proper scoring rules and market de-margining.

All functions take arrays with one row per match. Lower scores are better.
Outcome codes for 1X2: 0 = home win, 1 = draw, 2 = away win.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

EPS = 1e-15


def outcome_1x2(home_goals: np.ndarray, away_goals: np.ndarray) -> np.ndarray:
    return np.where(home_goals > away_goals, 0, np.where(home_goals == away_goals, 1, 2))


def rps(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    """Ranked Probability Score for ordered outcomes (home, draw, away).

    RPS = 1/(K-1) * sum over k of (cumulative forecast - cumulative outcome)^2.
    It rewards putting probability near the actual result: calling a draw when
    the home side won is less wrong than calling an away win.
    """
    probs = np.asarray(probs, dtype=float)
    k = probs.shape[1]
    observed = np.eye(k)[outcome]
    diff = np.cumsum(probs, axis=1)[:, :-1] - np.cumsum(observed, axis=1)[:, :-1]
    return (diff**2).sum(axis=1) / (k - 1)


def log_loss(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    """Surprise: -ln of the probability given to what happened."""
    probs = np.asarray(probs, dtype=float)
    return -np.log(np.clip(probs[np.arange(len(outcome)), outcome], EPS, 1.0))


def brier(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    """Squared distance between the forecast and the 0/1 outcome, summed over outcomes."""
    probs = np.asarray(probs, dtype=float)
    return ((probs - np.eye(probs.shape[1])[outcome]) ** 2).sum(axis=1)


def binary_log_loss(p: np.ndarray, happened: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return -np.where(happened, np.log(p), np.log(1 - p))


def binary_brier(p: np.ndarray, happened: np.ndarray) -> np.ndarray:
    return (np.asarray(p, dtype=float) - np.asarray(happened, dtype=float)) ** 2


def demargin_power(odds: np.ndarray) -> np.ndarray:
    """Implied probabilities with the bookmaker margin removed by the power method.

    Raw implied probabilities 1/odds sum to more than 1. Find k with
    sum((1/odds)^k) = 1. Because k > 1 shrinks small numbers proportionally more,
    this takes more margin off long shots, where bookmakers put more of it.
    Rows with any missing or invalid odds return NaN.
    """
    odds = np.asarray(odds, dtype=float)
    out = np.full(odds.shape, np.nan)
    for i, row in enumerate(odds):
        if not np.all(np.isfinite(row)) or np.any(row <= 1.0):
            continue
        raw = 1.0 / row
        if raw.sum() <= 1.0:  # no margin (rare on exchanges): just normalise
            out[i] = raw / raw.sum()
            continue
        k = brentq(lambda k, raw=raw: np.sum(raw**k) - 1.0, 1.0, 10.0)
        out[i] = raw**k
    return out
