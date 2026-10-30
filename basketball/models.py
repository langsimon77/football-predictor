"""Basketball phase B1: Elo, the points model, the naive benchmarks and the scores.

Plan: data/audit/preregistration_basketball_b1_2026_10.md, sections 2, 3 and 6.

Every model walks forward one game day at a time: the games of a day are forecast from games
on earlier days only, and their results are added after the whole day is forecast.

Input to every model: a table of played games sorted by date, with columns date, season,
home_id, away_id, home_pts, away_pts.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import ndtr  # standard normal cumulative chance

Z90 = 1.6448536269514722  # a 90% central range is the mean plus or minus 1.645 widths
START = 1500.0  # every new club's Elo rating


# ---------------------------------------------------------------- Elo


@dataclass(frozen=True)
class EloSettings:
    k: float      # update size
    home: float   # home edge, in Elo points
    carry: float  # share of a rating kept at a new season; the rest returns to 1500
    mov: bool     # scale updates by the winning margin (FiveThirtyEight's multiplier)


def elo_run(games: pd.DataFrame, s: EloSettings) -> pd.DataFrame:
    """Walk forward. Returns, per game, `elo_diff` = home rating + home edge - away rating
    before the game, and `p_home` = 1 / (1 + 10^(-elo_diff / 400))."""
    diff, _, _ = _elo_walk(games, s)
    return pd.DataFrame({"elo_diff": diff, "p_home": 1 / (1 + 10 ** (-diff / 400))},
                        index=games.index)


def elo_ratings(games: pd.DataFrame, s: EloSettings, season: int | None = None
                ) -> dict[str, float]:
    """Every club's rating after all of `games` (played games, sorted by date), ready for the
    next game day (phase B4, live forecasts). If `season` is a new season, the ratings get the
    same pull toward 1500 that elo_run applies at a season's first game day."""
    _, ratings, last = _elo_walk(games, s)
    if season is not None and last is not None and season != last:
        ratings = {c: s.carry * r + (1 - s.carry) * START for c, r in ratings.items()}
    return ratings


def _elo_walk(games: pd.DataFrame, s: EloSettings
              ) -> tuple[np.ndarray, dict[str, float], object]:
    ratings: dict[str, float] = {}
    season = None
    diff = np.empty(len(games))
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    seasons = games["season"].to_numpy()
    for idx in _day_groups(games):
        if seasons[idx[0]] != season:  # new season: pull every rating part way back to 1500
            season = seasons[idx[0]]
            ratings = {c: s.carry * r + (1 - s.carry) * START for c, r in ratings.items()}
        for i in idx:  # forecasts first, from ratings before the day
            diff[i] = ratings.get(home[i], START) + s.home - ratings.get(away[i], START)
        for i in idx:  # then the day's results
            expected = 1 / (1 + 10 ** (-diff[i] / 400))
            won = 1.0 if hp[i] > ap[i] else 0.0
            mult = 1.0
            if s.mov:
                winner_diff = diff[i] if won else -diff[i]
                mult = (abs(hp[i] - ap[i]) + 3) ** 0.8 / (7.5 + 0.006 * winner_diff)
            delta = s.k * mult * (won - expected)
            ratings[home[i]] = ratings.get(home[i], START) + delta
            ratings[away[i]] = ratings.get(away[i], START) - delta
    return diff, ratings, season


# ---------------------------------------------------------------- points model


@dataclass(frozen=True)
class PointsSettings:
    half_life: float  # days: a game this old counts half as much as today's
    penalty: float    # pulls every attack and defence rating toward zero


def points_run(games: pd.DataFrame, s: PointsSettings) -> pd.DataFrame:
    """Walk forward. Returns expected home and away points per game:
    home = mu + home edge + attack(home) - defence(away); away = mu + attack(away) -
    defence(home). Fitted before each game day by weighted least squares with a ridge
    penalty on the club ratings; weights halve every `half_life` days.

    The sums are kept up to date day by day: moving forward d days multiplies every past
    weight by 0.5 ** (d / half_life), so the old sums are scaled and the new games added."""
    clubs = sorted(set(games["home_id"]) | set(games["away_id"]))
    col = {c: i for i, c in enumerate(clubs)}
    n = 2 + 2 * len(clubs)  # mu, home edge, attacks, defences
    att = lambda c: 2 + col[c]  # noqa: E731
    dfn = lambda c: 2 + len(clubs) + col[c]  # noqa: E731
    pen = np.full(n, s.penalty)
    pen[:2] = 1e-9  # mu and the home edge are not pulled toward zero
    xtx, xty = np.zeros((n, n)), np.zeros(n)
    beta = np.zeros(n)
    ordinal = np.array([d.toordinal() for d in games["date"]], dtype=float)
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    m_home, m_away = np.full(len(games), np.nan), np.full(len(games), np.nan)
    last_day, seen = None, 0
    pending: list[int] = []  # games of earlier days not yet added
    for idx in _day_groups(games):
        day = ordinal[idx[0]]
        if last_day is not None:
            xtx *= 0.5 ** ((day - last_day) / s.half_life)
            xty *= 0.5 ** ((day - last_day) / s.half_life)
        for i in pending:
            w = 0.5 ** ((day - ordinal[i]) / s.half_life)
            for row, y in ((_row(n, (0, 1, att(home[i])), (dfn(away[i]),)), hp[i]),
                           (_row(n, (0, att(away[i])), (dfn(home[i]),)), ap[i])):
                xtx += w * np.outer(row, row)
                xty += w * row * y
            seen += 1
        if seen:
            beta = np.linalg.solve(xtx + np.diag(pen), xty)
            for i in idx:
                m_home[i] = beta[0] + beta[1] + beta[att(home[i])] - beta[dfn(away[i])]
                m_away[i] = beta[0] + beta[att(away[i])] - beta[dfn(home[i])]
        pending = list(idx)
        last_day = day
    return pd.DataFrame({"m_home": m_home, "m_away": m_away}, index=games.index)


def points_fit(games: pd.DataFrame, s: PointsSettings, day) -> dict:
    """The points model's ratings as points_run would use them on `day` (phase B4, live
    forecasts): every game before that day, weighted 0.5 ** (days ago / half_life), fitted by
    the same weighted least squares with the same ridge penalty. Returns mu, the home edge,
    and each club's attack and defence (a club with no game gets 0, as in points_run)."""
    clubs = sorted(set(games["home_id"]) | set(games["away_id"]))
    col = {c: i for i, c in enumerate(clubs)}
    n = 2 + 2 * len(clubs)
    ordinal = np.array([d.toordinal() for d in games["date"]], dtype=float)
    keep = ordinal < day.toordinal()
    w = 0.5 ** ((day.toordinal() - ordinal) / s.half_life)
    xtx, xty = np.zeros((n, n)), np.zeros(n)
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    for i in np.flatnonzero(keep):
        h, a = col[home[i]], col[away[i]]
        for row, y in ((_row(n, (0, 1, 2 + h), (2 + len(clubs) + a,)), hp[i]),
                       (_row(n, (0, 2 + a), (2 + len(clubs) + h,)), ap[i])):
            xtx += w[i] * np.outer(row, row)
            xty += w[i] * row * y
    pen = np.full(n, s.penalty)
    pen[:2] = 1e-9
    beta = np.linalg.solve(xtx + np.diag(pen), xty)
    return {"mu": float(beta[0]), "home": float(beta[1]),
            "attack": {c: float(beta[2 + i]) for c, i in col.items()},
            "defence": {c: float(beta[2 + len(clubs) + i]) for c, i in col.items()}}


def points_expect(fit: dict, home: str, away: str) -> tuple[float, float]:
    """Expected home and away points from points_fit."""
    att, dfn = fit["attack"], fit["defence"]
    return (fit["mu"] + fit["home"] + att.get(home, 0.0) - dfn.get(away, 0.0),
            fit["mu"] + att.get(away, 0.0) - dfn.get(home, 0.0))


def _row(n: int, plus: tuple[int, ...], minus: tuple[int, ...]) -> np.ndarray:
    r = np.zeros(n)
    r[list(plus)] = 1.0
    r[list(minus)] = -1.0
    return r


def _day_groups(games: pd.DataFrame) -> list[np.ndarray]:
    """Row positions of each game day, in date order. `games` must be sorted by date."""
    dates = pd.to_datetime(pd.Series(games["date"].to_numpy()))
    if not dates.is_monotonic_increasing:
        raise ValueError("games must be sorted by date")
    codes, _ = pd.factorize(dates)
    return [np.flatnonzero(codes == k) for k in range(codes.max() + 1)] if len(codes) else []


@dataclass(frozen=True)
class Spread:
    """Widths of the bell curves around the expected scores, from the tuning seasons."""
    sd_home: float
    sd_away: float
    rho: float

    @property
    def sd_margin(self) -> float:
        return float(np.sqrt(self.sd_home**2 + self.sd_away**2
                             - 2 * self.rho * self.sd_home * self.sd_away))

    @property
    def sd_total(self) -> float:
        return float(np.sqrt(self.sd_home**2 + self.sd_away**2
                             + 2 * self.rho * self.sd_home * self.sd_away))


def spread_from(games: pd.DataFrame, pred: pd.DataFrame) -> Spread:
    rh = games["home_pts"] - pred["m_home"]
    ra = games["away_pts"] - pred["m_away"]
    ok = rh.notna() & ra.notna()
    rho = float(np.corrcoef(rh[ok], ra[ok])[0, 1])
    return Spread(float(rh[ok].std()), float(ra[ok].std()), rho)


# ---------------------------------------------------------------- naive total


def naive_total_mean(games: pd.DataFrame, days: int = 60, min_games: int = 20,
                     fallback: int = 100) -> np.ndarray:
    """Average total of the league's games in the previous `days` days (earlier days only);
    with fewer than `min_games` there, the last `fallback` games (plan, amendment 1)."""
    ordinal = np.array([d.toordinal() for d in games["date"]])
    totals = (games["home_pts"] + games["away_pts"]).to_numpy(float)
    out = np.full(len(games), np.nan)
    for idx in _day_groups(games):
        day = ordinal[idx[0]]
        before = np.flatnonzero(ordinal < day)
        recent = before[ordinal[before] >= day - days]
        use = recent if len(recent) >= min_games else before[-fallback:]
        if len(use):
            out[idx] = totals[use].mean()
    return out


# ---------------------------------------------------------------- scores


def log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def crps_normal(x: np.ndarray, mu: np.ndarray, sd: np.ndarray | float) -> np.ndarray:
    """Continuous ranked probability score of a bell curve (mean mu, width sd) for outcome x:
    sd * (z * (2 Phi(z) - 1) + 2 phi(z) - 1 / sqrt(pi)), z = (x - mu) / sd. Lower is better."""
    sd = np.asarray(sd, dtype=float)
    z = (x - mu) / sd
    pdf = np.exp(-0.5 * z**2) / np.sqrt(2 * np.pi)
    return sd * (z * (2 * ndtr(z) - 1) + 2 * pdf - 1 / np.sqrt(np.pi))


def p_above(mu: np.ndarray, sd: float, line: float = 0.0) -> np.ndarray:
    """Chance a bell curve (mean mu, width sd) lands above `line`."""
    return ndtr((mu - line) / sd)


def inside_90(x: np.ndarray, mu: np.ndarray, sd: float) -> np.ndarray:
    return np.abs(x - mu) <= Z90 * sd


def calibration_slope(p: np.ndarray, y: np.ndarray, steps: int = 50) -> float:
    """Slope of a logistic fit of the outcome on log(p / (1 - p)). 1 is ideal; below 1 the
    forecasts are too bold, above 1 too timid."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    x = np.column_stack([np.ones_like(p), np.log(p / (1 - p))])
    b = np.zeros(2)
    for _ in range(steps):
        q = 1 / (1 + np.exp(-(x @ b)))
        w = q * (1 - q)
        step = np.linalg.solve(x.T @ (x * w[:, None]), x.T @ (y - q))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(b[1])


def bootstrap_mean(diff: np.ndarray, day: np.ndarray, reps: int = 4000,
                   seed: int = 2026, level: float = 0.95) -> tuple[float, float, float]:
    """Mean of `diff` with an interval (95% unless `level` says otherwise), resampling whole
    game days (paired bootstrap: `diff` is one model's score minus another's on the same
    games)."""
    codes, _ = pd.factorize(pd.Series(day))
    sums = np.bincount(codes, weights=diff)
    counts = np.bincount(codes).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(sums), size=(reps, len(sums)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    tail = (1 - level) / 2 * 100
    lo, hi = np.percentile(means, [tail, 100 - tail])
    return float(diff.mean()), float(lo), float(hi)
