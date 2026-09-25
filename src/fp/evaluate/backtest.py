"""Walk-forward backtest (spec S8).

For every past match, as_of is the daily run that would have locked it
(fp.validate.leakage.lock_time). At each lock time the models are refitted on
results known by then, and only then asked about the matches locked at that
moment. This is the live system replayed, so the scores are honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import numpy as np
import pandas as pd

from fp.evaluate import metrics
from fp.models import dixon_coles as dc
from fp.models import elo
from fp.models.priors import PromotedPrior, season_teams
from fp.validate.leakage import check_features, known_as_of, lock_time

DC_MARKETS = ["p_home", "p_draw", "p_away", "p_over_1_5", "p_over_2_5", "p_over_3_5",
              "p_btts", "exp_goals_home", "exp_goals_away"]


@dataclass
class Config:
    seasons: list[int]
    dc: dc.DCParams = field(default_factory=dc.DCParams)
    elo: elo.EloParams = field(default_factory=elo.EloParams)
    base_window_days: int = 1100
    refit_days: int = 0  # 0 = refit Dixon-Coles at every lock; 7 = weekly, like Phase 2


def predict_league(matches: pd.DataFrame, league: str, cfg: Config,
                   prior: PromotedPrior) -> pd.DataFrame:
    lg = matches[matches["league"] == league]
    teams_by_season = season_teams(matches, league)
    targets = lg[lg["season"].isin(cfg.seasons)].copy()
    targets["lock_utc"] = lock_time(targets["kickoff_utc"])
    tracker = elo.EloTracker(lg, teams_by_season, cfg.elo)

    rows = []
    fit_at: pd.Timestamp | None = None
    fit_season: int | None = None
    for lock_key, group in targets.groupby("lock_utc", sort=True):
        lock = cast(pd.Timestamp, lock_key)  # groupby key of a UTC datetime column
        season = int(group["season"].iloc[0])
        known = known_as_of(lg, lock)
        tracker.advance_to(lock)
        tracker.ensure_season(season)
        curve = elo.curve_as_of(tracker, lock)
        if (cfg.refit_days == 0 or fit_at is None or season != fit_season
                or lock - fit_at >= pd.Timedelta(days=cfg.refit_days)):
            fit = dc.fit(known, lock, cfg.dc, prior.for_season(teams_by_season, season),
                         extra_teams=sorted(teams_by_season[season]))
            fit_at, fit_season = lock, season
        recent = known[known["kickoff_utc"] >= lock - pd.Timedelta(days=cfg.base_window_days)]
        outcome = metrics.outcome_1x2(recent["home_goals"].to_numpy(),
                                      recent["away_goals"].to_numpy())
        base = np.bincount(outcome, minlength=3) / len(outcome)
        base_over = float(((recent["home_goals"] + recent["away_goals"]) > 2.5).mean())
        for r in group.itertuples():
            home, away = str(r.home_id), str(r.away_id)
            out = dc.markets(fit.score_matrix(home, away))
            e = curve.probs(tracker.gap(home, away))[0]
            row = {
                "match_id": r.match_id, "league": league, "season": season,
                "as_of_utc": lock, "source_max_utc": known["result_available_utc"].max(),
                "dc_converged": fit.converged,
                "elo_home": e[0], "elo_draw": e[1], "elo_away": e[2],
                "base_home": base[0], "base_draw": base[1], "base_away": base[2],
                "base_over_2_5": base_over,
            }
            row.update({f"dc_{k[2:] if k.startswith('p_') else k}": out[k] for k in DC_MARKETS})
            rows.append(row)
    preds = pd.DataFrame(rows)
    check_features(preds)  # fails loudly if any prediction saw the future
    return preds


def run(matches: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    prior = PromotedPrior(matches)
    return pd.concat([predict_league(matches, lg, cfg, prior) for lg in ("EPL", "LaLiga")],
                     ignore_index=True)


def _market(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return metrics.demargin_power(frame[cols].to_numpy())


def attach_outcomes_and_market(preds: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    m = matches.set_index("match_id")
    odds_cols = [str(c) for c in m.columns if str(c).startswith("odds_")]
    out = preds.join(m[["home_goals", "away_goals", *odds_cols]], on="match_id")
    out["outcome"] = metrics.outcome_1x2(out["home_goals"].to_numpy(), out["away_goals"].to_numpy())
    out["over_2_5"] = (out["home_goals"] + out["away_goals"]) > 2.5

    books = {"pin_close": "odds_pin_close", "bfe_close": "odds_bfe_close",
             "avg_close": "odds_avg_close", "pin_pre": "odds_pin_pre", "avg_pre": "odds_avg_pre"}
    for name, prefix in books.items():
        p = _market(out, [f"{prefix}_home", f"{prefix}_draw", f"{prefix}_away"])
        out[[f"mkt_{name}_home", f"mkt_{name}_draw", f"mkt_{name}_away"]] = p
        ou = _market(out, [f"{prefix}_over25", f"{prefix}_under25"])
        out[f"mkt_{name}_over_2_5"] = ou[:, 0]
    # Sharpest available closing line: Pinnacle until it vanished (Jan 2026), then Betfair.
    for k in ("home", "draw", "away", "over_2_5"):
        out[f"mkt_sharp_{k}"] = out[f"mkt_pin_close_{k}"].fillna(out[f"mkt_bfe_close_{k}"])
    return out


def score_1x2(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    probs = frame[[f"{prefix}_home", f"{prefix}_draw", f"{prefix}_away"]].to_numpy()
    y = frame["outcome"].to_numpy()
    return pd.DataFrame({
        "rps": metrics.rps(probs, y),
        "log_loss": metrics.log_loss(probs, y),
        "brier": metrics.brier(probs, y),
        "top_pick_hit": (probs.argmax(axis=1) == y).astype(float),
    }, index=frame.index)


def paired_ci(diff: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval for a mean difference over the same matches."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), (n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summary(scored: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    """Mean RPS, log loss, Brier, and top-pick accuracy per model, on matches every
    model priced (market odds are occasionally missing)."""
    cols = [f"{m}_{k}" for m in models for k in ("home", "draw", "away")]
    common = scored.dropna(subset=cols)
    rows = []
    for m in models:
        s = score_1x2(common, m)
        rows.append({"model": m, "n": len(common), **s.mean().round(4).to_dict()})
    return pd.DataFrame(rows)
