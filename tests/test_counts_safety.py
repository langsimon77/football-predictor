"""Safety factor for corners and yellows picks (Lang's request, 14 Oct 2026)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import counts_safety as cs  # noqa: E402


def test_wilson_lower_bound():
    assert cs.wilson_lower(77, 100) == pytest.approx(0.7121, abs=1e-3)  # one-sided 90%
    assert cs.wilson_lower(0, 10) == pytest.approx(0.0, abs=1e-12)
    assert np.isnan(cs.wilson_lower(0, 0))
    # More evidence, tighter bound, same rate.
    assert cs.wilson_lower(770, 1000) > cs.wilson_lower(77, 100)


def test_safe_chance_is_never_above_the_model_and_needs_a_record():
    table = pd.DataFrame({"fam": ["yellows", "yellows"], "band": [0.75, 0.6],
                          "lower90": [0.73, 0.70]})
    picks = pd.DataFrame({"fam": ["yellows", "yellows", "corners"], "band": [0.75, 0.6, 0.6],
                          "p": [0.79, 0.62, 0.61]})
    safe = cs.safe_chance(picks, table)
    assert safe[0] == pytest.approx(0.73)  # the record is the tighter limit
    assert safe[1] == pytest.approx(0.62)  # the model is already below the record's low end
    assert np.isnan(safe[2])  # no record for this market: no safe chance


def test_s1_counts_a_cell_as_safe_when_picks_beat_the_safe_chance():
    rng = np.random.default_rng(0)
    rows = []
    for season in (2021, 2022, 2023, 2024, 2025):
        for _ in range(400):
            rows.append({"fam": "yellows", "season": season, "p": 0.77, "band": 0.75,
                         "hit": bool(rng.random() < 0.77)})
    out = cs.check_s1(pd.DataFrame(rows))
    assert out["n_cells"] == 1 and out["pass"]
