"""Season-end table projection (spec S9, page 3).

Each simulation draws one set of team ratings from the Bayesian posterior, plays
every remaining fixture with Poisson goals, and adds the points to the current
table. Ranking uses points, then goal difference, then goals scored. That is the
Premier League rule; La Liga breaks ties head to head first, which this ignores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fp.models.bayes_dc import Posterior

N_SIMS = 10_000
TOP = 4
RELEGATED = 3


def table(played: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """Current points, goal difference, and goals for from completed matches."""
    rows = {t: {"played": 0, "points": 0, "gd": 0, "gf": 0} for t in teams}
    for home, away, hg, ag in zip(played["home_id"], played["away_id"], played["home_goals"],
                                  played["away_goals"], strict=True):
        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            if team not in rows:
                continue
            r = rows[team]
            r["played"] += 1
            r["gf"] += int(gf)
            r["gd"] += int(gf) - int(ga)
            r["points"] += 3 if gf > ga else 1 if gf == ga else 0
    return pd.DataFrame.from_dict(rows, orient="index")


def simulate(post: Posterior, played: pd.DataFrame, remaining: pd.DataFrame,
             n_sims: int = N_SIMS, seed: int = 0) -> pd.DataFrame:
    """Per club: current points, mean final points, and chances of the title, the
    top four, and relegation."""
    teams = sorted(set(played["home_id"]) | set(played["away_id"])
                   | set(remaining["home_id"]) | set(remaining["away_id"]))
    now = table(played, teams)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, len(post.mu), n_sims)
    idx = {t: i for i, t in enumerate(teams)}
    points = np.tile(now["points"].to_numpy(dtype=float), (n_sims, 1))
    gd = np.tile(now["gd"].to_numpy(dtype=float), (n_sims, 1))
    gf = np.tile(now["gf"].to_numpy(dtype=float), (n_sims, 1))
    for home, away in zip(remaining["home_id"], remaining["away_id"], strict=True):
        h, a = post.index(home), post.index(away)
        lam = np.exp(post.mu[draw] + post.home[draw] + post.att[draw, h] + post.def_[draw, a])
        nu = np.exp(post.mu[draw] + post.att[draw, a] + post.def_[draw, h])
        x, y = rng.poisson(lam), rng.poisson(nu)
        i, j = idx[home], idx[away]
        points[:, i] += np.where(x > y, 3, np.where(x == y, 1, 0))
        points[:, j] += np.where(y > x, 3, np.where(x == y, 1, 0))
        gd[:, i] += x - y
        gd[:, j] += y - x
        gf[:, i] += x
        gf[:, j] += y
    key = points * 1e6 + (gd + 1000) * 1e3 + gf + rng.random(points.shape) * 1e-3
    position = (-key).argsort(axis=1).argsort(axis=1) + 1   # 1 = top
    n = len(teams)
    return pd.DataFrame({
        "team_id": teams, "played": now["played"].to_numpy(), "points": now["points"].to_numpy(),
        "mean_points": points.mean(axis=0).round(1),
        "p_title": (position == 1).mean(axis=0), "p_top4": (position <= TOP).mean(axis=0),
        "p_relegation": (position > n - RELEGATED).mean(axis=0),
        "mean_position": position.mean(axis=0).round(1),
    }).sort_values("mean_points", ascending=False).reset_index(drop=True)
