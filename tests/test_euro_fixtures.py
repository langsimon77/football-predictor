"""pipeline_euro/fixtures.py: two sources, verified only when they agree."""
from __future__ import annotations

import importlib
import sys
from datetime import date

from fp import ROOT

sys.path.insert(0, str(ROOT / "pipeline_euro"))
fixtures = importlib.import_module("fixtures")

ALIAS = {"sparta prague": "sparta praha"}


def R(name, cc):
    n = name.lower()
    return cc + ":" + ALIAS.get(n, n)


def w(home, hcc, away, acc, md, hg=None, ag=None, day=None):
    return {"comp": "UEL", "matchday": md, "home": home, "hcc": hcc, "away": away, "acc": acc,
            "date": day, "hg": hg, "ag": ag}


def hr(day, home, hcc, away, acc, hg, ag):
    return {"comp": "UEL", "date": day, "home": home, "hcc": hcc, "away": away, "acc": acc,
            "hg": hg, "ag": ag}


def hf(ko, home, hcc, away, acc):
    return {"comp": "UEL", "kickoff": ko, "home": home, "hcc": hcc, "away": away, "acc": acc,
            "round": "League phase, matchday 3"}


HAND_RES = [hr("2026-09-16", "Ararat", "ARM", "Sparta Praha", "CZE", 1, 4),
            hr("2026-09-16", "Omonia", "CYP", "Celta", "ESP", 1, 0),
            hr("2026-10-15", "Lyon", "FRA", "Palace", "ENG", 3, 2)]
HAND_FIX = [hf("2026-10-22T16:45Z", "Juventus", "ITA", "Rennes", "FRA"),
            hf("2026-10-23T19:00Z", "Only", "AUT", "List", "BEL")]
WIKI = [
    w("Ararat", "ARM", "Sparta Prague", "CZE", 1, 1, 4),          # agrees (through the alias)
    w("Omonia", "CYP", "Celta", "ESP", 1, 2, 0),                  # the scores disagree
    w("Benfica", "POR", "Celtic", "SCO", 1, 4, 1),                # Wikipedia only: matchday date
    w("Juventus", "ITA", "Rennes", "FRA", 3, day="2026-10-22"),   # agrees, time from list
    w("Hoffenheim", "GER", "Lyon", "FRA", 3, day="2026-10-22"),   # Wikipedia only, summer
    w("Celje", "SVN", "Salzburg", "AUT", 4, day="2026-10-29"),    # Wikipedia only, winter
]


def test_cross_check():
    out = fixtures.collect(R, date(2026, 10, 22), horizon_days=10, wiki=WIKI,
                           hand_results=HAND_RES, hand_fixtures=HAND_FIX)
    rep = out["report"]
    assert rep["results"]["conflicts"] == [
        {"key": ["UEL", "CYP:omonia", "ESP:celta"], "list": [1, 0], "wikipedia": [2, 0]}]
    res = {(r["home"], r["away"]): r for r in out["results"]}
    ara = res[("Ararat", "Sparta Prague")]
    assert ara["verified"] and ara["date"] == "2026-09-16"
    assert ("Omonia", "Celta") not in res                                   # left out of training
    ben = res[("Benfica", "Celtic")]
    assert not ben["verified"] and ben["date"] == "2026-09-16"
    lyo = res[("Lyon", "Palace")]
    assert not lyo["verified"] and lyo["sources"] == ["list"]
    up = {(f["home"], f["away"]): f for f in out["upcoming"]}
    juv = up[("Juventus", "Rennes")]
    assert juv["verified"] and juv["kickoff"] == "2026-10-22T16:45Z"
    hof = up[("Hoffenheim", "Lyon")]
    assert not hof["verified"] and not hof["time_confirmed"]
    assert hof["kickoff"] == "2026-10-22T14:30Z"                      # 16:30 summer time
    assert up[("Celje", "Salzburg")]["kickoff"] == "2026-10-29T15:30Z"  # 16:30 winter time
    assert not up[("Only", "List")]["verified"] and up[("Only", "List")]["sources"] == ["list"]
