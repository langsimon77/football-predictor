"""Champions League daily step (fp.pipeline.ucl), on toy data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fp import ledger
from fp.pipeline import trial, ucl
from tests.test_club_dc import toy


def context(tmp_path: Path) -> tuple[ucl.UclContext, pd.Timestamp]:
    past, country = toy()
    now = past["result_available_utc"].max() + pd.Timedelta(days=10)
    # x1 plays only in Europe (a league without domestic data).
    extra = []
    for i, opp in enumerate(["s1", "w1", "s2", "w2"]):
        ko = now - pd.Timedelta(days=40 - 7 * i)
        extra.append({"match_id": f"e{i}", "competition": "UCL", "season": 2024,
                      "kind": "europe", "date": ko.date(), "kickoff_utc": ko,
                      "result_available_utc": ko + pd.Timedelta(hours=3), "home_id": "x1",
                      "away_id": opp, "home_goals": 1.0, "away_goals": 1.0,
                      "neutral": False, "round": "LEAGUE_STAGE 1"})
    past = pd.concat([past, pd.DataFrame(extra)], ignore_index=True)
    country["x1"] = "XXX"

    def game(mid: str, home: str, away: str, hours: float, goals: float | None = None) -> dict:
        ko = now + pd.Timedelta(hours=hours)
        return {"match_id": mid, "competition": "UCL", "kind": "europe", "season": 2026,
                "date": ko.date(), "kickoff_utc": ko,
                "result_available_utc": ko + pd.Timedelta(hours=3), "home_id": home,
                "away_id": away, "home_goals": goals, "away_goals": goals, "neutral": False,
                "round": "LEAGUE_STAGE 3"}

    current = pd.DataFrame([
        game("done", "s3", "w3", -30, 2.0),
        game("in30h", "s1", "w4", 30),
        game("in20h", "x1", "s4", 20),
        game("in60h", "w1", "s2", 60),
    ])
    current[["home_goals", "away_goals"]] = current[["home_goals", "away_goals"]].astype("Float64")
    ctx = ucl.UclContext(matches=past, current=current, countries=country,
                         ledger_path=tmp_path / "predictions.parquet",
                         results_path=tmp_path / "results.parquet",
                         upcoming_path=tmp_path / "upcoming.parquet",
                         report_path=tmp_path / "latest.md")
    return ctx, now


def test_locks_the_next_48_hours_once(tmp_path):
    ctx, now = context(tmp_path)
    new = ucl.run_once(now, ctx)
    assert set(new["match_id"]) == {"in30h", "in20h"}
    assert (new["model_name"] == ucl.MODEL).all() and (new["league"] == "UCL").all()
    by = new.set_index("match_id")
    assert by.loc["in20h", "late_lock"] and not by.loc["in30h", "late_lock"]
    for p in ("p_home", "p_over_1_5", "p_over_2_5", "p_over_3_5"):
        assert by[p].between(0, 1).all()
    assert by["p_btts"].isna().all()
    locked = ledger.load(ctx.ledger_path)
    ledger.verify_chain(locked)
    assert len(locked) == 2
    assert ucl.run_once(now + pd.Timedelta(hours=1), ctx).empty


def test_flags_clubs_rated_from_europe_only(tmp_path):
    ctx, now = context(tmp_path)
    by = ucl.run_once(now, ctx, dry_run=True).set_index("match_id")
    assert json.loads(by.loc["in20h", "flags"]) == ["ucl", "europe_only_rating:x1", "late_lock"]
    assert json.loads(by.loc["in30h", "flags"]) == ["ucl"]
    assert not ctx.ledger_path.exists()


def test_records_results_and_exports_upcoming(tmp_path):
    ctx, now = context(tmp_path)
    ucl.run_once(now, ctx)
    up = pd.read_parquet(ctx.upcoming_path).set_index("match_id")
    assert set(up.index) == {"in30h", "in20h", "in60h"}
    assert up.loc["in30h", "locked"] and not up.loc["in60h", "locked"]
    assert pd.isna(up.loc["in60h", "lock_utc"])
    assert up.loc["in20h", "europe_only"] == "x1" and up.loc["in30h", "europe_only"] == ""
    assert (up["round"] == "LEAGUE_STAGE 3").all()

    later = now + pd.Timedelta(hours=34)
    ctx.current.loc[ctx.current["match_id"] == "in30h", ["home_goals", "away_goals"]] = [3.0, 1.0]
    ucl.run_once(later, ctx)
    res = pd.read_parquet(ctx.results_path)
    assert list(res["match_id"]) == ["in30h"]  # "done" was never locked
    assert res.iloc[0]["home_goals"] == 3 and res.iloc[0]["source"] == "football_data_org"


def test_ucl_files_are_apart_from_live_and_trial_files():
    mine = {ucl.LEDGER, ucl.RESULTS, ucl.UPCOMING, ucl.REPORT}
    assert not mine & {ledger.PREDICTIONS, ledger.RESULTS, trial.LEDGER, trial.RESULTS,
                       trial.UPCOMING, trial.REPORT}
    assert ucl.LEDGER.parent.name == "ucl"


def test_model_lab_shows_only_tested_markets_for_the_champions_league():
    import sys as _sys
    from pathlib import Path as _Path
    from types import SimpleNamespace

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "scripts"))
    import build_model_lab

    r = SimpleNamespace(p_home=0.5, p_draw=0.3, p_away=0.2, p_over_1_5=0.8, p_over_2_5=0.55,
                        p_over_3_5=0.3)
    picks = build_model_lab.ucl_picks(r, "Bayern Munich", "PSV")
    assert {p["fam"] for p in picks} == {"result", "dc", "dnb", "goals"}
    assert all(p["g"] == "ucl" for p in picks)
    by = {p["k"]: p for p in picks}
    assert by["G>2.5"]["label"] == "3 or more goals" and by["G<2.5"]["p"] == 0.45
    assert by["G<1.5"]["label"] == "1 goal or fewer"
    assert build_model_lab.ucl_round("LEAGUE_STAGE 3") == "League phase, matchday 3"
    assert build_model_lab.ucl_round("LAST_16") == "Round of 16"
    names = build_model_lab.ucl_names({"arsenal": "Arsenal"})
    assert names["arsenal"] == "Arsenal" and names["ger_bayern_munich"] == "Bayern Munich"
