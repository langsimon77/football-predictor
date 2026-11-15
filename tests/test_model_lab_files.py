"""The Model Lab page reads three data files. The builder writes them for the daily job."""

import json
import sys

import pytest

from fp import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import build_model_lab as lab  # noqa: E402


def snapshot() -> dict:
    def pick(k, label, p):
        return {"k": k, "label": label, "p": p}

    match = {"lg": "Premier League", "h": "Arsenal", "a": "Everton", "kickoff": "2026-11-21T15:00Z",
             "picks": [pick("H", "Arsenal win", 0.61), pick("D", "Draw", 0.22),
                       pick("A", "Everton win", 0.17), pick("G>2.5", "Over 2.5 goals", 0.44),
                       pick("G<2.5", "Under 2.5 goals", 0.56),
                       pick("BTTS", "Both teams score", 0.5),
                       pick("NoBTTS", "Not both teams score", 0.5)]}
    later = dict(match, h="Leeds", a="Fulham", kickoff="2026-11-22T14:00Z",
                 picks=[pick("H", "Leeds win", 0.3), pick("D", "Draw", 0.3),
                        pick("A", "Fulham win", 0.4)])
    return {"built": "2026-11-15 06:21 UTC", "data_as_of": "2026-11-14T07:02Z",
            "model_version": "abc", "clubs": ["Arsenal"], "up": [], "trial": {}, "ucl": {},
            "uel": {}, "uecl": {}, "basketball": {}, "bets": None,
            "pairs": {"matches": {"m2": later, "m1": match}},
            "bt": {"x": 1}, "sim": {"y": 2}, "ev": {"z": 3}}


def test_every_block_lands_in_exactly_one_file():
    files = lab.page_files(snapshot())
    assert set(files) == {"gameweek", "core", "history-seed"}
    assert set(files["core"]) == {"bt", "sim", "ev"}
    assert "pairs" in files["gameweek"] and "bt" not in files["gameweek"]
    assert files["gameweek"]["bets"] is None  # the private bet summary never comes from here


def test_a_new_block_must_be_assigned_to_a_file():
    data = snapshot()
    data["surprise"] = {}
    with pytest.raises(SystemExit, match="surprise"):
        lab.page_files(data)


def test_history_seed_has_the_main_call_per_market_in_kickoff_order():
    seed = lab.page_files(snapshot())["history-seed"]
    assert [d["match_id"] for d in seed] == ["m1", "m2"]
    first = seed[0]
    assert first["h"] == "Arsenal" and first["made_from"] == "2026-11-14T07:02Z"
    assert first["score"] is None and first["settled_utc"] is None
    calls = {c["mkt"]: c for c in first["calls"]}
    assert calls["result"]["k"] == "H" and calls["result"]["label"] == "Arsenal win"
    assert calls["goals"]["k"] == "G<2.5" and calls["goals"]["p"] == 0.56
    assert calls["btts"]["k"] == "BTTS"  # a tie goes to the first side, as on the page
    assert "corners" not in calls  # no corner forecast for this match
    assert all(c["result"] is None for c in first["calls"])
    assert [c["k"] for c in seed[1]["calls"]] == ["A"]


def test_files_are_written_as_compact_json(tmp_path):
    sizes = lab.write_page_files(snapshot(), tmp_path)
    assert set(sizes) == {"gameweek", "core", "history-seed"}
    for name in sizes:
        text = (tmp_path / f"{name}.json").read_text(encoding="utf-8")
        assert json.loads(text) is not None and "\n" not in text
