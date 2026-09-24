"""Promoted-team prior for the fast Dixon-Coles model.

Promoted clubs are usually weaker than the average top-flight club. With few
top-flight matches, the ridge penalty would pull them to average and overrate
them. Instead we pull them towards the average rating that promoted clubs
actually had in their first top-flight season.

Estimated from the promoted clubs of 2017/18 to 2020/21 only (24 clubs across
both leagues). Those seasons come before every tuning and test season, so the
estimate cannot leak into the backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fp.models import dixon_coles as dc

ESTIMATION_SEASONS = (2017, 2018, 2019, 2020)


def season_teams(matches: pd.DataFrame, league: str) -> dict[int, set[str]]:
    lg = matches[matches["league"] == league]
    seasons = lg["season"].astype(int)
    return {s: set(lg.loc[seasons == s, "home_id"]) for s in sorted(set(seasons.tolist()))}


def promoted(teams_by_season: dict[int, set[str]], season: int) -> set[str]:
    if season - 1 not in teams_by_season:
        return set()
    return teams_by_season[season] - teams_by_season[season - 1]


def estimate(matches: pd.DataFrame) -> tuple[float, float]:
    """Average first-season (attack, defence) of promoted clubs, both leagues pooled."""
    values = []
    for league in ("EPL", "LaLiga"):
        teams = season_teams(matches, league)
        for season in ESTIMATION_SEASONS:
            games = matches[(matches["league"] == league) & (matches["season"] == season)]
            end = games["kickoff_utc"].max() + pd.Timedelta(days=1)
            fit = dc.fit(games, end, dc.DCParams(xi=0.0, ridge=0.5, window_days=400))
            for team in promoted(teams, season):
                values.append((fit.attack[team], fit.defence[team]))
    a, d = np.mean(values, axis=0)
    return float(a), float(d)


class PromotedPrior:
    """Computes the prior once per matches table and reuses it."""

    def __init__(self, matches: pd.DataFrame):
        self.mean = estimate(matches)

    def for_season(self, teams_by_season: dict[int, set[str]], season: int
                   ) -> dict[str, tuple[float, float]]:
        return {t: self.mean for t in promoted(teams_by_season, season)}
