"""CI guard: the ledger may only grow. No locked row may change or disappear.

Compares ledger/predictions.parquet in the working tree with the version at a
base commit (BASE_SHA env var, default HEAD~1). Passes if there is no ledger yet.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys

import pandas as pd

from fp import ROOT, ledger

LEDGER_PATH = "ledger/predictions.parquet"


def at_commit(sha: str) -> pd.DataFrame | None:
    result = subprocess.run(
        ["git", "show", f"{sha}:{LEDGER_PATH}"], cwd=ROOT, capture_output=True, check=False
    )
    if result.returncode != 0:
        return None  # no ledger at that commit
    return ledger.coerce(pd.read_parquet(io.BytesIO(result.stdout)))


def main() -> int:
    if not ledger.PREDICTIONS.exists():
        print("ledger check: no ledger yet, nothing to check")
        return 0
    current = ledger.load()
    ledger.verify_chain(current)
    base_sha = os.environ.get("BASE_SHA") or "HEAD~1"
    if set(base_sha) == {"0"}:  # first push to a branch
        base_sha = "HEAD~1"
    old = at_commit(base_sha)
    if old is not None:
        ledger.verify_append_only(old, current)
        print(f"ledger check: {len(old)} rows at {base_sha[:7]}, {len(current)} now; append-only")
    else:
        print(f"ledger check: chain OK over {len(current)} rows (no ledger at {base_sha[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
