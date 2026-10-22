"""data/markets/markets.json is the single definition of every pick: settle rules, labels and
families. These tests check the rules on hand-picked scores, and that the code which builds
picks (scripts/pairs_lab.py, scripts/build_model_lab.py) agrees with the definition."""
from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pytest

from fp import ROOT
from fp import markets_gen as M

sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TABLE = [
    # (code, score, expected)
    ("H", {"hg": 2, "ag": 1}, "won"),
    ("H", {"hg": 0, "ag": 0}, "lost"),
    ("D", {"hg": 0, "ag": 0}, "won"),
    ("D", {"hg": 3, "ag": 3}, "won"),
    ("A", {"hg": 3, "ag": 3}, "lost"),
    ("A", {"hg": 0, "ag": 2}, "won"),
    ("1X", {"hg": 3, "ag": 3}, "won"),
    ("X2", {"hg": 2, "ag": 1}, "lost"),
    ("12", {"hg": 0, "ag": 0}, "lost"),
    ("12", {"hg": 4, "ag": 4}, "lost"),
    ("12", {"hg": 1, "ag": 0}, "won"),
    ("EH+2H", {"hg": 0, "ag": 1}, "won"),
    ("EH+2H", {"hg": 0, "ag": 2}, "lost"),
    ("EH+2A", {"hg": 3, "ag": 1}, "lost"),
    ("EH-1H", {"hg": 2, "ag": 0}, "won"),
    ("EH-1H", {"hg": 2, "ag": 1}, "lost"),
    ("EH-1A", {"hg": 1, "ag": 3}, "won"),
    ("DNB-H", {"hg": 1, "ag": 1}, "void"),
    ("DNB-H", {"hg": 2, "ag": 1}, "won"),
    ("DNB-H", {"hg": 0, "ag": 1}, "lost"),
    ("DNB-A", {"hg": 0, "ag": 0}, "void"),
    ("DNB-A", {"hg": 0, "ag": 1}, "won"),
    ("G>0.5", {"hg": 0, "ag": 0}, "lost"),
    ("G<0.5", {"hg": 0, "ag": 0}, "won"),
    ("G>2.5", {"hg": 3, "ag": 3}, "won"),
    ("G<2.5", {"hg": 1, "ag": 1}, "won"),
    ("G<2.5", {"hg": 2, "ag": 1}, "lost"),
    ("G<6.5", {"hg": 4, "ag": 1}, "won"),
    ("G>6.5", {"hg": 4, "ag": 3}, "won"),
    ("BTTS", {"hg": 3, "ag": 3}, "won"),
    ("BTTS", {"hg": 0, "ag": 0}, "lost"),
    ("NoBTTS", {"hg": 2, "ag": 0}, "won"),
    ("C>9.5", {"hg": 1, "ag": 0, "corners": 10}, "won"),
    ("C>9.5", {"hg": 1, "ag": 0, "corners": 9}, "lost"),
    ("C<9.5", {"hg": 1, "ag": 0, "corners": 9}, "won"),
    ("C>9.5", {"hg": 1, "ag": 0}, None),
    ("Y>4.5", {"hg": 0, "ag": 0, "yellows": 5}, "won"),
    ("Y<4.5", {"hg": 0, "ag": 0, "yellows": 5}, "lost"),
    ("Y>4.5", {"hg": 0, "ag": 0}, None),
    ("H", {}, None),
    ("DNB-H", {}, None),
]


@pytest.mark.parametrize(("code", "score", "want"), TABLE)
def test_settle_rules(code, score, want):
    assert M.settle(code, score) == want


def test_every_code_has_family_market_label_and_book():
    for code, m in M.MARKETS.items():
        assert m["family"] and m["market"] and m["label"] and len(m["book"]) == 2, code


def test_pairs_lab_agrees_with_the_definition():
    pl = _load("pairs_lab")
    rng = np.random.default_rng(3)
    mat = rng.random((11, 11))
    mat /= mat.sum()
    cpmf, ypmf = rng.random(25), rng.random(15)
    picks = pl.picks(mat, cpmf, ypmf, "Home", "Away")
    i, j = np.meshgrid(np.arange(11), np.arange(11), indexing="ij")
    cpmf, ypmf = cpmf / cpmf.sum(), ypmf / ypmf.sum()
    for pk in picks:
        k = pk["k"]
        assert pk["label"] == M.label(k, "Home", "Away"), k
        assert pk["fam"] == M.MARKETS[k]["family"], k
        if pk["fam"] in ("corners", "yellows"):
            pmf, stat = (cpmf, "corners") if pk["fam"] == "corners" else (ypmf, "yellows")
            want = sum(pmf[n] for n in range(len(pmf))
                       if M.settle(k, {"hg": 0, "ag": 0, stat: n}) == "won")
        else:
            won = np.vectorize(
                lambda a, b, k=k: M.settle(k, {"hg": int(a), "ag": int(b)}) == "won")(i, j)
            want = mat[won].sum()
        assert pk["p"] == pytest.approx(want), k


def test_model_lab_pick_builders_agree():
    bl = _load("build_model_lab")

    class R:
        p_home, p_draw, p_away = 0.5, 0.3, 0.2
        p_over_1_5, p_over_2_5, p_over_3_5 = 0.7, 0.5, 0.3
        p_yellows_over_3_5, p_yellows_over_4_5, p_yellows_over_5_5 = 0.6, 0.4, 0.2

    built = (bl.result_picks(R, "Home", "Away") + bl.ucl_picks(R, "Home", "Away")
             + bl.trial_picks(R, "Home", "Away"))
    for pk in built:
        assert pk["label"] == M.label(pk["k"], "Home", "Away"), pk["k"]
        assert pk["fam"] == M.MARKETS[pk["k"]]["family"], pk["k"]
