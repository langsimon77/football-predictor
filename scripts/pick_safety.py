"""Safety margin for every pick family (Lang's request, 14 Oct 2026). Rules fixed
beforehand: data/audit/preregistration_safety_all_2026_10.md.

    uv run python scripts/pick_safety.py

Writes data/audit/pick_safety_2026_10.json (the table the Model Lab reads) and
appends a section to reports/counts_safety_2026_10.md's sibling,
reports/pick_safety_2026_10.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import counts_safety as cs  # noqa: E402
import pairs_lab  # noqa: E402
import shape_v1_rollout  # noqa: E402

from fp.ingest.matches import PROCESSED, TRIAL_DIR  # noqa: E402

BT = ROOT / "data" / "backtests"
RESULTS = ROOT / "data" / "audit" / "pick_safety_2026_10.json"
REPORT = ROOT / "reports" / "pick_safety_2026_10.md"
Z = {"90": 1.2816, "95": 1.6449}
NAMES = {"result": "Home, draw, away", "dc": "Double chance", "eh": "European handicap",
         "dnb": "Draw no bet", "goals": "Goal lines", "btts": "Both teams score",
         "corners": "Corners", "yellows": "Yellow cards"}


TRIAL_FAMILIES = ("result", "dc", "dnb", "yellows")  # the markets that passed (trial report)


def all_picks(group: str = "live") -> pd.DataFrame:
    """Every pick of every family for 2021/22 to 2025/26 with its outcome; the
    published goals forecast (with the goals fix, refitted monthly on the group's own
    forecasts). group "live": EPL and La Liga; "trial": Serie A and Ligue 1."""
    bt = BT if group == "live" else BT / "trial"
    matches = pd.read_parquet((PROCESSED if group == "live" else TRIAL_DIR) / "matches.parquet")
    gf = audit.goals_frame(bt / "dc_bayes_v1_walkforward_2021_2025.parquet", matches=matches)
    fixed, _ = shape_v1_rollout.rolling_tables(gf)
    corners = pd.read_parquet(bt / "corners_total_poisson_walkforward_2021_2025.parquet"
                              ).set_index("match_id")
    cards = pd.read_parquet(bt / "cards_nb_walkforward_2021_2025.parquet").set_index("match_id")
    m = matches.set_index("match_id")
    rows = []
    for idx, r in gf.iterrows():
        mid = r["match_id"]
        c = float(m.at[mid, "home_corners"] + m.at[mid, "away_corners"])
        y = float(m.at[mid, "home_yellows"] + m.at[mid, "away_yellows"])
        ps = pairs_lab.picks(fixed[idx], corners.at[mid, "pmf"] if mid in corners.index else None,
                             cards.at[mid, "pmf"] if mid in cards.index else None, "", "")
        for p in ps:
            hit = pairs_lab.happened(p, int(r["hg"]), int(r["ag"]), c, y)
            if hit is None:
                continue  # draw no bet on a draw: the stake comes back, no verdict
            q = p["p"] / (1 - p["refund"]) if p["fam"] == "dnb" else p["p"]
            rows.append({"match_id": mid, "season": int(r["season"]), "fam": p["fam"],
                         "k": p["k"], "p": q, "hit": bool(hit),
                         "band": min(int(q * 20), 19) / 20})
    return pd.DataFrame(rows)


def table(picks: pd.DataFrame, z: float) -> pd.DataFrame:
    t = picks.groupby(["fam", "band"]).agg(n=("hit", "size"), hits=("hit", "sum")).reset_index()
    t["lower"] = [cs.wilson_lower(h, n, z) for h, n in zip(t["hits"], t["n"], strict=True)]
    return t.rename(columns={"lower": "lower90"})  # the column name check_s1 reads


def check(picks: pd.DataFrame, fam: str, z: float) -> dict:
    sub = picks[picks["fam"] == fam]
    cal = table(sub[sub["season"].isin(cs.CALIBRATION)], z)
    test = sub[sub["season"].isin(cs.TEST)].copy()
    test["safe"] = cs.safe_chance(test, cal)
    cells = test.groupby(["fam", "band"]).agg(n=("hit", "size"), rate=("hit", "mean"),
                                              safe=("safe", "mean"), model=("p", "mean"))
    cells = cells[cells["n"] >= cs.MIN_CELL].dropna(subset=["safe"]).reset_index()
    cells["covered"] = cells["rate"] >= cells["safe"]
    share = float(cells["covered"].mean()) if len(cells) else float("nan")
    return {"cells": cells.to_dict("records"), "n_cells": len(cells), "share_covered": share,
            "pass": bool(len(cells) and share >= 0.9)}


def margins(picks: pd.DataFrame, families) -> dict:
    out: dict = {"families": {}, "safety_table": {}}
    for fam in families:
        res90 = check(picks, fam, Z["90"])
        level = "90" if res90["pass"] else None
        res95 = None
        if not res90["pass"]:
            res95 = check(picks, fam, Z["95"])
            level = "95" if res95["pass"] else None
        out["families"][fam] = {"check90": res90, "check95": res95, "level": level}
        if level is not None:
            full = table(picks[picks["fam"] == fam], Z[level])
            out["safety_table"][fam] = (full[["band", "n", "hits", "lower90"]].round(4)
                                        .values.tolist())
    return out


def record(picks: pd.DataFrame) -> dict:
    """How often picks came true on the test seasons, by family and 5-point band
    (the Model Lab's "came true in testing")."""
    t = picks[picks["season"].isin(cs.TEST)]
    g = t.groupby(["fam", "band"])["hit"].agg(["size", "sum"]).reset_index()
    return {fam: [[float(b), int(n), int(k)] for b, n, k in
                  zip(sub["band"], sub["size"], sub["sum"], strict=True)]
            for fam, sub in g.groupby("fam")}


def main() -> int:
    picks = all_picks()
    res: dict = {"families": {}, "safety_table": {}}
    trial_picks = all_picks("trial")
    trial_picks = trial_picks[trial_picks["fam"].isin(TRIAL_FAMILIES)]
    res["trial"] = {**margins(trial_picks, TRIAL_FAMILIES), "record": record(trial_picks)}
    for fam in NAMES:
        out = check(picks, fam, Z["90"])
        level = "90" if out["pass"] else None
        out95 = None
        if not out["pass"]:
            out95 = check(picks, fam, Z["95"])
            level = "95" if out95["pass"] else None
        res["families"][fam] = {"check90": out, "check95": out95, "level": level}
        if level is not None:
            full = table(picks[picks["fam"] == fam], Z[level])
            res["safety_table"][fam] = (full[["band", "n", "hits", "lower90"]].round(4)
                                        .values.tolist())
    RESULTS.write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    lines = ["# Safety margin for every pick", "",
             "Generated by `scripts/pick_safety.py`. Rules fixed beforehand: "
             "`data/audit/preregistration_safety_all_2026_10.md`. EPL and La Liga; margins "
             "built on 2021/22 and 2022/23, checked on 2023/24 to 2025/26 (groups of at least "
             f"{cs.MIN_CELL} picks). Pass: picks came true at least as often as the safe "
             "chance in 90% of groups.", "",
             "| Family | Groups | Safe at 90% | Result | Safe at 95% | Margin used |",
             "|---|---|---|---|---|---|"]
    for fam, name in NAMES.items():
        f = res["families"][fam]
        c90, c95 = f["check90"], f["check95"]
        lines.append(f"| {name} | {c90['n_cells']} | {c90['share_covered']:.0%} | "
                     f"{'pass' if c90['pass'] else 'fail'} | "
                     + (f"{c95['share_covered']:.0%}, {'pass' if c95['pass'] else 'fail'}"
                        if c95 else "not needed")
                     + " | " + (f"one-sided {f['level']}%" if f["level"]
                                else "none (plain price, flagged)") + " |")
    lines += ["", "## Groups that were not safe", ""]
    for fam, name in NAMES.items():
        f = res["families"][fam]
        chk = f["check95"] if f["level"] == "95" else f["check90"]
        bad = [c for c in chk["cells"] if not c["covered"]]
        if bad:
            lines.append(f"- {name}: " + "; ".join(
                f"{c['band']:.0%} to {c['band'] + 0.05:.0%} band: safe {c['safe']:.1%}, came "
                f"true {c['rate']:.1%} ({c['n']} picks)" for c in bad) + ".")
    lines += ["", "## Serie A and Ligue 1 (the markets shown there)", "",
              "| Family | Groups | Safe at 90% | Result | Safe at 95% | Margin used |",
              "|---|---|---|---|---|---|"]
    for fam in TRIAL_FAMILIES:
        f = res["trial"]["families"][fam]
        c90, c95 = f["check90"], f["check95"]
        lines.append(f"| {NAMES[fam]} | {c90['n_cells']} | {c90['share_covered']:.0%} | "
                     f"{'pass' if c90['pass'] else 'fail'} | "
                     + (f"{c95['share_covered']:.0%}, {'pass' if c95['pass'] else 'fail'}"
                        if c95 else "not needed")
                     + " | " + (f"one-sided {f['level']}%" if f["level"]
                                else "none (plain price, flagged)") + " |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
