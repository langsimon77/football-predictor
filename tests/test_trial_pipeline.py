"""Leagues on trial in the background (Lang chose "Run what passed", 13 Oct 2026)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fp import ledger
from fp.models import posterior_store, shape
from fp.pipeline import daily, trial


def rows() -> pd.DataFrame:
    base = {"match_id": "SerieA_2627_roma_genoa", "league": "SerieA", "p_home": 0.5,
            "p_draw": 0.3, "p_away": 0.2, "p_over_2_5": 0.55, "p_btts": 0.5,
            "p_corners_over_9_5": 0.5, "exp_corners_home": 5.0, "exp_goals_home": 1.6,
            "exp_goals_away": 1.0, "p_yellows_over_4_5": 0.4, "top_scorelines": "[[1, 0, 0.1]]",
            "intervals": json.dumps({"p_home": [0.4, 0.6], "p_over_2_5": [0.5, 0.6]})}
    return pd.DataFrame([
        {**base, "model_name": daily.BAYES_MODEL,
         "flags": json.dumps(["shape_v1", "counts:corners_total_poisson_v1,cards_nb_v1"])},
        {**base, "model_name": daily.NO_SHAPE_MODEL, "flags": json.dumps(["shadow", "no_shape"])},
        {**base, "model_name": daily.DC_MODEL, "flags": json.dumps(["fast_track_model"])},
        {**base, "model_name": daily.ELO_MODEL, "flags": "[]"},
    ])


def test_only_the_markets_that_passed_are_kept():
    out = trial.trim(rows()).set_index("model_name")
    assert list(out.index) == [daily.BAYES_MODEL, daily.NO_SHAPE_MODEL, daily.ELO_MODEL]
    for col in ("p_over_2_5", "p_btts", "p_corners_over_9_5", "exp_corners_home"):
        assert out[col].isna().all()
    assert out.loc[daily.BAYES_MODEL, "p_home"] == 0.5
    assert out.loc[daily.BAYES_MODEL, "p_yellows_over_4_5"] == 0.4
    # The fix keeps expected goals; only the plain copy carries them, for the monthly refit.
    assert np.isnan(out.loc[daily.BAYES_MODEL, "exp_goals_home"])
    assert out.loc[daily.NO_SHAPE_MODEL, "exp_goals_home"] == 1.6
    assert json.loads(out.loc[daily.BAYES_MODEL, "intervals"]) == {"p_home": [0.4, 0.6]}
    assert (out["top_scorelines"] == "[]").all()


def test_flags_name_the_yellows_model_only_and_mark_the_trial():
    out = trial.trim(rows()).set_index("model_name")
    assert json.loads(out.loc[daily.BAYES_MODEL, "flags"]) == [
        "shape_v1", "counts:cards_nb_v1", "trial"]
    assert json.loads(out.loc[daily.ELO_MODEL, "flags"]) == ["trial"]


def test_empty_day_locks_nothing():
    assert trial.trim(pd.DataFrame()).empty


def test_trial_files_are_apart_from_live_files():
    live = {ledger.PREDICTIONS, ledger.RESULTS, shape.STORE, posterior_store.STORE}
    mine = {trial.LEDGER, trial.RESULTS, trial.REPORT, trial.SHAPE_STORE, trial.STORE}
    assert not live & mine
    assert trial.LEDGER.parent.name == "trial" and trial.STORE.name == "trial"
    assert set(trial.COMPETITIONS.values()) == {"SerieA", "Ligue1"}
