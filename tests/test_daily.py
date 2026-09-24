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
