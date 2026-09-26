"""Which matches does a daily run lock? (spec S10 plus PRD item 24)."""

from __future__ import annotations

import pandas as pd

from fp.pipeline import daily

NOW = pd.Timestamp("2026-10-08 04:41", tz="UTC")


def fixtures():
    rows = [
        ("late", 10, True),       # under 24 h: lock now, flagged late
        ("normal", 38, True),     # the usual case
        ("too_far", 50, True),    # next run's job
        ("no_time", 30, False),   # kickoff not confirmed: cannot lock
        ("started", -1, True),    # already kicked off
        ("locked", 30, True),     # already in the ledger
    ]
    return pd.DataFrame({
        "match_id": [r[0] for r in rows],
        "kickoff_utc": [NOW + pd.Timedelta(hours=r[1]) for r in rows],
        "time_confirmed": [r[2] for r in rows],
    })


def test_candidates_follow_the_lock_rule():
    existing = pd.DataFrame({"match_id": ["locked"]})
    got = daily.candidates(fixtures(), NOW, existing).set_index("match_id")
    assert sorted(got.index) == ["late", "normal"]
    assert got.loc["late", "late_lock"]
    assert not got.loc["normal", "late_lock"]


def test_candidates_with_empty_ledger():
    got = daily.candidates(fixtures(), NOW, pd.DataFrame())
    assert "locked" in set(got["match_id"])


def test_a_locked_match_that_moves_more_than_7_days_locks_again():
    fx = pd.DataFrame({
        "match_id": ["moved_far", "moved_near", "new"],
        "kickoff_utc": [NOW + pd.Timedelta(hours=30)] * 3,
        "time_confirmed": [True, True, True],
    })
    existing = pd.DataFrame({
        "match_id": ["moved_far", "moved_near"],
        "lock_utc": [NOW - pd.Timedelta(days=12)] * 2,
        "kickoff_utc": [NOW - pd.Timedelta(days=11), NOW + pd.Timedelta(days=2)],
    })
    got = daily.candidates(fx, NOW, existing).set_index("match_id")
    assert sorted(got.index) == ["moved_far", "new"]
    assert got.loc["moved_far", "relock_reason"].startswith("kickoff moved from")
    assert got.loc["new", "relock_reason"] is None


def test_problem_log_keeps_pipeline_warnings_only():
    import logging
    handler = daily.ProblemLog()
    logging.getLogger("fp.pipeline.daily").addHandler(handler)
    logging.getLogger("fp.ingest.matches").addHandler(handler)
    try:
        logging.getLogger("fp.pipeline.daily").warning("EPL: diagnostics failed")
        logging.getLogger("fp.ingest.matches").warning("impossible odds set to missing")
    finally:
        logging.getLogger("fp.pipeline.daily").removeHandler(handler)
        logging.getLogger("fp.ingest.matches").removeHandler(handler)
    assert handler.lines == ["WARNING: EPL: diagnostics failed"]
