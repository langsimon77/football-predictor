"""The freshness check flags a source that falls more than 72 hours behind (spec S3)."""

from __future__ import annotations

import pandas as pd

from fp.validate import freshness

NOW = pd.Timestamp("2026-10-14 06:00", tz="UTC")


def calendar(kickoffs_played, scheduled_days=()):
    rows = []
    for i, k in enumerate(kickoffs_played):
        k = pd.Timestamp(k, tz="UTC")
        rows.append({"match_id": f"p{i}", "league": "EPL", "season": 2026, "status": "played",
                     "kickoff_utc": k, "date": k.date().isoformat(), "time_confirmed": True})
    for i, d in enumerate(scheduled_days):
        rows.append({"match_id": f"s{i}", "league": "EPL", "season": 2026, "status": "scheduled",
                     "kickoff_utc": pd.NaT, "date": d, "time_confirmed": False})
    return pd.DataFrame(rows)


def results(match_ids):
    return pd.DataFrame({
        "match_id": list(match_ids), "league": "EPL", "season": 2026,
        "kickoff_utc": pd.Timestamp("2026-10-10 14:00", tz="UTC"),
    })


def test_up_to_date_source_is_fresh():
    report = freshness.check(results(["p0"]), calendar(["2026-10-10 14:00"]), now=NOW)
    assert not report.stale


def test_recent_gap_is_not_yet_stale():
    """Finished 40 hours ago and missing: normal lag, not stale yet."""
    report = freshness.check(results([]), calendar(["2026-10-12 14:00"]), now=NOW)
    assert not report.stale
    assert report.leagues[0].missing_results == ["p0"]


def test_gap_over_72_hours_is_stale():
    report = freshness.check(results([]), calendar(["2026-10-10 14:00"]), now=NOW)
    assert report.stale
    assert "STALE" in report.summary()


def test_fixture_soon_without_kickoff_time_is_reported():
    cal = calendar(["2026-10-10 14:00"], scheduled_days=["2026-10-15"])
    report = freshness.check(results(["p0"]), cal, now=NOW)
    assert report.leagues[0].unconfirmed_soon == ["s0"]
