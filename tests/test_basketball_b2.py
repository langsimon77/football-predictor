"""Basketball phase B2: features, challengers and checks (no XGBoost here: it needs OpenMP)."""
from __future__ import annotations

import importlib
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from fp import ROOT

sys.path.insert(0, str(ROOT / "basketball"))
features = importlib.import_module("features")
challengers = importlib.import_module("challengers")
models = importlib.import_module("models")
locations = importlib.import_module("locations")
backtest_b2 = importlib.import_module("backtest_b2")

B1 = {"elo": {"k": 20, "home": 60, "carry": 0.75, "mov": True, "margin_scale_b": 0.04,
              "margin_sd": 12.0},
      "points": {"half_life": 120, "penalty": 3, "sd_home": 10.0, "sd_away": 10.0, "rho": 0.3}}
CITIES = pd.DataFrame({"club_title": [f"Club {i}" for i in range(6)],
                       "lat": [40.4, 41.4, 41.0, 37.98, 45.4, 54.9],
                       "lon": [-3.7, 2.2, 28.96, 23.73, 9.1, 23.9]})


def league(seed: int = 4, seasons: int = 2, noise: float = 8.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    clubs = [f"c{i}" for i in range(6)]
    strength = dict(zip(clubs, rng.normal(0, 5, 6), strict=True))
    rows = []
    start = date(2020, 10, 1)
    for s in range(seasons):
        for r in range(20):
            perm = rng.permutation(clubs)
            for h, a in zip(perm[::2], perm[1::2], strict=True):
                diff = 3 + strength[h] - strength[a]
                rows.append({"date": start + timedelta(days=200 * s + 4 * r), "season": s,
                             "home_id": h, "away_id": a,
                             "home_title": "Club " + h[1:], "away_title": "Club " + a[1:],
                             "home_pts": float(round(80 + diff / 2 + rng.normal(0, noise))),
                             "away_pts": float(round(80 - diff / 2 + rng.normal(0, noise)))})
    return pd.DataFrame(rows).sort_values("date", kind="stable").reset_index(drop=True)


def test_haversine_known_distance():
    assert features.haversine_km(40.4169, -3.7033, 41.3833, 2.1833) == pytest.approx(505, abs=5)
    assert features.haversine_km(1, 2, 1, 2) == pytest.approx(0.0)


def test_features_use_earlier_days_only():
    g = league()
    x = features.build_features(g, B1, CITIES)
    first = g["date"] == g["date"].min()
    assert (x.loc[first, ["form_home", "form_away", "played_home", "h_count"]] == 0).all().all()
    assert (x.loc[first, "rest_home"] == features.REST_CAP).all()
    changed = g.copy()
    day = g["date"].iloc[len(g) // 2]
    changed.loc[changed["date"] == day, "home_pts"] += 30
    y = features.build_features(changed, B1, CITIES)
    upto = (g["date"] <= day).to_numpy()
    assert np.allclose(x[upto].to_numpy(float), y[upto].to_numpy(float), equal_nan=True)
    assert not np.allclose(x[~upto].to_numpy(float), y[~upto].to_numpy(float), equal_nan=True)


def test_refit_blocks_start_each_season_and_every_28_days():
    g = league()
    rows = np.arange(len(g))
    blocks = challengers.refit_blocks(g, rows)
    ordinal = np.array([d.toordinal() for d in g["date"]])
    assert sum(len(m) for _, m in blocks) == len(g)
    for day, members in blocks:
        assert (ordinal[members] >= day).all() and (ordinal[members] < day + 28).all()
    assert len(blocks) == 2 * 3  # 20 rounds 4 days apart: 76 days per season, 3 blocks each


def test_ml_forecasts_never_see_their_own_block():
    g = league()
    x = features.build_features(g, B1, CITIES)
    rows = np.flatnonzero(g["season"] == 1)
    p = {"penalty": 1}
    before = challengers.ml_predict("C1", "margin", p, g, x, rows)
    first_day, members = challengers.refit_blocks(g, rows)[0]
    changed = g.copy()
    ordinal = np.array([d.toordinal() for d in g["date"]])
    changed.loc[ordinal >= first_day, "home_pts"] += 50  # only results in or after the block
    after = challengers.ml_predict("C1", "margin", p, changed, x, rows)
    assert np.allclose(before[members], after[members])


def test_kalman_tracks_strength_and_never_peeks():
    g = league(seasons=3, noise=4.0)
    out = challengers.kalman_run(g, drift=0.05, season_drift=5, sd_home=4, sd_away=4, rho=0.0)
    late = g["season"] == 2
    margin = (out["m_home"] - out["m_away"])[late]
    actual = (g["home_pts"] - g["away_pts"])[late]
    assert np.corrcoef(margin, actual)[0, 1] > 0.6
    changed = g.copy()
    day = g["date"].iloc[len(g) // 2]
    changed.loc[changed["date"] == day, "home_pts"] += 40
    again = challengers.kalman_run(changed, 0.05, 5, 4, 4, 0.0)
    upto = (g["date"] <= day).to_numpy()
    assert np.allclose(out[upto].to_numpy(), again[upto].to_numpy(), equal_nan=True)


def test_club_home_edges_shrink_to_the_b1_points_model():
    g = league()
    b1 = models.points_run(g, models.PointsSettings(120, 3))
    c7 = challengers.points_home_run(g, 120, 3, home_penalty=1e9)
    assert np.allclose(b1.to_numpy(), c7.to_numpy(), equal_nan=True, atol=1e-6)


def test_rolling_width_needs_100_games():
    ordinal = np.arange(300)
    errors = np.random.default_rng(5).normal(0, 7, 300)
    sd = backtest_b2.rolling_width(errors, ordinal, fallback=12.0)
    assert (sd[:100] == 12.0).all()               # fewer than 100 earlier games: tuning width
    assert sd[250] == pytest.approx(np.std(errors[:250]), rel=1e-9)


def test_99_interval_is_wider_than_95():
    rng = np.random.default_rng(6)
    diff = rng.normal(0, 1, 400)
    day = np.repeat(np.arange(100), 4)
    _, lo95, hi95 = models.bootstrap_mean(diff, day)
    _, lo99, hi99 = models.bootstrap_mean(diff, day, level=0.99)
    assert lo99 < lo95 and hi99 > hi95


def test_infobox_location_link():
    text = ("{{Infobox basketball club\n| location = [[Madrid]], Spain\n"
            "| arena = [[WiZink Center]]\n}}")
    assert locations.infobox_field(text, "location") == "Madrid"
    assert locations.infobox_field(text, "arena") == "WiZink Center"
    assert locations.infobox_field(text, "city") is None
