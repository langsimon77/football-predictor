"""collect_part_a: keep part A, rename columns, record fit status truthfully."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_part_a import collect  # noqa: E402

START = pd.Timestamp("2026-11-23T15:00:11Z")


def _frame(locks, league="EPL", fit_ok=True, as_of="2026-11-01T00:00:00Z"):
    n = len(locks)
    return pd.DataFrame({
        "match_id": [f"m{i}" for i in range(n)],
        "league": league,
        "as_of_utc": pd.Timestamp(as_of),
        "lock_utc": pd.to_datetime(locks, utc=True),
        "fit_ok": fit_ok,
        "bdc_home": 0.5, "bdc_draw": 0.3, "bdc_away": 0.2,
        "bdc_over_2_5": 0.55, "bdc_btts": 0.5,
    })


def _fits(rows):
    return pd.DataFrame(
        [{"league": "EPL", "as_of_utc": pd.Timestamp(t), "ok": ok} for t, ok in rows]
    )


def _args(locks=("2026-11-10T12:00:00Z", "2026-11-23T15:00:11Z", "2026-11-24T12:00:00Z")):
    frames = {a: _frame(list(locks)) for a in ("control", "joint", "blend")}
    fits = {a: _fits([("2026-11-01T00:00:00Z", True)]) for a in frames}
    return frames, fits


def test_collect_keeps_only_pre_part_b():
    frames, fits = _args()
    out = collect(frames, fits, START)
    assert len(out) == 3  # one early match per arm; the start time itself is part B
    assert set(out["arm"]) == {"control", "joint", "blend"}
    assert (out["lock_utc"] < START).all()


def test_renames_bdc_columns():
    frames, fits = _args()
    out = collect(frames, fits, START)
    assert list(out.columns) == [
        "match_id", "league", "lock_utc", "arm",
        "p_home", "p_draw", "p_away", "p_over_2_5", "p_btts", "fit_ok",
    ]
    assert out["p_home"].eq(0.5).all()


def test_fit_ok_comes_from_latest_fit_attempt():
    locks = ["2026-11-05T12:00:00Z", "2026-11-12T12:00:00Z"]
    frames = {a: _frame(locks, fit_ok=True) for a in ("control", "joint", "blend")}
    fits = {a: _fits([("2026-11-01T00:00:00Z", True)]) for a in frames}
    # joint tried again on 8 Nov and failed: its later row must read fit_ok False
    fits["joint"] = _fits([("2026-11-01T00:00:00Z", True), ("2026-11-08T00:00:00Z", False)])
    out = collect(frames, fits, START).set_index(["arm", "match_id"])["fit_ok"]
    assert out[("joint", "m0")]
    assert not out[("joint", "m1")]
    assert out[("control", "m1")]


def test_missing_arm_raises():
    frames, fits = _args()
    del frames["blend"]
    with pytest.raises(ValueError, match="blend"):
        collect(frames, fits, START)


def test_mixed_datetime_resolutions():
    frames, fits = _args()
    for a in frames:
        frames[a]["lock_utc"] = frames[a]["lock_utc"].astype("datetime64[us, UTC]")
        fits[a]["as_of_utc"] = fits[a]["as_of_utc"].astype("datetime64[ns, UTC]")
    out = collect(frames, fits, START)
    assert out["fit_ok"].all()


def test_nothing_before_part_b_returns_empty():
    frames, fits = _args(locks=("2026-11-24T12:00:00Z",))
    out = collect(frames, fits, START)
    assert out.empty
    assert list(out.columns) == [
        "match_id", "league", "lock_utc", "arm",
        "p_home", "p_draw", "p_away", "p_over_2_5", "p_btts", "fit_ok",
    ]
