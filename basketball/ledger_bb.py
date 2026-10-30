"""Basketball phase B4: the locked forecasts, in their own append-only, hash-chained ledger
(ledger/basketball/predictions.parquet), like the football ledgers (fp.ledger).

One row per game and model. A basketball game has no draw, so a row holds the home win
chance and, where the league's test passed, the bell curves for the margin and the total
(mean and width). The chain rule is fp.ledger's: each row's hash covers the previous hash
and the row's non-empty cells, so no locked row can change without breaking the chain.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from fp.ledger import GENESIS_HASH, LedgerError, _canonical

COLUMNS = [
    "prediction_id", "game_id", "league", "season", "round", "home_id", "away_id",
    "home_name", "away_name", "tip_utc", "lock_utc", "as_of_utc", "model_name",
    "model_version", "code_dirty", "late_lock",
    "p_home", "margin_mean", "margin_sd", "total_mean", "total_sd",
    "flags", "prev_hash", "row_hash",
]
RESULT_COLUMNS = ["game_id", "home_pts", "away_pts", "overtime", "recorded_utc", "source"]
TIMESTAMPS = ["tip_utc", "lock_utc", "as_of_utc"]
BOOLS = ["code_dirty", "late_lock"]
FLOATS = ["p_home", "margin_mean", "margin_sd", "total_mean", "total_sd"]
HASHES = ["prev_hash", "row_hash"]


def coerce(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.reindex(columns=COLUMNS).copy()
    for c in COLUMNS:
        if c in TIMESTAMPS:
            out[c] = pd.to_datetime(out[c], utc=True).astype("datetime64[us, UTC]")
        elif c in BOOLS:
            out[c] = out[c].astype("boolean")
        elif c in FLOATS:
            out[c] = out[c].astype("float64")
        elif c == "season":
            out[c] = out[c].astype("Int64")
        else:
            out[c] = out[c].astype("string")
    return out


def row_hash(row: dict, prev_hash: str) -> str:
    body = {k: v for k in COLUMNS if k not in HASHES and (v := _canonical(row.get(k))) is not None}
    payload = prev_hash + json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load(path: Path) -> pd.DataFrame:
    return coerce(pd.read_parquet(path)) if path.exists() else coerce(pd.DataFrame(columns=COLUMNS))


def verify_chain(ledger: pd.DataFrame) -> None:
    prev = GENESIS_HASH
    for i, row in enumerate(ledger.to_dict("records")):
        if row["prev_hash"] != prev or row["row_hash"] != row_hash(row, prev):
            raise LedgerError(f"basketball hash chain broken at row {i} "
                              f"({row.get('prediction_id')})")
        prev = row["row_hash"]


def verify_append_only(old: pd.DataFrame, new: pd.DataFrame) -> None:
    if len(new) < len(old):
        raise LedgerError(f"basketball ledger shrank from {len(old)} to {len(new)} rows")
    if list(new["row_hash"].iloc[: len(old)]) != list(old["row_hash"]):
        raise LedgerError("an existing basketball ledger row was changed or reordered")
    verify_chain(new)


def append(rows: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Lock new rows. Refuses a second lock for the same game and model, a chance outside
    [0, 1], a time zone-less time and a lock at or after tip-off."""
    if rows.empty:
        return load(path)
    p = rows["p_home"].astype(float)
    if ((p < 0) | (p > 1) | p.isna()).any():
        raise LedgerError("a basketball win chance is missing or outside [0, 1]")
    for c in TIMESTAMPS:
        if pd.to_datetime(rows[c]).dt.tz is None:
            raise LedgerError(f"{c} must be timezone-aware UTC")
    if (pd.to_datetime(rows["lock_utc"]) >= pd.to_datetime(rows["tip_utc"])).any():
        raise LedgerError("cannot lock a game at or after tip-off")
    ledger = load(path)
    verify_chain(ledger)
    have = set(zip(ledger["game_id"], ledger["model_name"], strict=True))
    for g, m in zip(rows["game_id"], rows["model_name"], strict=True):
        if (g, m) in have:
            raise LedgerError(f"{g} is already locked for {m}")
    prev = ledger["row_hash"].iloc[-1] if len(ledger) else GENESIS_HASH
    records = []
    for r in coerce(rows).to_dict("records"):
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
    tmp.replace(path)
    return updated
