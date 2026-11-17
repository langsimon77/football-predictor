"""Basketball upgrade step 4 (Lang: "Approved all", 17 Nov 2026): model plus market.

Winner: logarithmic pool, p = sigmoid(w * logit(p_model) + (1 - w) * logit(p_market)).
Handicap and total: the mean is w * model + (1 - w) * market line; the width stays the model's.
The weight w is fitted once by least log loss (winner) on the first MIN_GAMES locked games that
have a pre-tip-off market price, then frozen and tested on the next MIN_GAMES
(pre-registration B6, section 6). Until then w is None and nothing is blended.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar

MIN_GAMES = 150
EPS = 1e-6


def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def pool(p_model, p_market, w: float):
    z = w * _logit(p_model) + (1 - w) * _logit(p_market)
    return 1 / (1 + np.exp(-z))


def fit_weight(p_model, p_market, y) -> float:
    """Weight on the model, in [0, 1], that minimises mean log loss."""
    y = np.asarray(y, float)

    def loss(w):
        p = np.clip(pool(p_model, p_market, w), EPS, 1 - EPS)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())

    return float(minimize_scalar(loss, bounds=(0.0, 1.0), method="bounded").x)


def blend_line(model_mean, market_line, w: float):
    return w * np.asarray(model_mean, float) + (1 - w) * np.asarray(market_line, float)
