"""The ledger must be append-only and tamper-evident (spec S4, S13)."""

from __future__ import annotations

import pandas as pd
import pytest

from fp import ledger


def make_rows(match_ids, p=(0.5, 0.3, 0.2), model="test_model", **extra):
    kickoff = pd.Timestamp("2026-10-10 11:30", tz="UTC")
    rows = pd.DataFrame({
        "prediction_id": [f"{m}:{model}" for m in match_ids],
        "match_id": match_ids,
        "league": "EPL",
        "season": 2026,
        "home_id": "arsenal",
        "away_id": "leeds",
        "kickoff_utc": kickoff,
        "lock_utc": kickoff - pd.Timedelta(hours=30),
        "as_of_utc": kickoff - pd.Timedelta(hours=30),
        "model_name": model,
        "model_version": "abc1234",
        "code_dirty": False,
        "degraded": False,
        "late_lock": False,
        "relock_reason": None,
        "p_home": p[0],
        "p_draw": p[1],
        "p_away": p[2],
        "exp_goals_home": 1.7,
        "exp_goals_away": 0.9,
    })
    for key, value in extra.items():
        rows[key] = value
    return rows


def test_append_then_reload_keeps_the_chain_valid(tmp_path):
    path = tmp_path / "predictions.parquet"
    ledger.append(make_rows(["m1", "m2"]), path)
    ledger.append(make_rows(["m3"]), path)
    reloaded = ledger.load(path)
    assert list(reloaded["match_id"]) == ["m1", "m2", "m3"]
    ledger.verify_chain(reloaded)


def test_editing_an_old_row_is_detected(tmp_path):
    path = tmp_path / "predictions.parquet"
    ledger.append(make_rows(["m1", "m2", "m3"]), path)
    tampered = ledger.load(path)
    tampered.loc[0, "p_home"] = 0.9
    with pytest.raises(ledger.LedgerError, match="row 0"):
        ledger.verify_chain(tampered)


def test_deleting_a_row_is_detected(tmp_path):
    path = tmp_path / "predictions.parquet"
    old = ledger.append(make_rows(["m1", "m2", "m3"]), path)
    with pytest.raises(ledger.LedgerError):
        ledger.verify_append_only(old, old.drop(index=1).reset_index(drop=True))


def test_same_match_cannot_be_locked_twice(tmp_path):
    path = tmp_path / "predictions.parquet"
    ledger.append(make_rows(["m1"]), path)
    with pytest.raises(ledger.LedgerError, match="already locked"):
        ledger.append(make_rows(["m1"]), path)


def test_relock_allowed_with_a_reason(tmp_path):
    path = tmp_path / "predictions.parquet"
    ledger.append(make_rows(["m1"]), path)
    ledger.append(make_rows(["m1"], relock_reason="kickoff moved 14 days"), path)
    assert len(ledger.load(path)) == 2


def test_1x2_must_sum_to_one(tmp_path):
    with pytest.raises(ledger.LedgerError, match="sum to 1"):
        ledger.append(make_rows(["m1"], p=(0.5, 0.3, 0.3)), tmp_path / "p.parquet")


def test_probability_out_of_range(tmp_path):
    with pytest.raises(ledger.LedgerError, match="outside"):
        ledger.append(make_rows(["m1"], p_over_2_5=1.2), tmp_path / "p.parquet")


def test_cannot_lock_after_kickoff(tmp_path):
    rows = make_rows(["m1"])
    rows["lock_utc"] = rows["kickoff_utc"] + pd.Timedelta(minutes=1)
    with pytest.raises(ledger.LedgerError, match="kickoff"):
        ledger.append(rows, tmp_path / "p.parquet")


def test_adding_a_column_later_keeps_old_hashes(tmp_path, monkeypatch):
    """A later phase may add a column. Old rows leave it empty, so their hashes hold."""
    path = tmp_path / "predictions.parquet"
    ledger.append(make_rows(["m1", "m2"]), path)
    monkeypatch.setattr(ledger, "COLUMNS", [*ledger.COLUMNS[:-2], "new_metric",
                                            *ledger.HASH_COLUMNS])
    ledger.verify_chain(ledger.load(path))
