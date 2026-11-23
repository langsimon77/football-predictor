"""The hidden xG test file: paired mean change in home, draw, away log loss, no verdict."""

import json
import math
import sys

import pandas as pd

from fp import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import make_xg_test as xt  # noqa: E402

NOW = pd.Timestamp("2026-12-01T07:30:00Z")
B = pd.Timestamp("2026-11-24T06:00:00Z")      # after the part B start
A = pd.Timestamp("2026-10-01T06:00:00Z")      # before it
CONTROL = "dc_bayes_v1_noshape"
JOINT = "dc_bayes_xg_joint_v1"
BLEND = "dc_bayes_xg_blend_v1"


def pred(match, model, probs, lock=B, league="EPL", degraded=False):
    h, d, a = probs
    return {"model_name": model, "match_id": match, "league": league, "lock_utc": lock,
            "p_home": h, "p_draw": d, "p_away": a, "p_over_2_5": 0.5, "p_btts": 0.5,
            "degraded": degraded}


def res(match, hg, ag):
    return {"match_id": match, "home_goals": hg, "away_goals": ag,
            "recorded_utc": NOW, "source": "test"}


def part_a_row(match, arm, probs, league="EPL", fit_ok=True, lock=A):
    h, d, a = probs
    return {"match_id": match, "league": league, "lock_utc": lock, "arm": arm,
            "p_home": h, "p_draw": d, "p_away": a, "p_over_2_5": 0.5, "p_btts": 0.5,
            "fit_ok": fit_ok}


def run(preds, results, part_a=None):
    return xt.build(pd.DataFrame(preds), pd.DataFrame(results),
                    pd.DataFrame(part_a or [], columns=xt.PART_A_COLUMNS), NOW)


def test_mean_change_is_arm_minus_control():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15)),
             pred("m2", CONTROL, (0.4, 0.3, 0.3)), pred("m2", JOINT, (0.3, 0.3, 0.4))]
    out = run(preds, [res("m1", 2, 0), res("m2", 1, 1)])
    want = ((-math.log(0.6) + math.log(0.5)) + (-math.log(0.3) + math.log(0.3))) / 2
    joint = out["arms"][JOINT]
    assert joint["n"] == 2
    assert abs(joint["mean_change"] - want) < 1e-12
    assert out["end_date"] == "2027-06-07"
    assert out["as_of"] == "2026-12-01T07:30Z"


def test_paired_drop():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15))]
    out = run(preds, [res("m1", 0, 1)])
    assert out["arms"][JOINT]["n"] == 1
    assert out["arms"][BLEND]["n"] == 0
    assert out["arms"][BLEND]["mean_change"] is None
    assert out["arms"][BLEND]["dropped"] == 1
    assert out["arms"][JOINT]["dropped"] == 0


def test_part_b_wins_over_part_a():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15)),
             pred("m1", BLEND, (0.55, 0.25, 0.2))]
    part_a = [part_a_row("m1", "control", (0.1, 0.1, 0.8)),
              part_a_row("m1", "joint", (0.9, 0.05, 0.05)),
              part_a_row("m1", "blend", (0.9, 0.05, 0.05))]
    out = run(preds, [res("m1", 1, 0)], part_a)
    assert out["parts"]["B"]["n"] == 1
    assert out["parts"]["A"]["n"] == 0
    assert out["arms"][JOINT]["n"] == 1
    assert abs(out["arms"][JOINT]["mean_change"] - (math.log(0.5) - math.log(0.6))) < 1e-12


def test_no_interval_fields():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15)),
             pred("m1", BLEND, (0.55, 0.25, 0.2))]
    text = json.dumps(run(preds, [res("m1", 1, 0)]))
    for word in ('"interval"', '"ci"', '"lower"', '"upper"', '"pass"', '"verdict"',
                 "bootstrap", "fail"):
        assert word not in text


def test_empty_league_is_null():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15))]
    out = run(preds, [res("m1", 1, 0)])
    by = out["arms"][JOINT]["by_league"]
    assert set(by) == {"EPL", "LaLiga", "SerieA", "Ligue1"}
    assert by["SerieA"] == {"n": 0, "mean_change": None}
    assert by["EPL"]["n"] == 1


def test_relock_uses_latest_row():
    later = B + pd.Timedelta(days=1)
    preds = [pred("m1", CONTROL, (0.2, 0.3, 0.5)), pred("m1", CONTROL, (0.5, 0.3, 0.2), later),
             pred("m1", JOINT, (0.9, 0.05, 0.05)), pred("m1", JOINT, (0.6, 0.25, 0.15), later)]
    out = run(preds, [res("m1", 1, 0)])
    assert out["arms"][JOINT]["n"] == 1
    assert abs(out["arms"][JOINT]["mean_change"] - (math.log(0.5) - math.log(0.6))) < 1e-12


def test_fit_ok_false_counts_as_missing():
    part_a = [part_a_row("m1", "control", (0.5, 0.3, 0.2)),
              part_a_row("m1", "joint", (0.6, 0.25, 0.15)),
              part_a_row("m1", "blend", (0.6, 0.25, 0.15), fit_ok=False)]
    out = run([], [res("m1", 1, 0)], part_a)
    assert out["arms"][JOINT]["n"] == 1
    assert out["arms"][BLEND]["n"] == 0
    assert out["arms"][BLEND]["dropped"] == 1
    assert out["parts"]["A"]["n"] == 1
    assert out["parts"]["A"]["mean_change"]["blend"] is None


def test_missing_part_a_file_is_empty_part_a(tmp_path):
    frame = xt.load_part_a(tmp_path / "no_such.parquet")
    assert frame.empty
    out = run([pred("m1", CONTROL, (0.5, 0.3, 0.2))], [res("m1", 1, 0)])
    assert out["parts"]["A"] == {"n": 0, "mean_change": {"joint": None, "blend": None}}


def test_degraded_control_still_counts():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2), degraded=True),
             pred("m1", JOINT, (0.6, 0.25, 0.15))]
    out = run(preds, [res("m1", 1, 0)])
    assert out["arms"][JOINT]["n"] == 1


def test_fits_block():
    out = run([pred("m1", CONTROL, (0.5, 0.3, 0.2))], [])
    assert out["fits"] == {"last_run_utc": None, "joint_ok": None, "blend_ok": None}
    late = B + pd.Timedelta(days=2)
    preds = [pred("m1", JOINT, (0.6, 0.25, 0.15)), pred("m1", BLEND, (0.6, 0.25, 0.15)),
             pred("m2", JOINT, (0.6, 0.25, 0.15), late)]
    out = run(preds, [])
    assert out["fits"] == {"last_run_utc": "2026-11-26T06:00Z", "joint_ok": True,
                           "blend_ok": False}


def test_rows_before_part_b_start_are_not_part_b():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2), A), pred("m1", JOINT, (0.6, 0.25, 0.15), A)]
    out = run(preds, [res("m1", 1, 0)])
    assert out["parts"]["B"]["n"] == 0
    assert out["arms"][JOINT]["n"] == 0


def test_cli_writes_the_file(tmp_path):
    out = tmp_path / "deep" / "xg_test.json"
    code = xt.main(["--out", str(out), "--now", "2026-12-01T07:30:00Z",
                    "--ledger", str(tmp_path / "none"), "--part-a", str(tmp_path / "none.pq")])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["arms"][JOINT]["n"] == 0


def test_progress_line():
    data = {"arms": {JOINT: {"n": 3, "mean_change": -0.00214},
                     BLEND: {"n": 2, "mean_change": None}},
            "parts": {"A": {"n": 1}, "B": {"n": 2}}}
    assert xt.progress_line(data) == ("xG test: 3 matches scored; joint -0.0021, blend not yet. "
                                      "No verdict until 7 Jun 2027.")


def test_monthly_progress_line_reads_both_ledgers(tmp_path):
    from fp.pipeline import monthly

    (tmp_path / "trial").mkdir()
    pd.DataFrame([pred("m1", CONTROL, (0.5, 0.3, 0.2), league="SerieA"),
                  pred("m1", JOINT, (0.6, 0.25, 0.15), league="SerieA")]).to_parquet(
        tmp_path / "trial" / "predictions.parquet")
    pd.DataFrame([res("m1", 1, 0)]).to_parquet(tmp_path / "trial" / "results.parquet")
    line = monthly.xg_progress(tmp_path, NOW, tmp_path / "none.parquet", played=[])
    want = math.log(0.5) - math.log(0.6)
    assert line == (f"xG test: 1 matches scored; joint {want:+.4f}, blend not yet. "
                    "No verdict until 7 Jun 2027.")


def test_part_a_result_from_processed_table_is_scored(tmp_path):
    part_a = [part_a_row("m1", "control", (0.5, 0.3, 0.2), league="Ligue1"),
              part_a_row("m1", "joint", (0.6, 0.25, 0.15), league="Ligue1")]
    table = tmp_path / "matches.parquet"
    pd.DataFrame([{"league": "Ligue1", "match_id": "m1", "home_goals": 3, "away_goals": 1},
                  {"league": "Bundesliga", "match_id": "m9", "home_goals": 0,
                   "away_goals": 0}]).to_parquet(table)
    played = xt.load_played([table, tmp_path / "missing.parquet"])
    assert list(played["match_id"]) == ["m1"]
    out = xt.build(pd.DataFrame(), pd.DataFrame(),
                   pd.DataFrame(part_a, columns=xt.PART_A_COLUMNS), NOW, played)
    assert out["parts"]["A"]["n"] == 1
    assert out["arms"][JOINT]["by_league"]["Ligue1"]["n"] == 1
    assert abs(out["arms"][JOINT]["mean_change"] - (math.log(0.5) - math.log(0.6))) < 1e-12


def test_ledger_result_wins_over_processed_table():
    preds = [pred("m1", CONTROL, (0.5, 0.3, 0.2)), pred("m1", JOINT, (0.6, 0.25, 0.15))]
    played = pd.DataFrame([{"match_id": "m1", "home_goals": 0, "away_goals": 2}])
    out = xt.build(pd.DataFrame(preds), pd.DataFrame([res("m1", 1, 0)]),
                   pd.DataFrame(columns=xt.PART_A_COLUMNS), NOW, played)
    assert abs(out["arms"][JOINT]["mean_change"] - (math.log(0.5) - math.log(0.6))) < 1e-12
