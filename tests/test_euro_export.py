"""pipeline_euro/export.py: started matches keep their last forecast; new ones are written."""
from __future__ import annotations

import importlib
import json
import sys

from fp import ROOT


def run(tmp_path, monkeypatch, now, pred, rec, old=None):
    monkeypatch.setenv("EURO_OUT", str(tmp_path))
    monkeypatch.setenv("EURO_WORK", str(tmp_path / "w"))
    monkeypatch.setenv("EURO_SOURCES", str(tmp_path / "s"))
    monkeypatch.setenv("EURO_NOW", now)
    sys.path.insert(0, str(ROOT / "pipeline_euro"))
    for m in ("paths", "export"):
        sys.modules.pop(m, None)
    export = importlib.import_module("export")
    (tmp_path / "pred.json").write_text(json.dumps(pred))
    (tmp_path / "eurrec.json").write_text(json.dumps(rec))
    if old:
        (tmp_path / "euro_gameweek.json").write_text(json.dumps(old["gw"]))
        (tmp_path / "history_seed.json").write_text(json.dumps(old["hist"]))
    export.main()
    return (json.loads((tmp_path / "euro_gameweek.json").read_text()),
            json.loads((tmp_path / "history_seed.json").read_text()))


def row(mid, ko, p):
    return {"id": mid, "kickoff": ko, "p": p}


def test_started_matches_are_never_rewritten(tmp_path, monkeypatch):
    rec = {"test": {"n": 1}, "safety": {}, "record": {}}
    ka, kb = "2026-10-22T16:45Z", "2026-10-29T16:45Z"
    rows = [row("A", ka, [500, 300, 200]), row("B", kb, [400, 300, 300])]
    pred1 = {"out": {"uel": rows, "uecl": []},
             "pairs": {"A": {"kickoff": ka, "picks": [1]}, "B": {"kickoff": kb, "picks": [1]}},
             "hist": [{"match_id": "A", "kickoff": ka, "calls": [1]},
                      {"match_id": "B", "kickoff": kb, "calls": [1]}]}
    gw, hist = run(tmp_path, monkeypatch, "2026-10-22T09:00Z", pred1, rec)
    assert [r["id"] for r in gw["uel"]["rows"]] == ["A", "B"]
    # After A kicked off, a rerun brings changed numbers for both: A must stay as it was.
    pred2 = json.loads(json.dumps(pred1))
    pred2["out"]["uel"][0]["p"] = [100, 100, 800]
    pred2["out"]["uel"][1]["p"] = [600, 200, 200]
    pred2["pairs"]["A"]["picks"] = [9]
    pred2["hist"][0]["calls"] = [9]
    gw2, hist2 = run(tmp_path, monkeypatch, "2026-10-22T17:00Z", pred2, rec,
                     old={"gw": gw, "hist": hist})
    rows = {r["id"]: r for r in gw2["uel"]["rows"]}
    assert rows["A"]["p"] == [500, 300, 200] and rows["B"]["p"] == [600, 200, 200]
    assert gw2["pairs_matches"]["A"]["picks"] == [1]
    assert {h["match_id"]: h["calls"] for h in hist2}["A"] == [1]
    # A started match missing from a later prediction is still kept for a few days.
    pred3 = json.loads(json.dumps(pred2))
    pred3["out"]["uel"] = pred3["out"]["uel"][1:]
    gw3, _ = run(tmp_path, monkeypatch, "2026-10-23T08:00Z", pred3, rec,
                 old={"gw": gw2, "hist": hist2})
    assert [r["id"] for r in gw3["uel"]["rows"]] == ["A", "B"]
