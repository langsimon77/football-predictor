"""Stacked ensemble for home, draw, away (spec S5.6 step 2; Phase 4).

The ensemble is a weighted average of the models' probabilities (a linear pool).
Weights are learned by minimising log loss on predictions the models made
walk-forward, so every input was a genuine forecast at its time.

Guardrails from the spec:
- every model keeps at least a 5% weight, so a model can recover;
- in live use, a weekly update moves each weight by at most 10 percentage points;
- weights move off the backtest values only after 60 scored live predictions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax

FLOOR = 0.05
MAX_WEEKLY_MOVE = 0.10
MIN_LIVE_PREDICTIONS = 60


@dataclass
class Stack:
    models: list[str]
    weights: np.ndarray
    floor: float = FLOOR

    def combine(self, probs: dict[str, np.ndarray]) -> np.ndarray:
        return sum(w * probs[m] for m, w in zip(self.models, self.weights, strict=True))


def _weights(theta: np.ndarray, floor: float) -> np.ndarray:
    """Weights that sum to 1 with every weight at least `floor`."""
    k = len(theta) + 1
    free = softmax(np.concatenate([[0.0], theta]))
    return floor + (1 - k * floor) * free


def fit(probs: dict[str, np.ndarray], y: np.ndarray, floor: float = FLOOR,
        sample_weight: np.ndarray | None = None) -> Stack:
    """Weights with the lowest (optionally weighted) mean log loss. sample_weight
    lets recent matches count more (PRD item 10: time decay)."""
    models = list(probs)
    stacked = np.stack([probs[m] for m in models])        # (models, n, 3)
    chosen = stacked[:, np.arange(len(y)), y]              # (models, n)
    sw = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    sw = sw / sw.sum()

    def loss(theta: np.ndarray) -> float:
        p = _weights(theta, floor) @ chosen
        return float(-np.sum(sw * np.log(np.clip(p, 1e-12, 1))))

    res = minimize(loss, np.zeros(len(models) - 1), method="Nelder-Mead",
                   options={"maxiter": 20000, "xatol": 1e-7, "fatol": 1e-9})
    return Stack(models=models, weights=_weights(res.x, floor), floor=floor)


def guarded_update(current: np.ndarray, target: np.ndarray, n_scored: int,
                   floor: float = FLOOR, max_move: float = MAX_WEEKLY_MOVE) -> np.ndarray:
    """One weekly move from `current` towards `target` weights under the guardrails.

    Returns the weights closest to `target` that sum to 1, stay at or above the
    floor, and move no weight more than `max_move` from `current`. They take the
    form clip(target + shift, low, high); the single shift that makes them sum to 1
    is found by bisection, since the sum rises steadily with the shift.
    """
    current = np.asarray(current, dtype=float)
    if n_scored < MIN_LIVE_PREDICTIONS:
        return current
    target = np.asarray(target, dtype=float)
    low = np.maximum(current - max_move, floor)
    high = np.minimum(current + max_move, 1.0)
    lo_shift, hi_shift = -1.0, 1.0
    for _ in range(100):
        mid = (lo_shift + hi_shift) / 2
        if np.clip(target + mid, low, high).sum() > 1.0:
            hi_shift = mid
        else:
            lo_shift = mid
    return np.clip(target + (lo_shift + hi_shift) / 2, low, high)
