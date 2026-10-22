"""Write the Europa League and Conference League data the Model Lab reads.

data/euro/euro_gameweek.json  uel and uecl blocks (rows, as_of, test), the matches for the
                              pairs and slip pages, and the safety tables (safety_eur, record_eur)
data/euro/history_seed.json   one history document per match (calls; result filled later)

Lock rule: a match whose kickoff has passed is never rewritten. Its last forecast before
kickoff is carried over from the previous files unchanged; new forecasts are written only
for matches still to play.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import paths

KEEP_DAYS = 3  # started matches stay in the files this long (the page shows recent results)


def now_utc() -> datetime:
    s = os.environ.get("EURO_NOW")
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else datetime.now(timezone.utc)


def kickoff(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(name: str):
    f = paths.OUT / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def merge(new_items: list, old_items: list, key: str, now: datetime) -> list:
    """New entries for matches still to play; old entries, unchanged, for started ones."""
    old = {x[key]: x for x in old_items or []}
    out, seen = [], set()
    for x in new_items:
        k = x[key]
        if kickoff(x["kickoff"]) <= now and k in old:
            out.append(old[k])
        elif kickoff(x["kickoff"]) > now:
            out.append(x)
        seen.add(k)
    for k, x in old.items():  # started matches no longer in the new list
        if k not in seen and now - timedelta(days=KEEP_DAYS) < kickoff(x["kickoff"]) <= now:
            out.append(x)
    return sorted(out, key=lambda x: x["kickoff"])


def main() -> int:
    now = now_utc()
    pred, rec = load("pred.json"), load("eurrec.json")
    old = load("euro_gameweek.json") or {}
    old_hist = load("history_seed.json") or []
    as_of = now.strftime("%Y-%m-%d %H:%M UTC")
    out = {"as_of": as_of}
    for comp in ("uel", "uecl"):
        rows = merge(pred["out"][comp], (old.get(comp) or {}).get("rows"), "id", now)
        out[comp] = {"rows": rows, "as_of": as_of, "test": rec["test"]}
    old_pairs = [dict(v, _id=k) for k, v in (old.get("pairs_matches") or {}).items()]
    new_pairs = [dict(v, _id=k) for k, v in pred["pairs"].items()]
    out["pairs_matches"] = {x.pop("_id"): x for x in merge(new_pairs, old_pairs, "_id", now)}
    out["safety_eur"], out["record_eur"] = rec["safety"], rec["record"]
    hist = merge(pred["hist"], old_hist, "match_id", now)
    (paths.OUT / "euro_gameweek.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    (paths.OUT / "history_seed.json").write_text(json.dumps(hist, indent=0), encoding="utf-8")
    kept = sum(1 for c in ("uel", "uecl") for r in out[c]["rows"] if kickoff(r["kickoff"]) <= now)
    print(f"wrote euro_gameweek.json: {sum(len(out[c]['rows']) for c in ('uel', 'uecl'))} matches ({kept} started, kept as locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
