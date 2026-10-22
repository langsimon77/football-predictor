"""Task 6.2: the Europe pipeline's score grids, the blend reshape and club-name resolution."""
from __future__ import annotations

import importlib
import json
import sys

import numpy as np
import pandas as pd
import pytest

from fp import ROOT

sys.path.insert(0, str(ROOT / "pipeline_euro"))
dc = importlib.import_module("dc")
names = importlib.import_module("names")
evalkit = importlib.import_module("evalkit")


@pytest.mark.parametrize(("lh", "la"), [(0.3, 0.2), (1.4, 1.1), (2.9, 0.4), (4.5, 3.8)])
def test_score_grid_sums_to_one(lh, la):
    p3, o25, btts, M, _ = dc.probs(lh, la)
    assert M.sum() == pytest.approx(1)
    assert p3.sum() == pytest.approx(1)
    assert 0 < o25 < 1 and 0 < btts < 1
    G = evalkit.grids(np.array([lh]), np.array([la]), -0.05)
    assert G.sum() == pytest.approx(1)
    assert np.allclose(G[0], M)


def test_reshape_to_the_blend_keeps_totals():
    _, _, _, M, _ = dc.probs(1.6, 0.9)
    target = np.array([0.52, 0.27, 0.21])
    R = dc.reshape(M, target)
    i = np.arange(M.shape[0])
    hi, ai = np.meshgrid(i, i, indexing="ij")
    assert R.sum() == pytest.approx(1)
    assert [R[hi > ai].sum(), np.trace(R), R[hi < ai].sum()] == pytest.approx(list(target))
    home = hi > ai  # within a region, the shape is kept
    assert (R[home] / R[home].sum()) == pytest.approx(M[home] / M[home].sum())


def test_known_team_names_resolve():
    rows = []
    seen = [("Sparta Praha", "CZE", 6), ("Sparta Prague", "CZE", 2), ("Crvena Zvezda", "SRB", 5),
            ("Red Star Belgrade", "SRB", 1), ("Bayern Munchen", "GER", 6),
            ("Bayern Munich", "GER", 2), ("Real Madrid", "ESP", 6), ("Real Betis", "ESP", 5),
            ("Manchester United", "ENG", 6), ("Man Utd", "ENG", 1), ("FC Kobenhavn", "DEN", 5),
            ("FC Copenhagen", "DEN", 2)]
    for name, cc, n in seen:
        rows += [{"home": name, "hcc": cc, "away": "Other " + cc, "acc": cc}] * n
    R = names.resolve(pd.DataFrame(rows))
    assert R("Sparta Prague", "CZE") == R("Sparta Praha", "CZE")
    assert R("Red Star Belgrade", "SRB") == R("Crvena Zvezda", "SRB")
    assert R("Bayern Munich", "GER") == R("Bayern München", "GER")
    assert R("Man Utd", "ENG") == R("Manchester United", "ENG")
    assert R("FC Copenhagen", "DEN") == R("Kobenhavn", "DEN")
    assert R("Real Madrid", "ESP") != R("Real Betis", "ESP")


def test_no_fixture_left_unresolved():
    work = ROOT / "data" / "interim" / "euro"
    if not (work / "df.pkl").exists() or not (work / "fixtures.json").exists():
        pytest.skip("Europe sources not downloaded here (make euro)")
    df = pd.read_pickle(work / "df.pkl")
    R = names.resolve(pd.read_pickle(work / "raw.pkl"))
    known = set(df.H) | set(df.A)
    fx = json.loads((work / "fixtures.json").read_text())
    missing = [(f["home"], f["away"]) for f in fx
               if R(f["home"], f["hcc"]) not in known or R(f["away"], f["acc"]) not in known]
    assert not missing, missing
