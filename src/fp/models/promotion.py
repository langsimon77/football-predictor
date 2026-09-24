"""Promoted-team priors from second-tier form (spec S5.1).

A club that dominated the Championship usually does better after promotion than
one that scraped up through the play-offs. So each promoted club gets its own
prior, from a regression fitted on past promoted clubs:

    first-season attack  = a_att + b_att * second-tier attack
    first-season defence = a_def + b_def * second-tier defence

Ratings on both sides come from simple maximum-likelihood Dixon-Coles fits of
one whole season, so each is measured against its own league's average.
The regression uses the clubs promoted for 2017/18 to 2020/21 only. Those seasons
come before every tuning and test season, so the prior cannot leak.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fp.models import dixon_coles as dc
from fp.models.priors import promoted, season_teams

ESTIMATION_SEASONS = (2017, 2018, 2019, 2020)
SEASON_FIT = dc.DCParams(xi=0.0, ridge=1.0, window_days=400)


def _season_fit(games: pd.DataFrame, home: str, away: str) -> dc.DCFit:
    if home != "home_id":  # second tier: rate every club by name, promoted or not
        games = games.drop(columns=["home_id", "away_id"])
    frame = games.rename(columns={home: "home_id", away: "away_id"})
    end = pd.Timestamp(frame["result_available_utc"].max()) + pd.Timedelta(days=1)
    frame = frame.assign(kickoff_utc=frame["result_available_utc"])
    return dc.fit(frame, end, SEASON_FIT)


def second_tier_ratings(second_tier: pd.DataFrame, league: str, season: int
                        ) -> dict[str, tuple[float, float]]:
    """(attack, defence) of every club in one second-tier season, keyed by team_id.

    Clubs never promoted have no team_id and are left out of the result.
    """
    games = second_tier[(second_tier["league"] == league) & (second_tier["season"] == season)]
    fit = _season_fit(games, "home_name", "away_name")
    ids = dict(zip(games["home_name"], games["home_id"], strict=False))
    return {ids[name]: (fit.attack[name], fit.defence[name])
            for name in fit.teams if isinstance(ids.get(name), str)}


def first_season_ratings(matches: pd.DataFrame, league: str, season: int
                         ) -> dict[str, tuple[float, float]]:
    games = matches[(matches["league"] == league) & (matches["season"] == season)]
    fit = _season_fit(games, "home_id", "away_id")
    return {t: (fit.attack[t], fit.defence[t]) for t in fit.teams}


@dataclass
class PromotionModel:
    a_att: float
    b_att: float
    sd_att: float
    a_def: float
    b_def: float
    sd_def: float
    n: int

    def prior(self, second_tier_rating: tuple[float, float]) -> tuple[float, float, float, float]:
        """Prior (mean attack, sd attack, mean defence, sd defence) for one promoted club."""
        att2, def2 = second_tier_rating
        return (self.a_att + self.b_att * att2, self.sd_att,
                self.a_def + self.b_def * def2, self.sd_def)


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)
    return float(a), float(b), float(np.sqrt(resid @ resid / (len(x) - 2)))


def fit_promotion_model(matches: pd.DataFrame, second_tier: pd.DataFrame) -> PromotionModel:
    rows = []
    for league in ("EPL", "LaLiga"):
        teams = season_teams(matches, league)
        for season in ESTIMATION_SEASONS:
            lower = second_tier_ratings(second_tier, league, season - 1)
            upper = first_season_ratings(matches, league, season)
            for team in promoted(teams, season):
                rows.append((*lower[team], *upper[team]))
    r = np.array(rows)
    a_att, b_att, sd_att = _ols(r[:, 0], r[:, 2])
    a_def, b_def, sd_def = _ols(r[:, 1], r[:, 3])
    return PromotionModel(a_att, b_att, sd_att, a_def, b_def, sd_def, n=len(r))


def promoted_priors(model: PromotionModel, matches_or_teams: dict[int, set[str]],
                    second_tier: pd.DataFrame, league: str, season: int
                    ) -> dict[str, tuple[float, float, float, float]]:
    """Priors for the clubs promoted into `season`, from their season - 1 second-tier form."""
    lower = second_tier_ratings(second_tier, league, season - 1)
    return {t: model.prior(lower[t]) for t in promoted(matches_or_teams, season)}
