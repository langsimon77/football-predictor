"""The prediction ledger: append-only, hash-chained.

ledger/predictions.parquet holds every locked prediction. A locked row is never
edited or deleted (spec S4). Each row stores a SHA-256 hash of its own contents
plus the previous row's hash. Changing any old row breaks every hash after it, so
verify_chain() catches tampering or accidents. Git history then proves each row
existed before its kickoff.

ledger/results.parquet holds outcomes, joined on match_id. Results can be
corrected if a source fixes an error, so that file is not hash-chained.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd

from fp import ROOT

LEDGER_DIR = ROOT / "ledger"
PREDICTIONS = LEDGER_DIR / "predictions.parquet"
RESULTS = LEDGER_DIR / "results.parquet"
GENESIS_HASH = "0" * 64

IDENTITY_COLUMNS = [
    "prediction_id", "match_id", "league", "season", "home_id", "away_id",
    "kickoff_utc", "lock_utc", "as_of_utc", "model_name", "model_version",
    "code_dirty", "degraded", "late_lock", "relock_reason",
]
PROBABILITY_COLUMNS = [
    "p_home", "p_draw", "p_away",
    "p_over_1_5", "p_over_2_5", "p_over_3_5", "p_btts",
    "p_corners_over_8_5", "p_corners_over_9_5", "p_corners_over_10_5", "p_corners_over_11_5",
    "p_yellows_over_3_5", "p_yellows_over_4_5", "p_yellows_over_5_5",
]
EXPECTATION_COLUMNS = [
    "exp_goals_home", "exp_goals_away",
    "exp_corners_home", "exp_corners_away", "exp_yellows",
]
TEXT_COLUMNS = [  # JSON strings
    "top_scorelines", "tiers", "news_adjustments", "unanswered_questions", "flags",
]
HASH_COLUMNS = ["prev_hash", "row_hash"]
COLUMNS = IDENTITY_COLUMNS + PROBABILITY_COLUMNS + EXPECTATION_COLUMNS + TEXT_COLUMNS + HASH_COLUMNS

RESULT_COLUMNS = [
    "match_id", "home_goals", "away_goals", "home_corners", "away_corners",
    "home_yellows", "away_yellows", "home_reds", "away_reds", "recorded_utc", "source",
]


class LedgerError(RuntimeError):
    pass


TIMESTAMP_COLUMNS = ["kickoff_utc", "lock_utc", "as_of_utc"]
BOOL_COLUMNS = ["code_dirty", "degraded", "late_lock"]
FLOAT_COLUMNS = PROBABILITY_COLUMNS + EXPECTATION_COLUMNS


def coerce(frame: pd.DataFrame) -> pd.DataFrame:
    """Give every column one fixed type, so a row hashes the same before and after
    a round trip through Parquet."""
    out = frame.reindex(columns=COLUMNS).copy()
    for column in COLUMNS:
        if column in TIMESTAMP_COLUMNS:
            out[column] = pd.to_datetime(out[column], utc=True).astype("datetime64[us, UTC]")
        elif column in BOOL_COLUMNS:
            out[column] = out[column].astype("boolean")
        elif column in FLOAT_COLUMNS:
            out[column] = out[column].astype("float64")
        elif column == "season":
            out[column] = out[column].astype("Int64")
        else:
            out[column] = out[column].astype("string")
    return out


def _canonical(value: object) -> object:
    """A stable, JSON-safe form of one cell."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):  # numpy scalar
        return _canonical(value.item())
    return value


def row_hash(row: dict, prev_hash: str) -> str:
    body = {k: _canonical(row.get(k)) for k in COLUMNS if k not in HASH_COLUMNS}
    payload = prev_hash + json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def empty() -> pd.DataFrame:
    return coerce(pd.DataFrame(columns=COLUMNS))


def load(path: Path = PREDICTIONS) -> pd.DataFrame:
    return coerce(pd.read_parquet(path)) if path.exists() else empty()


def verify_chain(ledger: pd.DataFrame) -> None:
    prev = GENESIS_HASH
    for i, row in enumerate(ledger.to_dict("records")):
        if row["prev_hash"] != prev or row["row_hash"] != row_hash(row, prev):
            raise LedgerError(f"hash chain broken at row {i} ({row.get('prediction_id')})")
        prev = row["row_hash"]


def verify_append_only(old: pd.DataFrame, new: pd.DataFrame) -> None:
    """Every row in the old ledger must still be in the new one, unchanged, in order."""
    if len(new) < len(old):
        raise LedgerError(f"ledger shrank from {len(old)} to {len(new)} rows")
    old_hashes = list(old["row_hash"])
    if list(new["row_hash"].iloc[: len(old)]) != old_hashes:
        raise LedgerError("an existing ledger row was changed or reordered")
    verify_chain(new)


def validate_rows(rows: pd.DataFrame) -> None:
    """Checks on new rows before they are locked (spec S13)."""
    missing = set(IDENTITY_COLUMNS + ["p_home", "p_draw", "p_away"]) - set(rows.columns)
    if missing:
        raise LedgerError(f"new rows are missing columns: {sorted(missing)}")
    probs = rows[[c for c in PROBABILITY_COLUMNS if c in rows]].astype("float64")
    if ((probs < 0) | (probs > 1)).any().any():
        raise LedgerError("a probability is outside [0, 1]")
    total = rows[["p_home", "p_draw", "p_away"]].astype("float64").sum(axis=1)
    if ((total - 1).abs() > 1e-6).any():
        raise LedgerError("a 1X2 set does not sum to 1 within 1e-6")
    for column in ("kickoff_utc", "lock_utc", "as_of_utc"):
        if pd.to_datetime(rows[column]).dt.tz is None:
            raise LedgerError(f"{column} must be timezone-aware UTC")
    if (pd.to_datetime(rows["lock_utc"]) >= pd.to_datetime(rows["kickoff_utc"])).any():
        raise LedgerError("cannot lock a match at or after kickoff")


def append(rows: pd.DataFrame, path: Path = PREDICTIONS) -> pd.DataFrame:
    """Lock new predictions. Refuses a second lock for the same match and model
    unless the row carries a relock_reason (a kickoff moved by more than 7 days)."""
    validate_rows(rows)
    ledger = load(path)
    verify_chain(ledger)

    existing = set(zip(ledger["match_id"], ledger["model_name"], strict=True))
    for r in rows.to_dict("records"):
        if (r["match_id"], r["model_name"]) in existing and not r.get("relock_reason"):
            raise LedgerError(f"{r['match_id']} is already locked for {r['model_name']}")

    rows = coerce(rows)
    prev = ledger["row_hash"].iloc[-1] if len(ledger) else GENESIS_HASH
    records = []
    for r in rows.to_dict("records"):
        r["prev_hash"] = prev
        r["row_hash"] = row_hash(r, prev)
        prev = r["row_hash"]
        records.append(r)

    new = coerce(pd.DataFrame(records, columns=COLUMNS))
    updated = new if ledger.empty else pd.concat([ledger, new], ignore_index=True)
    verify_append_only(ledger, updated)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    updated.to_parquet(tmp, index=False)
    tmp.replace(path)  # atomic swap: a crash never leaves half a ledger
    return updated
