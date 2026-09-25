"""Confidence tiers: High, Medium, Low (spec S7; Phase 4).

Every match still gets a forecast. The tier says how much to trust it.

Rule, in order:
1. Start from the favoured probability: the top of home, draw, away, or the
   likelier side of an over/under line. At or above `high` starts High; below
   `low` starts Low; in between starts Medium.
2. Uncertainty: if the 80% interval on that probability is wider than
   `width_max`, or the ensemble and the Bayesian model disagree by more than
   `disagree_max`, drop one tier. A missing input never demotes.
3. Data quality flags: one flag caps the tier at Medium; two or more force Low.

All cut points come from the tuning seasons (`fit`), never the test seasons.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

TIERS = ("Low", "Medium", "High")
HIGH_QUANTILE = 0.75     # top quarter of tuning forecasts starts High
LOW_QUANTILE = 1 / 3     # bottom third starts Low
TAIL_QUANTILE = 0.90     # widest or most disputed tenth drops one tier


@dataclass
class Thresholds:
    market: str
    high: float
    low: float
    width_max: float | None = None
    disagree_max: float | None = None
    basis: str = ""


def fit(market: str, favoured: np.ndarray, width: np.ndarray | None = None,
        disagree: np.ndarray | None = None, basis: str = "") -> Thresholds:
    """Cut points from tuning-season forecasts, rounded to two decimals."""
    def cut(values: np.ndarray | None, q: float) -> float | None:
        if values is None or not np.isfinite(values).any():
            return None
        return round(float(np.nanquantile(values, q)), 2)
    high, low = cut(favoured, HIGH_QUANTILE), cut(favoured, LOW_QUANTILE)
    assert high is not None and low is not None
    return Thresholds(market=market, high=high, low=low, width_max=cut(width, TAIL_QUANTILE),
                      disagree_max=cut(disagree, TAIL_QUANTILE), basis=basis)


def assign(th: Thresholds, favoured: np.ndarray, n_flags: np.ndarray,
           width: np.ndarray | None = None, disagree: np.ndarray | None = None) -> np.ndarray:
    """Tier name for every forecast."""
    favoured = np.asarray(favoured, dtype=float)
    level = np.where(favoured >= th.high, 2, np.where(favoured < th.low, 0, 1))
    demote = np.zeros(len(favoured), dtype=bool)
    for values, limit in ((width, th.width_max), (disagree, th.disagree_max)):
        if values is not None and limit is not None:
            demote |= np.nan_to_num(np.asarray(values, dtype=float), nan=-np.inf) > limit
    level = np.maximum(level - demote, 0)
    n_flags = np.asarray(n_flags)
    level = np.where(n_flags >= 1, np.minimum(level, 1), level)
    level = np.where(n_flags >= 2, 0, level)
    return np.array(TIERS)[level]


def save(items: list[Thresholds], path: Path, **metadata: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**metadata, "thresholds": [asdict(t) for t in items]}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Thresholds]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t["market"]: Thresholds(**t) for t in data["thresholds"]}
