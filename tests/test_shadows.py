"""Shadow rows and live tiers (Phase 4, approved 26 Sep 2026)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fp.ensemble import tiers
from fp.pipeline import shadows

NOW = pd.Timestamp("2026-10-09 04:41", tz="UTC")


class Stub:
    def __init__(self, p):
        self.p = np.array([p])

    def predict(self, rows):
        return self.p


def ledger_rows(with_bayes=True):
    base = {"match_id": "EPL_2627_arsenal_leeds", "league": "EPL", "lock_utc": NOW,
            "tiers": "{}", "flags": json.dumps(["late_lock"])}
    rows = [{**base, "model_name": "elo_v0", "p_home": 0.70, "p_draw": 0.19, "p_away": 0.11},
            {**base, "model_name": "dc_mle_v0", "p_home": 0.60, "p_draw": 0.25, "p_away": 0.15}]
    if with_bayes:
        rows.append({**base, "model_name": "dc_bayes_v1", "p_home": 0.62, "p_draw": 0.24,
                     "p_away": 0.14})
    return pd.DataFrame(rows)


STUBS = {"ordered_logit": Stub([0.63, 0.22, 0.15]), "multinomial": Stub([0.61, 0.24, 0.15]),
         "random_forest": Stub([0.66, 0.22, 0.12]), "xgboost": Stub([0.64, 0.24, 0.12])}
FEATURES = pd.DataFrame({"match_id": ["EPL_2627_arsenal_leeds"]})


def test_shadow_rows_and_stack_weights():
    out = shadows.add_shadows(ledger_rows(), STUBS, FEATURES).set_index("model_name")
    assert {"ordered_logit_v1", "multinomial_v1", "random_forest_v1", "xgboost_v1",
            "stack_v1"} <= set(out.index)
    models, weights = shadows.load_stack()
    probs = {"elo": [0.70, 0.19, 0.11], "dc": [0.60, 0.25, 0.15], "bdc": [0.62, 0.24, 0.14],
             **{k: v.p[0] for k, v in STUBS.items()}}
    expected = sum(w * np.array(probs[m]) for m, w in zip(models, weights, strict=True))
    got = out.loc["stack_v1", ["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
    assert got == pytest.approx(expected)
    assert got.sum() == pytest.approx(1.0)
    assert json.loads(out.loc["stack_v1", "flags"]) == ["late_lock", "shadow"]
    assert out.loc["xgboost_v1", "prediction_id"] == "EPL_2627_arsenal_leeds:xgboost_v1"


def test_no_stack_row_without_every_component():
    out = shadows.add_shadows(ledger_rows(with_bayes=False), STUBS, FEATURES)
    assert "stack_v1" not in set(out["model_name"])
    assert "multinomial_v1" in set(out["model_name"])


TH = {"1x2": tiers.Thresholds("1x2", high=0.58, low=0.44, width_max=0.16, disagree_max=0.07),
      "over_2_5": tiers.Thresholds("over_2_5", high=0.61, low=0.55, width_max=0.16),
      "yellows_over_4_5": tiers.Thresholds("yellows_over_4_5", high=0.76, low=0.60)}


def primary(**changes):
    row = {"league": "EPL", "p_home": 0.62, "p_draw": 0.24, "p_away": 0.14,
           "p_over_2_5": 0.44, "p_yellows_over_4_5": 0.20, "flags": "[]",
           "intervals": json.dumps({"p_home": [0.55, 0.69], "p_over_2_5": [0.36, 0.52]})}
    return {**row, **changes}


def test_worked_example_tiers():
    got = shadows.tiers_for_row(primary(), TH, np.array([0.631, 0.235, 0.134]))
    assert got == {"rule": "tiers_v1", "1x2": "High", "over_2_5": "Medium",
                   "yellows_over_4_5": "High"}


def test_promoted_flag_never_caps():
    got = shadows.tiers_for_row(primary(flags=json.dumps(["promoted_lt6:leeds"])), TH, None)
    assert got["1x2"] == "High"


def test_source_failure_caps_and_referee_adds_a_flag():
    got = shadows.tiers_for_row(
        primary(flags=json.dumps(["stale_source", "referee_unknown"])), TH, None)
    assert got["1x2"] == "Medium"
    assert got["yellows_over_4_5"] == "Low"  # two flags


def test_la_liga_cards_count_the_referee_as_unknown():
    got = shadows.tiers_for_row(primary(league="LaLiga"), TH, None)
    assert got["yellows_over_4_5"] == "Medium"
    assert got["1x2"] == "High"


def test_disagreement_drops_one_tier():
    got = shadows.tiers_for_row(primary(), TH, np.array([0.50, 0.30, 0.20]))
    assert got["1x2"] == "Medium"


def test_add_tiers_fills_only_the_primary_row():
    rows = shadows.add_shadows(ledger_rows(), STUBS, FEATURES)
    rows["p_over_2_5"] = np.nan
    rows["intervals"] = None
    out = shadows.add_tiers(rows, "dc_bayes_v1").set_index("model_name")
    assert json.loads(out.loc["dc_bayes_v1", "tiers"])["1x2"] in tiers.TIERS
    assert out.loc["elo_v0", "tiers"] == "{}"
