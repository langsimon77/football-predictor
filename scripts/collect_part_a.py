"""Collect the part A walk-forward results of the xG test (pre-registration section 3 and 6).

Reads the artifacts that `gh run download` wrote for the three runs (control, joint,
blend), keeps matches locked before the part B start, and writes one long table.

    uv run python scripts/collect_part_a.py DOWNLOAD_DIR \
        --part-b-start 2026-11-23T15:00:11Z \
        --out data/backtests/xg_2026_27/part_a.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ARMS = {"control": "xg_none", "joint": "xg_joint", "blend": "xg_blend"}
LEAGUES = ("EPL", "LaLiga", "SerieA", "Ligue1")
PRED_COLS = {
    "bdc_home": "p_home", "bdc_draw": "p_draw", "bdc_away": "p_away",
    "bdc_over_2_5": "p_over_2_5", "bdc_btts": "p_btts",
}
OUT_COLS = ["match_id", "league", "lock_utc", "arm", *PRED_COLS.values(), "fit_ok"]


def _fit_ok_from_fits(pred: pd.DataFrame, fits: pd.DataFrame) -> pd.Series:
    """Per row: ok flag of the latest fit attempt (same league) at or before lock_utc.

    A failed attempt locks nothing: rows locked after it count as not fit_ok, even
    though the backtest carried an older good fit forward. No earlier fit means False.
    """
    f = fits[["league", "as_of_utc", "ok"]].copy()
    f["as_of_utc"] = pd.to_datetime(f["as_of_utc"], utc=True).astype("datetime64[ns, UTC]")
    left = pred[["league", "lock_utc"]].copy()
    left["lock_utc"] = pd.to_datetime(left["lock_utc"], utc=True).astype("datetime64[ns, UTC]")
    left["_i"] = range(len(left))
    merged = pd.merge_asof(
        left.sort_values("lock_utc"), f.sort_values("as_of_utc"),
        left_on="lock_utc", right_on="as_of_utc", by="league", direction="backward",
    ).sort_values("_i")
    return merged["ok"].eq(True).to_numpy()


def collect(frames: dict[str, pd.DataFrame], fits: dict[str, pd.DataFrame],
            part_b_start: pd.Timestamp) -> pd.DataFrame:
    missing = [a for a in ARMS if a not in frames or a not in fits]
    if missing:
        raise ValueError(f"missing arm(s): {', '.join(missing)}")
    start = pd.Timestamp(part_b_start)
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    parts = []
    for arm in ARMS:
        df = frames[arm].copy()
        df["lock_utc"] = pd.to_datetime(df["lock_utc"], utc=True)
        df = df[df["lock_utc"] < start].reset_index(drop=True)
        df["fit_ok"] = _fit_ok_from_fits(df, fits[arm])
        df["arm"] = arm
        parts.append(df.rename(columns=PRED_COLS)[OUT_COLS])
    return pd.concat(parts, ignore_index=True)


def _find(root: Path, pattern: str) -> Path:
    hits = sorted(root.rglob(pattern))
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one file for {pattern} under {root}, found {len(hits)}")
    return hits[0]


def load(download_dir: Path) -> tuple[dict, dict]:
    frames: dict[str, pd.DataFrame] = {}
    fits: dict[str, pd.DataFrame] = {}
    for arm, stage in ARMS.items():
        fr, ft = [], []
        for league in LEAGUES:
            base = f"{stage}_goals_{league}2026_sot"
            fr.append(pd.read_parquet(_find(download_dir, f"{base}.parquet")))
            fit = pd.read_parquet(_find(download_dir, f"{base}.fits.parquet"))
            if "league" not in fit.columns:
                fit["league"] = league
            ft.append(fit)
        frames[arm] = pd.concat(fr, ignore_index=True)
        fits[arm] = pd.concat(ft, ignore_index=True)
    return frames, fits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("download_dir", type=Path)
    ap.add_argument("--part-b-start", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    frames, fits = load(a.download_dir)
    out = collect(frames, fits, pd.Timestamp(a.part_b_start))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(a.out)
    all_fits = pd.concat([f.assign(arm=arm) for arm, f in fits.items()], ignore_index=True)
    fits_path = a.out.with_name(a.out.stem + "_fits.parquet")
    all_fits.to_parquet(fits_path)
    print(out.groupby(["arm", "league"]).size().unstack())
    print(f"wrote {a.out} ({len(out)} rows) and {fits_path} ({len(all_fits)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
