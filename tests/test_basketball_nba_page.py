"""NBA cards for the Model Lab (basketball/nba_page.py) on a toy schedule."""
from __future__ import annotations

import importlib
import sys

import numpy as np
import pandas as pd

from fp import ROOT

sys.path.insert(0, str(ROOT / "basketball"))
nba = importlib.import_module("nba_page")


def schedule(now: pd.Timestamp) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    strength = {"A": 8.0, "B": 2.0, "C": -2.0, "D": -8.0}
    rows = []
    for k in range(120):
        t = now - pd.Timedelta(days=120 - k)
        h, a = rng.choice(list(strength), 2, replace=False)
        margin = strength[h] - strength[a] + 3 + rng.normal(0, 10)
        hs = 110 + margin / 2
        rows.append({"gid": f"g{k}", "date": t.strftime("%Y-%m-%dT%H:%MZ"), "home": h, "away": a,
                     "hs": round(hs), "as_": round(hs - margin) - (1 if round(margin) == 0 else 0),
                     "neutral": False})
    for k, (h, a, hours) in enumerate([("A", "D", 20), ("D", "A", 44), ("B", "C", 400)]):
        t = now + pd.Timedelta(hours=hours)
        rows.append({"gid": f"u{k}", "date": t.strftime("%Y-%m-%dT%H:%MZ"), "home": h, "away": a,
                     "hs": np.nan, "as_": np.nan, "neutral": False})
    return pd.DataFrame(rows)


def test_feed_rows_and_favourites():
    now = pd.Timestamp("2026-11-14 18:00", tz="UTC")
    out = nba.feed(nba.prep(schedule(now)), now)
    rows = {r["id"]: r for r in out["rows"]}
    assert set(rows) == {"NBA_202627_u0", "NBA_202627_u1"}  # the third game is beyond 8 days
    assert rows["NBA_202627_u0"]["p"] > 0.8 and rows["NBA_202627_u1"]["p"] < 0.5
    assert rows["NBA_202627_u0"]["locked"] and not rows["NBA_202627_u1"]["locked"]  # 36 hours
    assert rows["NBA_202627_u0"]["margin"][0] > 0 and rows["NBA_202627_u0"]["total"][1] > 0
    assert out["test"]["NBA"]["games"] == 1423 and "twice a day" in out["test"]["NBA"]["note"]


def test_back_to_back_and_normal_cdf():
    d = nba.prep(pd.DataFrame([
        {"date": "2026-11-10T00:00Z", "home": "A", "away": "B", "hs": 100, "as_": 90,
         "neutral": False},
        {"date": "2026-11-11T00:00Z", "home": "A", "away": "C", "hs": np.nan, "as_": np.nan,
         "neutral": False}]))
    assert d["b2b_h"].tolist() == [0.0, 1.0] and d["b2b_a"].tolist() == [0.0, 0.0]
    assert abs(nba.ncdf(0) - 0.5) < 1e-12 and abs(nba.ncdf(1.96) - 0.975) < 1e-3
