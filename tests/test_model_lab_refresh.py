"""The checks a routine runs before it copies the daily data files to the Model Lab page."""

import json
import sys
from datetime import UTC, datetime

import pytest

from fp import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import model_lab_refresh as refresh  # noqa: E402

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def write(folder, built="2026-11-20 06:30 UTC", bets=None, seed=None):
    gw = {"built": built, "data_as_of": "2026-11-20T05:10Z", "up": [], "trial": {}, "ucl": {},
          "pairs": {"matches": {}}, "clubs": [], "bets": bets, "pad": "x" * 60_000}
    core = {"bt": {}, "sim": {}, "ev": {}, "pad": "x" * 600_000}
    for name, obj in (("gameweek", gw), ("core", core), ("history-seed", seed or [])):
        (folder / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")


def test_sound_files_newer_than_the_page_are_published(tmp_path):
    write(tmp_path)
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"built": "2026-11-19 06:30 UTC"}), encoding="utf-8")
    assert refresh.check(tmp_path, NOW, live).startswith("PUBLISH")
    assert refresh.check(tmp_path, NOW, None).startswith("PUBLISH")


def test_the_same_build_is_not_published_twice(tmp_path):
    write(tmp_path)
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"built": "2026-11-20 06:30 UTC"}), encoding="utf-8")
    assert refresh.check(tmp_path, NOW, live).startswith("SKIP")


@pytest.mark.parametrize("change, message", [
    ({"built": "2026-11-18 06:30 UTC"}, "hours ago"),
    ({"built": "2026-11-21 06:30 UTC"}, "future"),
    ({"bets": {"n": 3}}, "bets"),
])
def test_stale_future_or_private_files_are_refused(tmp_path, change, message):
    write(tmp_path, **change)
    with pytest.raises(ValueError, match=message):
        refresh.check(tmp_path, NOW, None)


def test_a_missing_or_cut_off_file_is_refused(tmp_path):
    write(tmp_path)
    (tmp_path / "core.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="too small"):
        refresh.check(tmp_path, NOW, None)
    (tmp_path / "core.json").unlink()
    assert refresh.main(["check", str(tmp_path), "--now", "2026-11-20 09:00"]) == 1


def test_a_banned_dash_is_refused(tmp_path):
    write(tmp_path, seed=[{"match_id": "m", "h": "A " + chr(0x2013) + " B"}])
    with pytest.raises(ValueError, match="dash"):
        refresh.check(tmp_path, NOW, None)


def seed_doc(mid, kickoff, calls=True):
    return {"match_id": mid, "lg": "Premier League", "h": "A", "a": "B", "kickoff": kickoff,
            "calls": [{"mkt": "result", "k": "H", "label": "A win", "p": 0.5, "result": None}]
            if calls else [], "made_from": "2026-11-20T05:10Z", "score": None,
            "settled_utc": None}


def test_history_records_only_for_final_forecasts_not_yet_recorded(tmp_path):
    write(tmp_path, seed=[
        seed_doc("soon", "2026-11-21T08:00Z"),      # 23 hours ahead: final
        seed_doc("later", "2026-11-22T15:00Z"),     # 54 hours ahead: may still change
        seed_doc("played", "2026-11-18T20:00Z"),    # 2 days ago: still wanted
        seed_doc("old", "2026-11-10T20:00Z"),       # too old
        seed_doc("have", "2026-11-21T08:00Z"),      # already recorded
        seed_doc("empty", "2026-11-21T08:00Z", calls=False),
    ])
    docs = refresh.history(tmp_path, {"have"}, NOW)
    assert [d["match_id"] for d in docs] == ["soon", "played"]
    assert docs[0]["created_utc"] == "2026-11-20T09:00Z"
    assert docs[0]["calls"][0]["result"] is None

    out = tmp_path / "new"
    have = tmp_path / "have.json"
    have.write_text(json.dumps(["have"]), encoding="utf-8")
    code = refresh.main(["history", str(tmp_path), "--have", str(have), "--out", str(out),
                         "--now", "2026-11-20 09:00"])
    assert code == 0 and sorted(p.name for p in out.iterdir()) == ["played.json", "soon.json"]


def test_an_extra_xg_test_file_does_not_block_the_check(tmp_path):
    write(tmp_path)
    (tmp_path / "xg_test.json").write_text(json.dumps({"arms": {}}), encoding="utf-8")
    (tmp_path / "tips.json").write_text(json.dumps({"free": []}), encoding="utf-8")
    assert refresh.check(tmp_path, NOW, None).startswith("PUBLISH")
