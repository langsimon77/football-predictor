"""Corners and yellows: a safety factor for picks, which lines have skill, and what an
EPL referee update is worth. Rules fixed beforehand:
data/audit/preregistration_counts_safety_2026_10.md (Lang's request, 14 Oct 2026).

    uv run python scripts/counts_safety.py [--referee AS_NOW.parquet ALWAYS.parquet]

The two referee files come from fp.evaluate.backtest_counts (cards EPL 2023 2024 2025,
without and with --referee-always). Writes reports/counts_safety_2026_10.md and
data/audit/counts_safety_2026_10.json (which also holds the safety table the Model Lab
reads).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import backtest_phase3b as p3b  # noqa: E402
import pairs_lab  # noqa: E402

from fp.evaluate import metrics  # noqa: E402
from fp.ingest.matches import PROCESSED, TRIAL_DIR  # noqa: E402

CALIBRATION = (2021, 2022)
TEST = (2023, 2024, 2025)
Z90 = 1.2816  # one-sided 90%
MIN_CELL = 30
FAMILIES = ("corners", "yellows")
REPORT = ROOT / "reports" / "counts_safety_2026_10.md"
RESULTS = ROOT / "data" / "audit" / "counts_safety_2026_10.json"
GROUPS = {"live": (ROOT / "data" / "backtests", PROCESSED, "EPL and La Liga"),
          "trial": (ROOT / "data" / "backtests" / "trial", TRIAL_DIR, "Serie A and Ligue 1")}
DUMMY = np.full((11, 11), 1 / 121)  # goals picks are built too, then ignored


def wilson_lower(hits: float, n: float, z: float = Z90) -> float:
    if n <= 0:
        return float("nan")
    p = hits / n
    centre = p + z * z / (2 * n)
    spread = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((centre - spread) / (1 + z * z / n))


def load(group: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bt, processed, _ = GROUPS[group]
    corners = pd.read_parquet(bt / "corners_total_poisson_walkforward_2021_2025.parquet")
    cards = pd.read_parquet(bt / "cards_nb_walkforward_2021_2025.parquet")
    return corners, cards, pd.read_parquet(processed / "matches.parquet")


def count_picks(group: str) -> pd.DataFrame:
    """Every corners and yellows pick (both sides of each line) with its outcome."""
    corners, cards, matches = load(group)
    m = matches.set_index("match_id")
    cards = cards.set_index("match_id")
    rows = []
    for r in corners.itertuples():
        mid = r.match_id
        if mid not in cards.index or mid not in m.index:
            continue
        c = float(m.at[mid, "home_corners"] + m.at[mid, "away_corners"])
        y = float(m.at[mid, "home_yellows"] + m.at[mid, "away_yellows"])
        for p in pairs_lab.picks(DUMMY, r.pmf, cards.at[mid, "pmf"], "", ""):
            if p["fam"] not in FAMILIES:
                continue
            hit = pairs_lab.happened(p, 0, 0, c, y)
            if hit is None:
                continue
            rows.append({"match_id": mid, "league": r.league, "season": int(r.season),
                         "fam": p["fam"], "k": p["k"], "p": p["p"], "hit": bool(hit),
                         "band": min(int(p["p"] * 20), 19) / 20})
    return pd.DataFrame(rows)


def safety_table(picks: pd.DataFrame) -> pd.DataFrame:
    t = picks.groupby(["fam", "band"]).agg(n=("hit", "size"), hits=("hit", "sum"),
                                           mean_p=("p", "mean")).reset_index()
    t["lower90"] = [wilson_lower(h, n) for h, n in zip(t["hits"], t["n"], strict=True)]
    return t


def safe_chance(picks: pd.DataFrame, table: pd.DataFrame) -> np.ndarray:
    look = table.set_index(["fam", "band"])["lower90"]
    lower = np.array([look.get((f, b), np.nan) for f, b in
                      zip(picks["fam"], picks["band"], strict=True)])
    return np.minimum(picks["p"].to_numpy(), lower)  # nan where no track record


def check_s1(picks: pd.DataFrame) -> dict:
    cal = safety_table(picks[picks["season"].isin(CALIBRATION)])
    test = picks[picks["season"].isin(TEST)].copy()
    test["safe"] = safe_chance(test, cal)
    cells = test.groupby(["fam", "band"]).agg(n=("hit", "size"), rate=("hit", "mean"),
                                              safe=("safe", "mean"), model=("p", "mean"))
    cells = cells[cells["n"] >= MIN_CELL].dropna(subset=["safe"]).reset_index()
    cells["covered"] = cells["rate"] >= cells["safe"]
    return {"cells": cells.to_dict("records"), "share_covered": float(cells["covered"].mean()),
            "n_cells": len(cells), "pass": bool(cells["covered"].mean() >= 0.9),
            "no_record_share": float(test["safe"].isna().mean())}


def line_skill(group: str) -> list[dict]:
    corners, cards, matches = load(group)
    out = []
    for target, preds, lines, cols in (
            ("corners_total", corners, (8.5, 9.5, 10.5, 11.5), ("home_corners", "away_corners")),
            ("cards", cards, (3.5, 4.5, 5.5), ("home_yellows", "away_yellows"))):
        pr = preds[preds["season"].isin(TEST)].reset_index(drop=True)
        base = p3b.baselines(matches, target, pr["match_id"])["league_avg"]
        m = matches.set_index("match_id")
        y = (pr["match_id"].map(m[cols[0]]) + pr["match_id"].map(m[cols[1]])).to_numpy(float)
        k = np.arange(base.shape[1])
        for i, line in enumerate(lines):
            p_model = pr[f"p_over_{str(line).replace('.', '_')}"].to_numpy(float)
            p_base = base[:, k > line].sum(axis=1)
            happened = y > line
            d = (metrics.binary_log_loss(p_model, happened)
                 - metrics.binary_log_loss(p_base, happened))
            mean, lo, hi, _ = audit.interval(d, 10 + i)
            out.append({"market": "corners" if target != "cards" else "yellows", "line": line,
                        "n": len(pr), "observed_over": float(happened.mean()),
                        "model_log_loss": float(metrics.binary_log_loss(p_model, happened).mean()),
                        "diff": mean, "lo": lo, "hi": hi,
                        "verdict": "model better" if hi < 0 else "no clear difference"})
    return out


def referee_value(as_now: Path, always: Path) -> dict:
    a, b = pd.read_parquet(as_now), pd.read_parquet(always)
    both = a.merge(b, on="match_id", suffixes=("_now", "_all"))
    matches = pd.read_parquet(PROCESSED / "matches.parquet").set_index("match_id")
    y = (both["match_id"].map(matches["home_yellows"])
         + both["match_id"].map(matches["away_yellows"])).to_numpy(int)
    pmf_now = np.array([np.asarray(p, float) for p in both["pmf_now"]])
    pmf_all = np.array([np.asarray(p, float) for p in both["pmf_all"]])
    d = p3b.log_score(pmf_all, y) - p3b.log_score(pmf_now, y)
    known = both["referee_known_now"].astype(bool).to_numpy()
    mean, lo, hi, _ = audit.interval(d, 20)
    later = d[~known]
    m2, lo2, hi2, _ = audit.interval(later, 21)
    lines = {}
    for line in (3.5, 4.5, 5.5):
        col = f"p_over_{str(line).replace('.', '_')}"
        happened = y > line
        dl = (metrics.binary_log_loss(both[f"{col}_all"].to_numpy(float), happened)
              - metrics.binary_log_loss(both[f"{col}_now"].to_numpy(float), happened))
        lm, llo, lhi, _ = audit.interval(dl, 22)
        lines[str(line)] = {"diff": lm, "lo": llo, "hi": lhi}
    return {"n": len(both), "known_at_lock_share": float(known.mean()),
            "all": {"diff": mean, "lo": lo, "hi": hi},
            "unknown_at_lock_only": {"n": int((~known).sum()), "diff": m2, "lo": lo2, "hi": hi2},
            "lines": lines, "pass": bool(hi < 0)}


def write_report(res: dict) -> None:
    s1 = res["live"]["s1"]
    lines = ["# Corners and yellows: safety factor, line skill, referee update", "",
             "Generated by `scripts/counts_safety.py`. Rules fixed before the analysis: "
             "`data/audit/preregistration_counts_safety_2026_10.md`. Walk-forward forecasts of "
             "`corners_total_poisson_v1` and `cards_nb_v1`; test seasons 2023/24 to 2025/26.",
             "", "## A. Safety factor (EPL and La Liga)", "",
             "Safe chance = the lower of the model's chance and the lower end of a one-sided "
             "90% interval for how often picks of the same kind and band came true in "
             "2021/22 and 2022/23. Check on 2023/24 to 2025/26, cells with at least "
             f"{MIN_CELL} picks:", "",
             "| Market | Model chance band | Picks | Model said | Safe chance | Came true "
             "| Safe? |",
             "|---|---|---|---|---|---|---|"]
    for c in s1["cells"]:
        lines.append(f"| {c['fam']} | {c['band']:.0%} to {c['band'] + 0.05:.0%} | {c['n']} | "
                     f"{c['model']:.1%} | {c['safe']:.1%} | {c['rate']:.1%} | "
                     f"{'yes' if c['covered'] else '**no**'} |")
    lines += ["", f"Covered in {s1['share_covered']:.0%} of {s1['n_cells']} cells: "
              f"**{'pass' if s1['pass'] else 'fail'}** (bar: 90%). Picks with no track record "
              f"in their band: {s1['no_record_share']:.1%}.", "",
              "## C. Which lines have skill (log loss, model minus league average)", "",
              "| Leagues | Market | Line | Matches | Over came true | Model log loss | "
              "Difference | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for g in ("live", "trial"):
        for r in res[g]["skill"]:
            lines.append(f"| {GROUPS[g][2]} | {r['market']} | {r['line']} | {r['n']} | "
                         f"{r['observed_over']:.1%} | {r['model_log_loss']:.4f} | "
                         f"{r['diff']:+.4f} ({r['lo']:+.4f} to {r['hi']:+.4f}) | {r['verdict']} |")
    if "referee" in res:
        r = res["referee"]
        lines += ["", "## B. EPL referee update for yellows", "",
                  f"{r['n']} EPL matches, 2023/24 to 2025/26; referee known at lock for "
                  f"{r['known_at_lock_share']:.0%}. Log score of total yellows, every referee "
                  "known minus as now (negative = the update helps):", "",
                  f"- All matches: {r['all']['diff']:+.4f} ({r['all']['lo']:+.4f} to "
                  f"{r['all']['hi']:+.4f}): **{'pass' if r['pass'] else 'fail'}**.",
                  f"- Matches where the referee was not known at lock "
                  f"({r['unknown_at_lock_only']['n']}): {r['unknown_at_lock_only']['diff']:+.4f} "
                  f"({r['unknown_at_lock_only']['lo']:+.4f} to "
                  f"{r['unknown_at_lock_only']['hi']:+.4f}).",
                  "- By line (log loss): " + ", ".join(
                      f"over {k} {v['diff']:+.4f} ({v['lo']:+.4f} to {v['hi']:+.4f})"
                      for k, v in r["lines"].items()) + "."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--referee", nargs=2, type=Path, metavar=("AS_NOW", "ALWAYS"))
    args = ap.parse_args(argv)
    res: dict = {}
    for g in GROUPS:
        picks = count_picks(g)
        res[g] = {"skill": line_skill(g), "n_picks": len(picks)}
        if g == "live":
            res[g]["s1"] = check_s1(picks)
            full = safety_table(picks)
            # For the Model Lab: [band, n, hits, lower90] per market, all five seasons.
            res[g]["safety_table"] = {f: full[full["fam"] == f][["band", "n", "hits", "lower90"]]
                                      .round(4).values.tolist() for f in FAMILIES}
    if args.referee:
        res["referee"] = referee_value(*args.referee)
    RESULTS.write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    write_report(res)
    print(REPORT.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
