"""Phase 4 in the daily run: shadow models and confidence tiers.

Approved by Lang on 26 Sep 2026:
1. The Bayesian model stays the published forecast. The four challengers and the
   stack are locked every day as shadow rows, so their live record builds up for
   the end-of-season re-test (reports/backtest_phase4.md, section 3).
2. Tiers go on the primary row. The promoted-club flag stays visible in `flags`
   but never caps a tier (its backtest evidence pointed the other way).

A failure here never blocks the primary forecast: the caller logs it and locks
the rest.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ensemble import tiers
from fp.features import ml_features, rolling
from fp.models import dixon_coles as dc
from fp.models import ml
from fp.validate.leakage import known_as_of

log = logging.getLogger(__name__)

SHADOWS_LIVE = True
TIERS_LIVE = True
TIERS_RULE = "tiers_v1"
STACK_MODEL = "stack_v1"
CHALLENGER_MODELS = {name: f"{name}_v1" for name in ml.MODELS}
# Chosen by time-ordered cross-validation on 2017/18 to 2020/21 (DECISIONS, 26 Sep 2026).
SETTINGS: dict[str, dict[str, Any]] = {
    "ordered_logit": {},
    "multinomial": {"C": 0.01},
    "random_forest": {"max_depth": 6, "min_samples_leaf": 50},
    "xgboost": {"max_depth": 2, "n_estimators": 150},
}
STACK_FILE = ROOT / "data" / "stacking" / "stack_1x2.json"
TIERS_FILE = ROOT / "data" / "tiers" / "thresholds.json"
# Stack components that come from rows the daily run already builds.
LEDGER_COMPONENTS = {"elo": "elo_v0", "dc": "dc_mle_v0", "bdc": "dc_bayes_v1"}
OUTCOMES = ["p_home", "p_draw", "p_away"]

_train_cache: dict[tuple[int, pd.Timestamp], pd.DataFrame] = {}


def training_rows(matches: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Lock-time feature rows for every match with a result known at `now`.
    Cached per set of known results, which speeds up replays."""
    known = known_as_of(matches, now)
    key = (len(known), known["result_available_utc"].max())
    if key not in _train_cache:
        _train_cache.clear()
        _train_cache[key] = ml_features.build(known)
    return _train_cache[key]


def fit_challengers(matches: pd.DataFrame, now: pd.Timestamp) -> dict[str, ml.Challenger]:
    """Refit every challenger on all results known at `now` (the backtest refitted
    monthly; refitting daily only adds fresher results)."""
    train = training_rows(matches, now)
    out = {}
    for name, params in SETTINGS.items():
        if name == "xgboost" and not ml.xgboost_available():
            log.warning("XGBoost unavailable here; no xgboost or stack rows this run")
            continue
        out[name] = ml.Challenger(name, params).fit(train)
    return out


def fixture_features(cands: pd.DataFrame, matches: pd.DataFrame, fixtures: pd.DataFrame,
                     now: pd.Timestamp, models: dict[str, Any],
                     base: pd.DataFrame | None = None) -> pd.DataFrame:
    """The challengers' 28 inputs for the matches locking now, built the same way as
    the training rows: rolling averages and Elo at lock, fast Dixon-Coles from
    today's fit, schedule from every kickoff before the lock."""
    frame = (base if base is not None
             else rolling.features_for_fixtures(cands, matches, now)).copy()
    for r in frame.itertuples():
        m = models[str(r.league)]
        mk = dc.markets(m.dc_fit.score_matrix(str(r.home_id), str(r.away_id)))
        for col, key in (("dc_home", "p_home"), ("dc_draw", "p_draw"), ("dc_away", "p_away"),
                         ("dc_exp_goals_home", "exp_goals_home"),
                         ("dc_exp_goals_away", "exp_goals_away")):
            frame.loc[r.Index, col] = mk[key]
        frame.loc[r.Index, "promoted_home"] = int(str(r.home_id) in m.promoted)
        frame.loc[r.Index, "promoted_away"] = int(str(r.away_id) in m.promoted)
    cols = ["match_id", "season", "home_id", "away_id", "kickoff_utc"]
    games = pd.concat([matches[cols], fixtures[cols]]).drop_duplicates("match_id")
    games = games[games["kickoff_utc"].notna()]
    frame = frame.join(ml_features.schedule(games, frame), on="match_id")
    return frame


def load_stack() -> tuple[list[str], np.ndarray]:
    data = json.loads(STACK_FILE.read_text(encoding="utf-8"))
    return list(data["models"]), np.asarray(data["weights"], dtype=float)


def add_shadows(new: pd.DataFrame, challengers: dict[str, ml.Challenger],
                features: pd.DataFrame) -> pd.DataFrame:
    """Append challenger and stack rows. Each copies the Elo row's identity columns
    and flags, plus a `shadow` flag."""
    stack_models, weights = load_stack()
    extra = []
    for match_id, rows in new.groupby("match_id", sort=False):
        template = rows[rows["model_name"] == LEDGER_COMPONENTS["elo"]].iloc[0].to_dict()
        f = features[features["match_id"] == match_id]
        probs: dict[str, np.ndarray] = {}
        for key, model_name in LEDGER_COMPONENTS.items():
            got = rows[rows["model_name"] == model_name]
            if len(got):
                probs[key] = got[OUTCOMES].to_numpy(dtype=float)[0]
        for name, model in challengers.items():
            probs[name] = model.predict(f)[0]
        entries = [(CHALLENGER_MODELS[n], probs[n]) for n in challengers]
        missing = [m for m in stack_models if m not in probs]
        if missing:
            log.warning("%s: no stack row, missing %s", match_id, missing)
        else:
            entries.append((STACK_MODEL, sum(w * probs[m]
                                             for m, w in zip(stack_models, weights, strict=True))))
        flags = [*json.loads(str(template["flags"])), "shadow"]
        for model_name, p in entries:
            extra.append({**template, "prediction_id": f"{match_id}:{model_name}",
                          "model_name": model_name, "degraded": False,
                          "p_home": p[0], "p_draw": p[1], "p_away": p[2],
                          "top_scorelines": "[]", "flags": json.dumps(flags)})
    return pd.concat([new, pd.DataFrame(extra)], ignore_index=True)


def tiers_for_row(row: dict, thresholds: dict[str, tiers.Thresholds],
                  stack: np.ndarray | None) -> dict[str, str]:
    """Tier for every market the row carries (spec S7, rule tiers_v1)."""
    flags = json.loads(str(row["flags"]))
    intervals = json.loads(row["intervals"]) if isinstance(row.get("intervals"), str) else {}
    source_failure = int("stale_source" in flags)
    # La Liga referees are appointed after our lock; EPL ones only sometimes.
    referee_unknown = int(row["league"] != "EPL" or "referee_unknown" in flags)
    out = {"rule": TIERS_RULE}

    def width(key: str) -> np.ndarray:
        lo_hi = intervals.get(key)
        return np.array([lo_hi[1] - lo_hi[0] if lo_hi else np.nan])

    p = np.array([row[c] for c in OUTCOMES], dtype=float)
    if np.isfinite(p).all():
        top = OUTCOMES[int(p.argmax())]
        dis = np.array([0.5 * np.abs(stack - p).sum() if stack is not None else np.nan])
        out["1x2"] = str(tiers.assign(thresholds["1x2"], np.array([p.max()]),
                                      np.array([source_failure]), width=width(top),
                                      disagree=dis)[0])
    for market, th in thresholds.items():
        if market.startswith("1x2"):
            continue
        value = row.get(f"p_{market}")
        if value is None or not np.isfinite(value):
            continue
        n_flags = source_failure + (referee_unknown if market.startswith("yellows_") else 0)
        out[market] = str(tiers.assign(th, np.array([max(value, 1 - value)]),
                                       np.array([n_flags]), width=width(f"p_{market}"))[0])
    return out


def add_tiers(new: pd.DataFrame, primary_model: str) -> pd.DataFrame:
    """Fill the `tiers` column of the primary rows."""
    thresholds = tiers.load(TIERS_FILE)
    new = new.copy()
    stacks = new[new["model_name"] == STACK_MODEL].set_index("match_id")
    for i in new.index[new["model_name"] == primary_model]:
        row = new.loc[i].to_dict()
        stack = (stacks.loc[row["match_id"], OUTCOMES].to_numpy(dtype=float)
                 if row["match_id"] in stacks.index else None)
        new.loc[i, "tiers"] = json.dumps(tiers_for_row(row, thresholds, stack))
    return new
