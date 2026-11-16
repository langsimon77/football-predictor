"""The recalibration test: fitted on earlier seasons only, scored as a paired difference."""

import sys

import numpy as np
import pandas as pd

from fp import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import recalibration_test as rc  # noqa: E402


def frame(seed: int, bold: float) -> pd.DataFrame:
    """Forecasts that are too bold by a known factor: true log-odds = bold * forecast."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in (2021, 2022, 2023, 2024, 2025):
        z = rng.normal(0, 1.0, 600)
        truth = 1 / (1 + np.exp(-bold * z))
        rows.append(pd.DataFrame({"league": "EPL", "season": season, "market": "over 2.5 goals",
                                  "p": 1 / (1 + np.exp(-z)),
                                  "happened": (rng.random(600) < truth).astype(float)}))
    return pd.concat(rows, ignore_index=True)


def test_fit_recovers_a_known_slope():
    f = frame(1, bold=0.5)
    a, b = rc.fit(f["p"].to_numpy(), f["happened"].to_numpy())
    assert abs(b - 0.5) < 0.08 and abs(a) < 0.08


def test_each_season_is_fitted_on_earlier_seasons_only():
    f = frame(2, bold=0.5)
    wf = rc.walk_forward(f)
    assert sorted(wf["season"].unique()) == [2023, 2024, 2025]
    # Changing a later season's results must not change an earlier season's new forecasts.
    g = f.copy()
    g.loc[g["season"] == 2025, "happened"] = 1.0
    wf2 = rc.walk_forward(g)
    for season in (2023, 2024, 2025):
        a = wf.loc[wf["season"] == season, "p_new"].to_numpy()
        b = wf2.loc[wf2["season"] == season, "p_new"].to_numpy()
        assert np.allclose(a, b)  # 2025's forecasts use 2021 to 2024 only, so they hold too


def test_bold_forecasts_pass_and_honest_forecasts_do_not():
    bold = rc.score(rc.walk_forward(frame(3, bold=0.5)))["over 2.5 goals"]
    assert bold["pass"] and bold["pooled"]["hi"] < 0
    assert abs(bold["slope_after"] - 1) < abs(bold["slope_before"] - 1)
    honest = rc.score(rc.walk_forward(frame(4, bold=1.0)))["over 2.5 goals"]
    assert not honest["pass"]
