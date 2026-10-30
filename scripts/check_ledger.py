"""CI guard: the ledgers may only grow. No locked row may change or disappear.

Compares each ledger (the live one; since 13 Oct 2026 the trial one in ledger/trial/;
since 20 Oct 2026 the Champions League one in ledger/ucl/; since 30 Oct 2026 the
basketball one in ledger/basketball/, with its own columns) in the working tree with its
version at a base commit (BASE_SHA env var, default HEAD~1). Passes for a ledger that does
not exist yet.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys

import pandas as pd

from fp import ROOT, ledger

sys.path.insert(0, str(ROOT / "basketball"))
import ledger_bb  # noqa: E402

LEDGER_PATHS = ("ledger/predictions.parquet", "ledger/trial/predictions.parquet",
                "ledger/ucl/predictions.parquet", "ledger/basketball/predictions.parquet")


def kind(path: str):
    """The ledger module for a path: basketball rows have their own columns."""
    return ledger_bb if path.startswith("ledger/basketball/") else ledger


def at_commit(sha: str, path: str) -> pd.DataFrame | None:
    result = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=ROOT, capture_output=True, check=False
    )
    if result.returncode != 0:
        return None  # no ledger at that commit
    return kind(path).coerce(pd.read_parquet(io.BytesIO(result.stdout)))


def main() -> int:
    base_sha = os.environ.get("BASE_SHA") or "HEAD~1"
    if set(base_sha) == {"0"}:  # first push to a branch
        base_sha = "HEAD~1"
    for path in LEDGER_PATHS:
        if not (ROOT / path).exists():
            print(f"ledger check: no {path} yet, nothing to check")
            continue
        mod = kind(path)
        current = mod.load(ROOT / path)
        mod.verify_chain(current)
        old = at_commit(base_sha, path)
        if old is not None:
            mod.verify_append_only(old, current)
            print(f"ledger check: {path}: {len(old)} rows at {base_sha[:7]}, {len(current)} now; "
                  "append-only")
        else:
            print(f"ledger check: {path}: chain OK over {len(current)} rows "
                  f"(none at {base_sha[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
