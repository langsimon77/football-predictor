"""Build today's tip products from the locked ledger.

Usage: python scripts/make_tips.py [--days N]

Reads ledger/predictions.parquet (primary rows: the ones carrying tiers) and
ledger/results.parquet. Writes data/tips/tips.json with:
  free, premium, diamond, coupons   for matches kicking off in the next N days
  record                            won/lost count per product over settled picks
Each pick has: match, league, kickoff (UTC), pick, model probability, fair odds,
tier, status. Fair odds = 1 / probability; a bet has value only above them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fp.tips import picks as tp  # noqa: E402


def primary_rows(pred: pd.DataFrame) -> pd.DataFrame:
    has = pred["tiers"].map(lambda t: "rule" in tp._tiers(t))
    p = pred[has].sort_values("lock_utc")
    return p.drop_duplicates("match_id", keep="last")


def _records(df: pd.DataFrame) -> list[dict]:
    keep = ["match_id", "league", "kickoff_utc", "home_id", "away_id", "market", "pick",
            "prob", "fair_odds", "tier", "status"]
    out = df[[c for c in keep if c in df.columns]].copy()
    out["kickoff_utc"] = out["kickoff_utc"].astype(str)
    out["prob"] = out["prob"].round(3)
    return out.to_dict("records")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()
    pred = pd.read_parquet(ROOT / "ledger" / "predictions.parquet")
    results = pd.read_parquet(ROOT / "ledger" / "results.parquet")
    cand = tp.candidates(primary_rows(pred))
    kick = pd.to_datetime(cand["kickoff_utc"], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    upcoming = cand[(kick >= now) & (kick < now + pd.Timedelta(days=args.days))]
    prod = tp.build_day(upcoming)
    out = {"generated_utc": now.isoformat(), "rule": "tips_v1, from tiers_v1",
           "note": "Fair odds = 1 / model probability. Bet only if the bookmaker pays more.",
           **{k: _records(tp.settle(prod[k], results)) for k in ("free", "premium", "diamond")},
           "coupons": [{**c, "legs": _records(tp.settle(pd.DataFrame(c["legs"]), results)),
                        "prob": round(c["prob"], 3)} for c in prod["coupons"]]}
    # Track record: replay every past day from the ledger, settled against results.
    record = {}
    cand["day"] = kick.dt.date
    past = cand[kick < now]
    for _, c in past.groupby("day"):
        day = tp.build_day(c)
        for name in ("free", "premium", "diamond"):
            st = tp.settle(day[name], results)["status"].value_counts()
            r = record.setdefault(name, {"won": 0, "lost": 0, "pending": 0})
            for s in r:
                r[s] += int(st.get(s, 0))
        for cp in day["coupons"]:
            r = record.setdefault(cp["name"].lower(), {"won": 0, "lost": 0, "pending": 0})
            r[tp.settle_coupon(cp, results)] += 1
    out["record"] = record
    path = ROOT / "data" / "tips" / "tips.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
