"""Corners and cards in the daily run (Phase 3b).

Fits the chosen count models each run, keeps the last good posterior per league
and model (spec S5.1 fallback rule, applied to counts), and fills the corners and
cards columns of each match's primary ledger row.

Chosen on the tuning seasons (reports/backtest_phase3b_*_tune.md):
- corners: total-corners model, Poisson likelihood, split by rolling corner share;
- cards: negative binomial, with an EPL referee effect when the appointment is
  known at lock time, otherwise averaged over referees (decision D3).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fp import ROOT
from fp.models import counts_nb as cn
from fp.validate.leakage import known_as_of

log = logging.getLogger(__name__)

# Live since Lang approved Phase 3b on 25 Sep 2026 (spec S0).
COUNTS_LIVE = True
CORNERS_MODEL = "corners_total_poisson_v1"
CARDS_MODEL = "cards_nb_v1"
STORE = ROOT / "data" / "posteriors"


def params(target: str, league: str) -> cn.CountParams:
    if target == "corners_total":
        return cn.CountParams(target="corners_total", poisson=True, sampler="numpyro")
    return cn.CountParams(target="cards", sampler="numpyro", use_referee=league == "EPL")


def save(post: cn.CountPosterior, league: str, store: Path = STORE) -> None:
    if not post.ok:
        raise ValueError("refusing to store a count posterior that failed its diagnostics")
    store.mkdir(parents=True, exist_ok=True)
    meta = {"target": post.target, "teams": post.teams, "referees": post.referees,
            "scales": post.scales, "poisson": post.poisson, "diagnostics": post.diagnostics}
    arrays: dict[str, Any] = {"meta": np.array(json.dumps(meta))}
    arrays.update({f"draw_{k}": v for k, v in post.draws.items()})
    np.savez_compressed(store / f"{league}_{post.target}.npz", **arrays)


def load(league: str, target: str, store: Path = STORE) -> cn.CountPosterior | None:
    path = store / f"{league}_{target}.npz"
    if not path.exists():
        return None
    z = np.load(path)
    meta = json.loads(str(z["meta"]))
    return cn.CountPosterior(
        target=meta["target"], teams=meta["teams"], referees=meta["referees"],
        draws={k[5:]: z[k] for k in z.files if k.startswith("draw_")},
        scales={k: tuple(v) for k, v in meta["scales"].items()}, poisson=meta["poisson"],
        diagnostics=meta["diagnostics"])


@dataclass
class LeagueCounts:
    corners: cn.CountPosterior | None
    cards: cn.CountPosterior | None
    fallbacks: list[str]


def fit_league(matches: pd.DataFrame, features: pd.DataFrame, league: str, now: pd.Timestamp,
               store: Path = STORE) -> LeagueCounts:
    lg = matches[matches["league"] == league]
    known = known_as_of(lg, now)
    teams = sorted(set(lg["home_id"]) | set(lg["away_id"]))
    out: dict[str, cn.CountPosterior | None] = {}
    fallbacks = []
    for target, to_rows in (("corners_total", cn.total_corner_rows), ("cards", cn.card_rows)):
        post = cn.fit_checked(to_rows(known, features), now, teams, params(target, league))
        log.info("%s %s fit %.1fs %s", league, target, post.seconds, post.diagnostics)
        if post.ok:
            save(post, league, store)
            out[target] = post
        else:  # never publish from a failed fit
            out[target] = load(league, target, store)
            fallbacks.append(f"{target}_posterior_fallback" if out[target] else
                             f"{target}_unavailable")
    return LeagueCounts(corners=out["corners_total"], cards=out["cards"], fallbacks=fallbacks)


def columns(models: LeagueCounts, fixture_features: pd.DataFrame, match_id: str,
            referee: str | None) -> tuple[dict, list[str]]:
    """Ledger columns for one match, plus flags."""
    flags = list(models.fallbacks)
    cols: dict = {}
    f = fixture_features[fixture_features["match_id"] == match_id]
    if models.corners is not None:
        row = cn.total_corner_rows(f, fixture_features).iloc[0].to_dict()
        out = cn.predict(models.corners, row)
        cols.update({"exp_corners_home": out["exp_home"], "exp_corners_away": out["exp_away"]})
        cols.update({f"p_corners_over_{str(k).replace('.', '_')}": v
                     for k, v in out["over"].items()})
    if models.cards is not None:
        row = cn.card_rows(f.assign(referee=referee), fixture_features).iloc[0].to_dict()
        out = cn.predict(models.cards, row)
        cols["exp_yellows"] = out["exp_total"]
        cols.update({f"p_yellows_over_{str(k).replace('.', '_')}": v
                     for k, v in out["over"].items()})
        if models.cards.referees and not out["referee_known"]:
            flags.append("referee_unknown")
    flags.append(f"counts:{CORNERS_MODEL},{CARDS_MODEL}")
    return cols, flags
