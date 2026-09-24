"""Elo baseline (spec S5.2): goal-difference-adjusted ratings, one pool per league.

After each result:
    expected = 1 / (1 + 10 ** (-(R_home + HOME - R_away) / 400))
    R_home  += K * G * (actual - expected)      and R_away moves the opposite way
    actual   = 1 for a home win, 0.5 for a draw, 0 for a loss
    G        = 1 (margin 0 or 1), 1.5 (margin 2), (11 + margin) / 8 (margin 3 or more)
Between seasons, ratings move a quarter of the way back to 1500, and each promoted
club starts at the average rating of the clubs that went down.

An ordered logistic curve turns the rating gap into home, draw, and away
probabilities. It is refitted at every lock on matches known by then.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

INITIAL = 1500.0


@dataclass
class EloParams:
    k: float = 10.0           # tuned on 2021/22 and 2022/23 (reports/backtest_1f.md)
    home: float = 60.0
    carry: float = 0.75       # share of a rating's distance from 1500 kept over summer
    window_days: int = 1100   # matches used to fit the rating-gap curve


def margin_multiplier(margin: int) -> float:
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11 + margin) / 8


class EloTracker:
    """Replays one league's results in the order they became known.

    advance_to(as_of) applies every result known by as_of. Call it with
    increasing as_of values. The tracker never looks ahead.
    """

    def __init__(self, matches: pd.DataFrame, season_teams: dict[int, set[str]],
                 params: EloParams | None = None):
        self.params = params or EloParams()
        self.season_teams = season_teams
        ordered = matches.sort_values("result_available_utc")
        self._known: list[pd.Timestamp] = list(ordered["result_available_utc"])
        self._rows = ordered[["season", "home_id", "away_id", "home_goals", "away_goals"]
                             ].to_numpy()
        self._next = 0
        self.season: int | None = None
        self.ratings: dict[str, float] = {}
        # One row per processed match: result time, pre-match gap, outcome (0 away, 1 draw, 2 home)
        self.history: list[tuple[pd.Timestamp, float, int]] = []

    def _start_season(self, season: int) -> None:
        teams = self.season_teams[season]
        if self.season is None:
            self.ratings = {t: INITIAL for t in teams}
        else:
            old = self.ratings
            relegated = [old[t] for t in old if t not in teams]
            start = float(np.mean(relegated)) if relegated else INITIAL
            carry = self.params.carry
            self.ratings = {
                t: INITIAL + carry * ((old[t] if t in old else start) - INITIAL) for t in teams
            }
        self.season = season

    def ensure_season(self, season: int) -> None:
        while self.season is None or self.season < season:
            self._start_season(season if self.season is None else self.season + 1)

    def advance_to(self, as_of: pd.Timestamp) -> None:
        p = self.params
        while self._next < len(self._rows):
            known = self._known[self._next]
            if known > as_of:
                break
            season, h, a, hg, ag = self._rows[self._next]
            self.ensure_season(int(season))
            gap = self.ratings[h] + p.home - self.ratings[a]
            expected = 1 / (1 + 10 ** (-gap / 400))
            actual = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
            delta = p.k * margin_multiplier(abs(int(hg) - int(ag))) * (actual - expected)
            self.ratings[h] += delta
            self.ratings[a] -= delta
            outcome = 2 if hg > ag else 1 if hg == ag else 0
            self.history.append((known, gap, outcome))
            self._next += 1

    def gap(self, home_id: str, away_id: str) -> float:
        return self.ratings[home_id] + self.params.home - self.ratings[away_id]


@dataclass
class GapCurve:
    """Ordered logit: P(away) = s(c1 - b*gap), P(away or draw) = s(c2 - b*gap)."""

    b: float
    c1: float
    c2: float

    def probs(self, gap: float | np.ndarray) -> np.ndarray:
        gap = np.atleast_1d(np.asarray(gap, dtype=float))
        away = expit(self.c1 - self.b * gap)
        away_or_draw = expit(self.c2 - self.b * gap)
        return np.column_stack([1 - away_or_draw, away_or_draw - away, away])  # home, draw, away


def fit_curve(gaps: np.ndarray, outcomes: np.ndarray) -> GapCurve:
    """Maximum likelihood fit of the ordered logit. outcomes: 0 away, 1 draw, 2 home."""

    def nll(theta):
        b, c1, log_width = theta
        curve = GapCurve(b, c1, c1 + np.exp(log_width))
        p = curve.probs(gaps)  # columns: home, draw, away
        chosen = p[np.arange(len(outcomes)), 2 - outcomes]
        return -np.sum(np.log(np.clip(chosen, 1e-12, 1)))

    result = minimize(nll, x0=[0.005, -0.5, 0.0], method="Nelder-Mead",
                      options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": 2000})
    b, c1, log_width = result.x
    return GapCurve(float(b), float(c1), float(c1 + np.exp(log_width)))


def curve_as_of(tracker: EloTracker, as_of: pd.Timestamp) -> GapCurve:
    cutoff = as_of - pd.Timedelta(days=tracker.params.window_days)
    rows = [(g, o) for t, g, o in tracker.history if cutoff <= t <= as_of]
    gaps, outcomes = (np.array(v) for v in zip(*rows, strict=True))
    return fit_curve(gaps, outcomes.astype(int))
