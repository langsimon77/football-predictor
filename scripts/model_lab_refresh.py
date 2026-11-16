"""Checks for the routine that copies the daily Model Lab data files to the page.

The daily job writes gameweek.json, core.json and history-seed.json to the branch
`lab-data` (scripts/build_model_lab.py --out-dir). A scheduled Claude routine (see
docs/CHECKPOINT.md for whether it is switched on) fetches that branch, runs this script, and
publishes the files to the page only when this script says so.

    python3 scripts/model_lab_refresh.py check DIR [--live-gameweek FILE] [--now ISO]
        exit 0 and "PUBLISH" : the files are sound and newer than the page's
        exit 0 and "SKIP ..."  : nothing to do (the page already has them)
        exit 1                : the files are not sound; publish nothing

    python3 scripts/model_lab_refresh.py history DIR --have IDS.json --out OUT_DIR [--now ISO]
        writes one JSON file per match that the page's History has no record of yet and
        whose forecast is final (kickoff within the next 24 hours, or up to 3 days ago)

Standard library only, so the routine needs no install step.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc  # noqa: UP017  (the routine's Python may be older than 3.11)
FILES = ("gameweek", "core", "history-seed")
MAX_AGE_HOURS = 36
MIN_BYTES = {"gameweek": 50_000, "core": 500_000, "history-seed": 2}
BANNED = (chr(0x2014), chr(0x2013))  # the page text carries no em or en dashes


def parse_time(text: str) -> datetime:
    text = text.strip().replace(" UTC", "").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"not a time: {text!r}")


def _no_constants(name: str) -> None:
    raise ValueError(f"not a number in the data: {name}")


def load(folder: Path) -> dict[str, object]:
    out = {}
    for name in FILES:
        path = folder / f"{name}.json"
        if not path.exists():
            raise ValueError(f"{name}.json is missing")
        text = path.read_text(encoding="utf-8")
        if len(text) < MIN_BYTES[name]:
            raise ValueError(f"{name}.json is too small ({len(text)} bytes)")
        out[name] = json.loads(text, parse_constant=_no_constants)  # NaN or Infinity
        if any(ch in json.dumps(out[name], ensure_ascii=False) for ch in BANNED):
            raise ValueError(f"{name}.json contains a banned dash")
    return out


def check(folder: Path, now: datetime, live_gameweek: Path | None) -> str:
    files = load(folder)
    gw = files["gameweek"]
    if not isinstance(gw, dict) or not isinstance(files["core"], dict):
        raise ValueError("gameweek.json and core.json must be objects")
    for key in ("built", "data_as_of", "up", "trial", "ucl", "pairs", "clubs"):
        if key not in gw:
            raise ValueError(f"gameweek.json has no {key!r}")
    for key in ("bt", "sim", "ev"):
        if key not in files["core"]:
            raise ValueError(f"core.json has no {key!r}")
    if gw.get("bets") is not None:
        raise ValueError("gameweek.json carries a bets block; the public job must never do so")
    if not isinstance(files["history-seed"], list):
        raise ValueError("history-seed.json must be a list")
    built = parse_time(str(gw["built"]))
    age = (now - built).total_seconds() / 3600
    if age > MAX_AGE_HOURS:
        raise ValueError(f"the files were built {age:.0f} hours ago (limit {MAX_AGE_HOURS})")
    if built > now + timedelta(hours=1):
        raise ValueError("the files claim to be built in the future")
    if live_gameweek is not None and live_gameweek.exists():
        live = json.loads(live_gameweek.read_text(encoding="utf-8"))
        if parse_time(str(live.get("built", "2000-01-01 00:00"))) >= built:
            return f"SKIP the page already has data built {live.get('built')}"
    return f"PUBLISH built {gw['built']}, forecasts of {gw['data_as_of']}"


def history(folder: Path, have: set[str], now: datetime) -> list[dict]:
    """Records to create: matches the History has not got, once their forecast is final.
    A forecast locks 24 to 48 hours before kickoff, so from 24 hours before kickoff the
    seed holds the locked forecast."""
    stamp = f"{now:%Y-%m-%dT%H:%MZ}"
    out = []
    for doc in load(folder)["history-seed"]:
        kickoff = parse_time(str(doc["kickoff"]))
        if doc["match_id"] in have or not doc.get("calls"):
            continue
        if now - timedelta(days=3) <= kickoff <= now + timedelta(hours=24):
            out.append({**doc, "created_utc": stamp, "updated_utc": stamp,
                        "created_by": "Claude (auto)"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("check", "history"))
    ap.add_argument("folder", type=Path)
    ap.add_argument("--live-gameweek", type=Path, default=None)
    ap.add_argument("--have", type=Path, default=None, help="JSON list of History record ids")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--now", default=None)
    args = ap.parse_args(argv)
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    try:
        if args.action == "check":
            print(check(args.folder, now, args.live_gameweek))
            return 0
        have = set(json.loads(args.have.read_text(encoding="utf-8"))) if args.have else set()
        docs = history(args.folder, have, now)
        if args.out is not None:
            args.out.mkdir(parents=True, exist_ok=True)
            for doc in docs:
                (args.out / f"{doc['match_id']}.json").write_text(
                    json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(f"{len(docs)} new History records" + (": " + ", ".join(
            d["match_id"] for d in docs) if docs else ""))
        return 0
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"INVALID {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
