"""Safety margins and track records for Champions League picks, by the rule in
data/audit/preregistration_ucl_2026_10.md (addendum of 20 Oct 2026).

    uv run python scripts/ucl_safety.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import counts_safety as cs  # noqa: E402
import pick_safety as ps  # noqa: E402

BACKTEST = ROOT / "data" / "backtests" / "ucl" / "club_dc_walkforward_2021_2025.parquet"
RESULTS = ROOT / "data" / "audit" / "ucl_safety_2026_10.json"
FAMILIES = ("result", "dc", "dnb", "goals")


def picks(bt: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in bt.itertuples():
        ph, pd_, pa = r.club_dc_home, r.club_dc_draw, r.club_dc_away
        hg, ag = r.home_goals, r.away_goals
        cand = [("result", "H", ph, hg > ag), ("result", "D", pd_, hg == ag),
                ("result", "A", pa, hg < ag), ("dc", "1X", ph + pd_, hg >= ag),
                ("dc", "X2", pd_ + pa, hg <= ag), ("dc", "12", ph + pa, hg != ag)]
        if hg != ag:  # draw no bet: a draw refunds, so it has no verdict
            cand += [("dnb", "DNB-H", ph / (1 - pd_), hg > ag),
                     ("dnb", "DNB-A", pa / (1 - pd_), hg < ag)]
        for line, p in ((1.5, r.club_dc_over_1_5), (2.5, r.club_dc_over_2_5),
                        (3.5, r.club_dc_over_3_5)):
            cand += [("goals", f"G>{line}", p, hg + ag > line),
                     ("goals", f"G<{line}", 1 - p, hg + ag < line)]
        for fam, k, p, hit in cand:
            rows.append({"match_id": r.match_id, "season": int(r.season), "fam": fam, "k": k,
                         "p": float(p), "hit": bool(hit), "band": min(int(p * 20), 19) / 20})
    return pd.DataFrame(rows)


def main() -> int:
    pk = picks(pd.read_parquet(BACKTEST))
    res = {**ps.margins(pk, FAMILIES), "record": ps.record(pk)}
    RESULTS.write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    for fam in FAMILIES:
        f = res["families"][fam]
        c90, c95 = f["check90"], f["check95"]
        print(f"{fam}: {c90['n_cells']} groups, safe at 90% {c90['share_covered']:.0%}"
              + (f", at 95% {c95['share_covered']:.0%}" if c95 else "")
              + f" -> margin {f['level'] or 'none'}")
    print("test seasons used for the check:", cs.TEST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
