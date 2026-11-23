"""Build the hidden xG test file (pre-registration data/audit/preregistration_xg_2026_11.md).

Usage: python scripts/make_xg_test.py [--out data/xg_test/xg_test.json] [--now ISO]

The logic lives in src/fp/evaluate/xg_test.py (the monthly review uses it too). The file
holds the paired mean change per xG arm and no interval, bootstrap or verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fp.evaluate.xg_test import (  # noqa: E402, F401
    LEDGER,
    OUT,
    PART_A,
    PART_A_COLUMNS,
    build,
    load_ledgers,
    load_part_a,
    progress_line,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--now", default=None)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--part-a", type=Path, default=PART_A)
    args = ap.parse_args(argv)
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp(datetime.now(UTC))
    now = now.tz_convert("UTC") if now.tzinfo else now.tz_localize("UTC")
    preds, results = load_ledgers(args.ledger)
    data = build(preds, results, load_part_a(args.part_a), now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    # Counts only: the means stay in the file, out of the job log.
    print(f"xg_test.json: part A {data['parts']['A']['n']} matches, "
          f"part B {data['parts']['B']['n']} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
