"""Calibration maps for home, draw, away probabilities (spec S5.6 step 3; Phase 3a).

Phase 2 found the Dixon-Coles family too timid: when it says 68% the favourite
wins 74% of the time. A calibration map is a small, fitted correction that
stretches forecasts back to match what happens.

Two candidates:
- Power scaling: q_i proportional to p_i ** alpha. One number. alpha above 1
  stretches favourites up and long shots down.
- Dirichlet calibration (Kull et al., 2019): q = softmax(W log p + b), with a
  penalty pulling W towards the identity and b towards zero. The three-outcome
  version of beta calibration.

After calibrating home, draw, away, the whole scoreline table is rescaled region
by region to match (PRD item 22), so every goals market stays consistent with it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import log_softmax, softmax

EPS = 1e-9


def _nll(q: np.ndarray, y: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(q[np.arange(len(y)), y], EPS, 1))))


@dataclass
class Identity:
    method: str = "identity"

    def apply(self, p: np.ndarray) -> np.ndarray:
        return np.asarray(p, dtype=float)


@dataclass
class PowerCalibration:
    alpha: float = 1.0
    method: str = "power"

    def apply(self, p: np.ndarray) -> np.ndarray:
        logp = np.log(np.clip(np.asarray(p, dtype=float), EPS, 1))
        return softmax(self.alpha * logp, axis=1)

    @classmethod
    def fit(cls, p: np.ndarray, y: np.ndarray) -> PowerCalibration:
        res = minimize_scalar(lambda a: _nll(cls(a).apply(p), y), bounds=(0.5, 3.0),
                              method="bounded")
        return cls(alpha=float(res.x))


@dataclass
class DirichletCalibration:
    weights: list[list[float]] = field(default_factory=lambda: np.eye(3).tolist())
    bias: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    penalty: float = 0.0
    method: str = "dirichlet"

    def apply(self, p: np.ndarray) -> np.ndarray:
        logp = np.log(np.clip(np.asarray(p, dtype=float), EPS, 1))
        return softmax(logp @ np.array(self.weights).T + np.array(self.bias), axis=1)

    @classmethod
    def fit(cls, p: np.ndarray, y: np.ndarray, penalty: float = 0.01) -> DirichletCalibration:
        logp = np.log(np.clip(np.asarray(p, dtype=float), EPS, 1))
        start = np.concatenate([np.eye(3).ravel(), np.zeros(3)])
        res = minimize(dirichlet_objective, start, args=(logp, np.eye(3)[y], penalty),
                       jac=True, method="L-BFGS-B")
        return cls(weights=res.x[:9].reshape(3, 3).tolist(), bias=res.x[9:].tolist(),
                   penalty=penalty)


def dirichlet_objective(theta: np.ndarray, logp: np.ndarray, onehot: np.ndarray,
                        penalty: float) -> tuple[float, np.ndarray]:
    """Mean log loss plus penalty, and its exact gradient."""
    eye = np.eye(3)
    w, b = theta[:9].reshape(3, 3), theta[9:]
    logq = log_softmax(logp @ w.T + b, axis=1)
    n = len(onehot)
    loss = -np.sum(onehot * logq) / n + penalty * (np.sum((w - eye) ** 2) + np.sum(b**2))
    g = (np.exp(logq) - onehot) / n  # d loss / d (logp @ w.T + b)
    grad_w = g.T @ logp + 2 * penalty * (w - eye)
    grad_b = g.sum(axis=0) + 2 * penalty * b
    return float(loss), np.concatenate([grad_w.ravel(), grad_b])


Calibrator = Identity | PowerCalibration | DirichletCalibration


def save(cal: Calibrator, path: Path, **metadata: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**asdict(cal), **metadata}, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> Calibrator:
    data = json.loads(path.read_text(encoding="utf-8"))
    method = data["method"]
    if method == "power":
        return PowerCalibration(alpha=data["alpha"])
    if method == "dirichlet":
        return DirichletCalibration(weights=data["weights"], bias=data["bias"],
                                    penalty=data["penalty"])
    return Identity()


def rescale_matrix(matrix: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Scale the home-win, draw, and away-win regions of a scoreline table so they
    sum to the calibrated probabilities. Relative shapes inside each region are kept."""
    m = np.asarray(matrix, dtype=float).copy()
    n = m.shape[0]
    home = np.tril(np.ones((n, n), dtype=bool), -1)   # home goals > away goals
    draw = np.eye(n, dtype=bool)
    away = home.T
    for region, q in zip((home, draw, away), target, strict=True):
        total = m[region].sum()
        if total > 0:
            m[region] *= q / total
    return m / m.sum()


def calibration_slope(p_home: np.ndarray, won: np.ndarray, bins: int = 5) -> float:
    """Slope of observed home-win rate on mean forecast across equal-size bins.
    1 is perfect; above 1 means too timid."""
    order = np.argsort(p_home)
    groups = np.array_split(order, bins)
    f = np.array([p_home[g].mean() for g in groups])
    o = np.array([won[g].mean() for g in groups])
    return float(np.polyfit(f, o, 1)[0])
