"""The hidden xG test file (pre-registration data/audit/preregistration_xg_2026_11.md).

scripts/make_xg_test.py writes it in the daily job. It reads the live and trial ledgers
(ledger/ and ledger/trial/) and the part A walk-forward file
(data/backtests/xg_2026_27/part_a.parquet; missing means an empty part A). The file holds, per xG
arm, the paired mean change in home, draw, away log loss (arm minus control; negative means
the arm is better), per league and per part.

The file holds no interval, no bootstrap and no verdict: the pre-registration decides only
at the end date, from the full season.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from fp import ROOT

CONTROL = "dc_bayes_v1_noshape"
ARMS = {"joint": "dc_bayes_xg_joint_v1", "blend": "dc_bayes_xg_blend_v1"}
MODEL_ARM = {CONTROL: "control", **{name: arm for arm, name in ARMS.items()}}
LEAGUES = ("EPL", "LaLiga", "SerieA", "Ligue1")
PART_B_START = pd.Timestamp("2026-11-23T15:00:11Z")
END_DATE = "2027-06-07"
RUN_WINDOW = pd.Timedelta(hours=12)   # rows of one daily job (live and trial steps)
PROBS = ["p_home", "p_draw", "p_away"]
PART_A_COLUMNS = ["match_id", "league", "lock_utc", "arm", "p_home", "p_draw", "p_away",
                  "p_over_2_5", "p_btts", "fit_ok"]
LEDGER = ROOT / "ledger"
PART_A = ROOT / "data" / "backtests" / "xg_2026_27" / "part_a.parquet"
OUT = ROOT / "data" / "xg_test" / "xg_test.json"


def _utc(series: pd.Series) -> pd.Series:
    out = pd.to_datetime(series)
    return out.dt.tz_localize("UTC") if out.dt.tz is None else out.dt.tz_convert("UTC")


def _stamp(ts: pd.Timestamp) -> str:
    return f"{ts.tz_convert('UTC'):%Y-%m-%dT%H:%MZ}"


def _latest(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per match and arm: the latest lock (a relock replaces the earlier row),
    the same rule the weekly report uses for ledger rows."""
    return rows.sort_values("lock_utc", kind="stable").drop_duplicates(
        ["match_id", "arm"], keep="last")


def outcomes(results: pd.DataFrame) -> pd.Series:
    """match_id -> 'home', 'draw' or 'away' from the 90-minute score."""
    if results.empty:
        return pd.Series(dtype=object)
    r = results.dropna(subset=["home_goals", "away_goals"])
    if "recorded_utc" in r.columns:
        r = r.sort_values("recorded_utc", kind="stable")
    r = r.drop_duplicates("match_id", keep="last")
    hg, ag = r["home_goals"].astype(int), r["away_goals"].astype(int)
    side = ["home" if h > a else "draw" if h == a else "away"
            for h, a in zip(hg, ag, strict=True)]
    return pd.Series(side, index=r["match_id"].astype(str).to_numpy())


def part_b_rows(preds: pd.DataFrame) -> pd.DataFrame:
    """Control and xG ledger rows locked at or after the part B start."""
    if preds.empty:
        return pd.DataFrame(columns=["match_id", "league", "lock_utc", "arm", *PROBS])
    p = preds[preds["model_name"].isin(MODEL_ARM)].copy()
    p["lock_utc"] = _utc(p["lock_utc"])
    p = p[p["lock_utc"] >= PART_B_START]
    p["arm"] = p["model_name"].map(MODEL_ARM)
    return p[["match_id", "league", "lock_utc", "arm", *PROBS]]


def part_a_rows(part_a: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward rows; a failed fit (fit_ok False) is no forecast for that arm."""
    if part_a.empty:
        return pd.DataFrame(columns=["match_id", "league", "lock_utc", "arm", *PROBS])
    a = part_a.copy()
    if "fit_ok" in a.columns:
        a = a[a["fit_ok"].fillna(False).astype(bool)]
    a["lock_utc"] = _utc(a["lock_utc"])
    return a[["match_id", "league", "lock_utc", "arm", *PROBS]]


def _log_loss(row: pd.Series, side: str) -> float:
    return -math.log(float(row[f"p_{side}"]))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build(preds: pd.DataFrame, results: pd.DataFrame, part_a: pd.DataFrame,
          now: pd.Timestamp) -> dict:
    """The xg_test.json content. Paired per arm (pre-registration section 6): a match counts
    for an arm only if that arm and the control both have a usable forecast and the result is
    known. `dropped` counts matches with a control forecast and a result but no forecast for
    that arm. A degraded control row still counts: it is what the published model said."""
    b_raw = part_b_rows(preds)
    a_raw = part_a_rows(part_a)
    b = _latest(b_raw.dropna(subset=PROBS))
    a = _latest(a_raw.dropna(subset=PROBS))
    b_matches = set(b_raw["match_id"])
    a = a[~a["match_id"].isin(b_matches)]                 # part B wins; each match once
    side = outcomes(results)
    if {"home_goals", "away_goals"} <= set(part_a.columns):
        extra = outcomes(part_a.drop_duplicates("match_id"))
        side = pd.concat([side, extra[~extra.index.isin(side.index)]])

    rows = pd.concat([a.assign(part="A"), b.assign(part="B")], ignore_index=True)
    scored: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    dropped = dict.fromkeys(ARMS, 0)
    for match, group in rows.groupby("match_id", sort=True):
        if match not in side.index:
            continue
        by_arm = {r["arm"]: r for _, r in group.iterrows()}
        if "control" not in by_arm:
            continue
        control = by_arm["control"]
        result = side[match]
        for arm in ARMS:
            if arm not in by_arm:
                dropped[arm] += 1
                continue
            change = _log_loss(by_arm[arm], result) - _log_loss(control, result)
            scored[arm].append({"match_id": match, "league": control["league"],
                                "part": control["part"], "change": change})

    arms = {}
    for arm, name in ARMS.items():
        items = scored[arm]
        by_league = {}
        for league in LEAGUES:
            vals = [s["change"] for s in items if s["league"] == league]
            by_league[league] = {"n": len(vals), "mean_change": _mean(vals)}
        arms[name] = {"n": len(items), "mean_change": _mean([s["change"] for s in items]),
                      "by_league": by_league, "dropped": dropped[arm]}

    parts = {}
    for part in ("A", "B"):
        counted = {s["match_id"] for arm in ARMS for s in scored[arm] if s["part"] == part}
        parts[part] = {"n": len(counted), "mean_change": {
            arm: _mean([s["change"] for s in scored[arm] if s["part"] == part])
            for arm in ARMS}}

    xg_b = b_raw[b_raw["arm"].isin(ARMS)]
    if xg_b.empty:
        fits = {"last_run_utc": None, "joint_ok": None, "blend_ok": None}
    else:
        last = xg_b["lock_utc"].max()
        run = xg_b[xg_b["lock_utc"] >= last - RUN_WINDOW]
        fits = {"last_run_utc": _stamp(last),
                **{f"{arm}_ok": bool((run["arm"] == arm).any()) for arm in ARMS}}

    return {"as_of": _stamp(pd.Timestamp(now)), "end_date": END_DATE, "arms": arms,
            "parts": parts, "fits": fits}


def progress_line(data: dict) -> str:
    """One line for the monthly review (pre-registration section 8). No verdict."""
    n = data["parts"]["A"]["n"] + data["parts"]["B"]["n"]

    def fmt(name: str) -> str:
        mean = data["arms"][name]["mean_change"]
        return "not yet" if mean is None else f"{mean:+.4f}"

    return (f"xG test: {n} matches scored; joint {fmt(ARMS['joint'])}, "
            f"blend {fmt(ARMS['blend'])}. No verdict until 7 Jun 2027.")


def _read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def load_ledgers(folder: Path = LEDGER) -> tuple[pd.DataFrame, pd.DataFrame]:
    preds, results = [], []
    for sub in (folder, folder / "trial"):
        preds.append(_read(sub / "predictions.parquet"))
        results.append(_read(sub / "results.parquet"))
    preds = [p for p in preds if not p.empty]
    results = [r for r in results if not r.empty]
    return (pd.concat(preds, ignore_index=True) if preds else pd.DataFrame(),
            pd.concat(results, ignore_index=True) if results else pd.DataFrame())


def load_part_a(path: Path = PART_A) -> pd.DataFrame:
    """The part A file arrives in a separate PR; until then part A is empty."""
    return _read(path) if path.exists() else pd.DataFrame(columns=PART_A_COLUMNS)
