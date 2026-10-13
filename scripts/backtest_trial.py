"""Serie A and Ligue 1 backtest (step 2), scored by the rules fixed beforehand in
data/audit/preregistration_trial_2026_10.md. The EPL and La Liga go through the same
code, as a reference.

1. Collect the GitHub artifacts into data/backtests/trial/:
       uv run python scripts/backtest_trial.py collect GOALS CORNERS CARDS CHALLENGERS
   (four run IDs of backtest.yml and backtest_ml.yml).
2. Score and write reports/trial_backtest_2026_10.md:
       uv run python scripts/backtest_trial.py report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import backtest_phase3b as p3b  # noqa: E402

from fp.ensemble import tiers  # noqa: E402
from fp.evaluate import backtest as bt  # noqa: E402
from fp.evaluate import metrics  # noqa: E402
from fp.ingest.matches import PROCESSED, TRIAL_DIR  # noqa: E402
from fp.models import shape  # noqa: E402

BT = ROOT / "data" / "backtests"
TRIAL = BT / "trial"
REPORT = ROOT / "reports" / "trial_backtest_2026_10.md"
RESULTS = ROOT / "data" / "audit" / "trial_backtest_2026_10.json"
TIERS_FILE = ROOT / "data" / "tiers" / "thresholds.json"
STACK_FILE = ROOT / "data" / "stacking" / "stack_1x2.json"
TEST = (2023, 2024, 2025)
CHALLENGERS = ["multinomial", "ordered_logit", "random_forest", "xgboost"]
NAMES = {"base": "League base rates", "elo": "Elo", "dc": "Fast Dixon-Coles",
         "bdc": "Bayesian, plain", "pub": "Bayesian with goals fix (published)",
         "stack": "Stack (live weights)", "mkt_sharp": "Sharp closing market",
         "multinomial": "Multinomial", "ordered_logit": "Ordered logit",
         "random_forest": "Random Forest", "xgboost": "XGBoost"}
STEM = {"goals": "dc_bayes_v1", "corners_total": "corners_total_poisson",
        "cards": "cards_nb"}
VARIANT = {"goals": "sot", "corners_total": "poisson", "cards": "nb"}


def path(group: str, name: str) -> Path:
    return (TRIAL if group == "trial" else BT) / name


# ------------------------------------------------------------------ collect
def collect(goals: str, corners: str, cards: str, challengers: str) -> None:
    TRIAL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for run in (goals, corners, cards, challengers):
            subprocess.run(["gh", "run", "download", run, "-D", f"{tmp}/{run}"], check=True)
        folder = Path(tmp)
        for target in ("goals", "corners_total", "cards"):
            preds, fits = p3b.load(folder, "trial", target, VARIANT[target])
            stem = f"{STEM[target]}_walkforward_2021_2025"
            preds.to_parquet(TRIAL / f"{stem}.parquet", index=False)
            fits.to_parquet(TRIAL / f"{stem}_fits.parquet", index=False)
            print(f"{target}: {len(preds)} predictions, {len(fits)} fits")
        found = list(folder.rglob("challengers_trial_walkforward_2021_2025*.parquet"))
        for f in found:
            name = f.name.replace("challengers_trial_", "challengers_").replace(".cv.", "_cv.")
            pd.read_parquet(f).to_parquet(TRIAL / name, index=False)
        print(f"challengers: {len(found)} files")


# ------------------------------------------------------------------ build
def goals(group: str, matches: pd.DataFrame) -> pd.DataFrame:
    """Plain Bayesian and published (goals fix refitted monthly on the group's own
    previous 730 days, the live rule) forecasts for every stored match."""
    f = audit.goals_frame(path(group, "dc_bayes_v1_walkforward_2021_2025.parquet"),
                          matches=matches)
    lam, nu = f["lam"].to_numpy(), f["nu"].to_numpy()
    hg, ag = f["hg"].to_numpy(), f["ag"].to_numpy()
    rows, history = audit.monthly(
        f, lambda idx, prev: shape.fit(lam[idx], nu[idx], hg[idx], ag[idx], prev),
        lambda sel, sh: list(shape.shaped(lam[sel], nu[sel], sh)), shape.POISSON)
    pub = audit.markets(np.stack(rows))
    plain = audit.markets(np.stack(f["M0"].to_numpy()))
    out = pd.DataFrame({"match_id": f["match_id"]})
    for prefix, mk in (("pub", pub), ("bdc", plain)):
        for i, k in enumerate(("home", "draw", "away")):
            out[f"{prefix}_{k}"] = mk["x12"][:, i]
        for k in ("over_1_5", "over_2_5", "over_3_5", "btts"):
            out[f"{prefix}_{k}"] = mk[k]
    iv = f["bdc_intervals"].map(json.loads)
    top = out[["pub_home", "pub_draw", "pub_away"]].to_numpy().argmax(1)
    names = np.array(["p_home", "p_draw", "p_away"])
    out["width_1x2"] = [d[n][1] - d[n][0] for d, n in zip(iv, names[top], strict=True)]
    out.attrs["history"] = history
    return out


def build(group: str) -> tuple[pd.DataFrame, dict]:
    matches = pd.read_parquet((TRIAL_DIR if group == "trial" else PROCESSED) /
                              "matches.parquet")
    fast = pd.read_parquet(path(group, "fast_walkforward_2021_2025.parquet"))
    frame = bt.attach_outcomes_and_market(fast, matches)
    g = goals(group, matches)
    frame = frame.merge(g, on="match_id", how="left")
    ch = pd.read_parquet(path(group, "challengers_walkforward_2021_2025.parquet"))
    for name, c in ch.groupby("model"):
        c = c.set_index("match_id")
        for k in ("home", "draw", "away"):
            frame[f"{name}_{k}"] = frame["match_id"].map(c[f"p_{k}"])
    stack = json.loads(STACK_FILE.read_text(encoding="utf-8"))
    comp = {"elo": "elo", "dc": "dc", "bdc": "pub", **{c: c for c in CHALLENGERS}}
    for k in ("home", "draw", "away"):
        frame[f"stack_{k}"] = sum(w * frame[f"{comp[m]}_{k}"]
                                  for m, w in zip(stack["models"], stack["weights"],
                                                  strict=True))
    fits = pd.read_parquet(path(group, "dc_bayes_v1_walkforward_2021_2025_fits.parquet"))
    counts = {}
    for target, stem in (("corners_total", "corners_total_poisson"), ("cards", "cards_nb")):
        pr = pd.read_parquet(path(group, f"{stem}_walkforward_2021_2025.parquet"))
        pr = pr[pr["season"].isin(TEST)].reset_index(drop=True)
        base = p3b.baselines(matches, target, pr["match_id"])
        cols = ("home_yellows", "away_yellows") if target == "cards" else \
            ("home_corners", "away_corners")
        m = matches.set_index("match_id")
        y = (pr["match_id"].map(m[cols[0]]) + pr["match_id"].map(m[cols[1]])).to_numpy(int)
        pmf = np.array([np.asarray(p, float) for p in pr["pmf"]])
        counts[target] = pd.DataFrame({
            "match_id": pr["match_id"], "league": pr["league"],
            "model": p3b.log_score(pmf, y),
            "league_avg": p3b.log_score(base["league_avg"], y),
            "team_avg": p3b.log_score(base["team_avg"], y),
            "mean_forecast": pmf @ np.arange(pmf.shape[1]), "actual": y})
    return frame, {"fits": fits, "counts": counts, "history": g.attrs["history"]}


# ------------------------------------------------------------------ scores
def probs(frame: pd.DataFrame, m: str) -> np.ndarray:
    return frame[[f"{m}_home", f"{m}_draw", f"{m}_away"]].to_numpy(float)


def rps(frame: pd.DataFrame, m: str) -> np.ndarray:
    return metrics.rps(probs(frame, m), frame["outcome"].to_numpy(int))


def over_loss(frame: pd.DataFrame, m: str, line: str = "over_2_5") -> np.ndarray:
    col = f"{m}_{line}" if m != "base" else "base_over_2_5"
    return metrics.binary_log_loss(frame[col].to_numpy(float), frame[line].to_numpy(bool))


def ci(d: np.ndarray, seed: int) -> dict:
    mean, lo, hi, _ = audit.interval(np.asarray(d, float), seed)
    return {"mean": mean, "lo": lo, "hi": hi, "n": len(d)}


def slope(p: np.ndarray, y: np.ndarray) -> float:
    """Calibration slope: logistic fit of the outcome on the forecast's log-odds,
    home, draw and away pooled. 1 is ideal; above 1 means too timid."""
    pp = np.clip(p, 1e-6, 1 - 1e-6).ravel()
    yy = np.eye(3)[y].ravel()
    x = np.log(pp / (1 - pp))

    def nll(ab: np.ndarray) -> float:
        z = ab[0] + ab[1] * x
        return float(np.sum(np.logaddexp(0, z) - yy * z))
    return float(minimize(nll, np.array([0.0, 1.0])).x[1])


def checks(frame: pd.DataFrame, extra: dict, league: str | tuple[str, ...]) -> dict:
    """The pre-registered checks on one league, or on several pooled."""
    group = (league,) if isinstance(league, str) else league
    t = frame[frame["league"].isin(group) & frame["season"].isin(TEST)]
    t = t.dropna(subset=["pub_home"])
    out: dict = {"n": len(t)}
    r_pub = rps(t, "pub")
    out["G1"] = ci(r_pub - rps(t, "base"), 1)
    out["G2"] = ci(r_pub - rps(t, "elo"), 2)
    sharp = t["mkt_sharp_home"].notna().to_numpy()
    out["G3"] = ci((r_pub - rps(t, "mkt_sharp"))[sharp], 3)
    out["G4"] = ci(over_loss(t, "pub") - over_loss(t, "base"), 4)
    fits = extra["fits"][extra["fits"]["league"].isin(group)]
    out["G5"] = {"passed": int(fits["ok"].sum()), "fits": len(fits),
                 "share": float(fits["ok"].mean())}
    for key, target in (("C1", "corners_total"), ("K1", "cards")):
        c = extra["counts"][target]
        c = c[c["league"].isin(group)]
        out[key] = ci((c["model"] - c["league_avg"]).to_numpy(), 5)
        out[key + "_team"] = ci((c["model"] - c["team_avg"]).to_numpy(), 6)
        out[key + "_means"] = {"forecast": float(c["mean_forecast"].mean()),
                               "actual": float(c["actual"].mean())}
    y = t["outcome"].to_numpy(int)
    models = ["base", "elo", "dc", "bdc", "pub", "stack", *CHALLENGERS]
    out["L"] = {m: float((probs(t, m).argmax(1) == y).mean()) for m in models
                if t[f"{m}_home"].notna().all()}
    out["pass"] = {
        "G1": out["G1"]["hi"] < 0, "G2": out["G2"]["hi"] < 0.002,
        "G3": out["G3"]["mean"] <= 0.010, "G4": out["G4"]["hi"] < 0,
        "G5": out["G5"]["share"] >= 0.95, "C1": out["C1"]["hi"] < 0,
        "K1": out["K1"]["hi"] < 0, "L": max(out["L"].values()) < 0.60}
    return out


def table_1x2(frame: pd.DataFrame, league: str) -> pd.DataFrame:
    t = frame[(frame["league"] == league) & frame["season"].isin(TEST)]
    models = ["base", "elo", "dc", "bdc", "pub", *CHALLENGERS, "stack", "mkt_sharp"]
    t = t.dropna(subset=[f"{m}_home" for m in models])
    y = t["outcome"].to_numpy(int)
    rows = []
    for m in models:
        p = probs(t, m)
        rows.append({"forecast": NAMES[m], "n": len(t),
                     "rps": float(metrics.rps(p, y).mean()),
                     "log_loss": float(metrics.log_loss(p, y).mean()),
                     "top_pick": float((p.argmax(1) == y).mean()),
                     "slope": slope(p, y) if m != "base" else float("nan")})
    return pd.DataFrame(rows)


def table_goals(frame: pd.DataFrame, league: str) -> pd.DataFrame:
    t = frame[(frame["league"] == league) & frame["season"].isin(TEST)]
    rows = []
    for line in ("over_1_5", "over_2_5", "over_3_5", "btts"):
        happened = {"over_1_5": t["home_goals"] + t["away_goals"] > 1.5,
                    "over_2_5": t["over_2_5"],
                    "over_3_5": t["home_goals"] + t["away_goals"] > 3.5,
                    "btts": (t["home_goals"] > 0) & (t["away_goals"] > 0)}[line].to_numpy(bool)
        row = {"market": {"over_1_5": "over 1.5", "over_2_5": "over 2.5", "over_3_5": "over 3.5",
                          "btts": "both teams score"}[line],
               "observed": float(happened.mean())}
        for m in ("bdc", "pub"):
            p = t[f"{m}_{line}"].to_numpy(float)
            row[f"{m}_mean"] = float(p.mean())
            row[f"{m}_log_loss"] = float(metrics.binary_log_loss(p, happened).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def table_tiers(frame: pd.DataFrame, league: str) -> pd.DataFrame:
    """The live 1x2 cut points applied as they are (widths: stored plain intervals,
    so the width cut is divided by the live widening factor, as in the switch-on)."""
    data = json.loads(TIERS_FILE.read_text(encoding="utf-8"))
    th = tiers.load(TIERS_FILE)["1x2"]
    ratio = data.get("width_scale", {}).get("1x2", 1.0)
    th = tiers.Thresholds(**{**vars(th), "width_max": (th.width_max or 0) / ratio})
    t = frame[(frame["league"] == league) & frame["season"].isin(TEST)]
    t = t.dropna(subset=["stack_home", "pub_home"])
    p, s = probs(t, "pub"), probs(t, "stack")
    level = tiers.assign(th, p.max(1), np.zeros(len(t), dtype=int),
                         width=t["width_1x2"].to_numpy(float),
                         disagree=0.5 * np.abs(s - p).sum(1))
    hit = p.argmax(1) == t["outcome"].to_numpy(int)
    return pd.DataFrame([{"level": lv, "n": int((level == lv).sum()),
                          "promised": float(p.max(1)[level == lv].mean()),
                          "came_true": float(hit[level == lv].mean())}
                         for lv in ("High", "Medium", "Low") if (level == lv).any()])


# ------------------------------------------------------------------ report
def md(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(map(str, frame.columns)) + " |\n|" + "---|" * len(frame.columns)
    body = "\n".join("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                                       for v in r) + " |" for r in frame.itertuples(index=False))
    return head + "\n" + body


def fmt(c: dict) -> str:
    return f"{c['mean']:+.4f} ({c['lo']:+.4f} to {c['hi']:+.4f})"


def clear_failures(r: dict) -> dict[str, bool]:
    """Amendment 1: a league is left out if its own interval lies wholly on the wrong
    side of a bar (or its own gap to the sharp close exceeds +0.010)."""
    return {"G1": r["G1"]["lo"] > 0, "G2": r["G2"]["lo"] > 0.002,
            "G3": r["G3"]["mean"] > 0.010, "G4": r["G4"]["lo"] > 0,
            "C1": r["C1"]["lo"] > 0, "K1": r["K1"]["lo"] > 0}


def verdicts(pooled: dict, per: dict[str, dict]) -> dict[str, dict[str, bool]]:
    """Which markets each league is proposed for, by the amended rule."""
    goals_pooled = all(pooled["pass"][k] for k in ("G1", "G2", "G3", "G4", "L"))
    out = {}
    for lg, r in per.items():
        fail = clear_failures(r)
        goals = goals_pooled and r["pass"]["G5"] and not any(
            fail[k] for k in ("G1", "G2", "G3", "G4"))
        out[lg] = {"goals": goals,
                   "corners": goals and pooled["pass"]["C1"] and not fail["C1"],
                   "yellows": goals and pooled["pass"]["K1"] and not fail["K1"]}
    return out


def report() -> int:
    groups = {g: build(g) for g in ("live", "trial")}
    res = {lg: checks(*groups[g], lg) for g, lgs in (("live", ("EPL", "LaLiga")),
                                                   ("trial", ("SerieA", "Ligue1")))
           for lg in lgs}
    res["trial_pooled"] = checks(*groups["trial"], ("SerieA", "Ligue1"))
    res["live_pooled"] = checks(*groups["live"], ("EPL", "LaLiga"))
    res["verdicts"] = verdicts(res["trial_pooled"], {lg: res[lg] for lg in ("SerieA", "Ligue1")})
    res["reference_verdicts"] = verdicts(res["live_pooled"],
                                         {lg: res[lg] for lg in ("EPL", "LaLiga")})
    for lg in ("SerieA", "Ligue1", "EPL", "LaLiga"):
        res[lg]["clear_failures"] = clear_failures(res[lg])
    RESULTS.write_text(json.dumps(res, indent=2, default=float) + "\n", encoding="utf-8")
    trial_frame, trial_extra = groups["trial"]
    rule = {"G1": "RPS minus base rates, upper end < 0",
            "G2": "RPS minus Elo, upper end < +0.002",
            "G3": "RPS minus sharp close, mean <= +0.010",
            "G4": "Over 2.5 log loss minus base rate, upper end < 0",
            "G5": "Weekly fits passing >= 95% (each league)",
            "C1": "Corners log score minus league average, upper end < 0",
            "K1": "Yellows log score minus league average, upper end < 0",
            "L": "Top-pick accuracy of every model < 60%"}

    def cell(r: dict, k: str) -> str:
        if k == "G5":
            return f"{r['G5']['passed']} of {r['G5']['fits']}"
        if k == "L":
            return f"highest {max(r['L'].values()):.1%}"
        return fmt(r[k])

    def judged(r: dict, k: str, pooled: bool) -> str:
        if pooled:
            return f"{cell(r, k)}, {'pass' if r['pass'][k] else '**fail**'}"
        if k == "G5":
            return f"{cell(r, k)}, {'pass' if r['pass'][k] else '**fail**'}"
        if k == "L":
            return cell(r, k)
        return f"{cell(r, k)}" + (", **clear failure**" if r["clear_failures"][k] else "")

    lines = [
        "# Serie A and Ligue 1 backtest", "",
        "Generated by `scripts/backtest_trial.py`. Rules fixed before any trial forecast was "
        "scored: `data/audit/preregistration_trial_2026_10.md` with amendment 1 (checks on "
        "the two leagues pooled; a league is left out if it clearly fails by itself). "
        "Walk-forward, 2021/22 to 2025/26, live code and settings; checks on the test seasons "
        "2023/24 to 2025/26. Differences are the published forecast minus the benchmark, with "
        "95% paired bootstrap intervals (4,000 resamples); negative means the published "
        "forecast is better. The EPL and La Liga run through the same code, for reference.",
        "", "## The checks", "",
        "| Check | Rule | Trial pooled (decides) | Serie A | Ligue 1 | Live pooled (reference) "
        "| EPL | La Liga |", "|---|---|---|---|---|---|---|---|"]
    for k in rule:
        lines.append(" | ".join([
            f"| {k}", rule[k], judged(res["trial_pooled"], k, k != "G5"),
            judged(res["SerieA"], k, False), judged(res["Ligue1"], k, False),
            cell(res["live_pooled"], k), cell(res["EPL"], k), cell(res["LaLiga"], k)]) + " |")
    lines += ["", f"Test matches: Serie A {res['SerieA']['n']}, Ligue 1 {res['Ligue1']['n']} "
              f"(EPL {res['EPL']['n']}, La Liga {res['LaLiga']['n']}).", "", "## Verdict", ""]
    for lg, name in (("SerieA", "Serie A"), ("Ligue1", "Ligue 1")):
        v = res["verdicts"][lg]
        markets = [m for m in ("goals", "corners", "yellows") if v[m]]
        lines.append(f"- **{name}**: " + (
            "proposed for background running of its " + ", ".join(markets) + " markets."
            if markets else "not proposed (a goals check fails)."))
    ref = res["reference_verdicts"]
    lines.append("- Reference: the same rule applied to the EPL and La Liga proposes "
                 + "; ".join(f"{n} for " + ", ".join(m for m in ("goals", "corners", "yellows")
                                                       if ref[lg][m])
                             for lg, n in (("EPL", "the EPL"), ("LaLiga", "La Liga")))
                 + ".")
    lines += ["", "## Home, draw, away (test seasons, matches every forecast priced)", ""]
    for lg, name in (("SerieA", "Serie A"), ("Ligue1", "Ligue 1"), ("EPL", "EPL"),
                     ("LaLiga", "La Liga")):
        g = "trial" if lg in ("SerieA", "Ligue1") else "live"
        lines += [f"### {name}", "", md(table_1x2(groups[g][0], lg)), ""]
    lines += ["Calibration slope: 1 is ideal, above 1 means too timid.", "",
              "## Goal lines and both teams score (test seasons, log loss)", ""]
    for lg, name in (("SerieA", "Serie A"), ("Ligue1", "Ligue 1")):
        lines += [f"### {name}", "", md(table_goals(trial_frame, lg)), ""]
    lines += ["## Context: how predictable are goal totals? (report only)", "",
              "Over 2.5 goals log loss on test matches with a sharp closing price. The market "
              "column shows how much even the sharpest price beats the base rate.", "",
              "| League | n | Base rate | Sharp market | Market minus base | Published | "
              "Published minus base |", "|---|---|---|---|---|---|---|"]
    for g, grp, name in (("trial", ("SerieA", "Ligue1"), "Serie A and Ligue 1"),
                         ("trial", ("SerieA",), "Serie A"), ("trial", ("Ligue1",), "Ligue 1"),
                         ("live", ("EPL", "LaLiga"), "EPL and La Liga"),
                         ("live", ("EPL",), "EPL"), ("live", ("LaLiga",), "La Liga")):
        f = groups[g][0]
        t = f[f["league"].isin(grp) & f["season"].isin(TEST)].dropna(
            subset=["pub_over_2_5", "mkt_sharp_over_2_5"])
        base, mkt, pub = (over_loss(t, m) for m in ("base", "mkt_sharp", "pub"))
        lines.append(f"| {name} | {len(t)} | {base.mean():.4f} | {mkt.mean():.4f} | "
                     f"{fmt(ci(mkt - base, 7))} | {pub.mean():.4f} | {fmt(ci(pub - base, 8))} |")
    lines += ["", "## Corners and yellows (test seasons)", "",
              "| League | Market | Model minus league average | Model minus team average "
              "| Mean forecast | Mean actual |", "|---|---|---|---|---|---|"]
    for lg, name in (("SerieA", "Serie A"), ("Ligue1", "Ligue 1"), ("EPL", "EPL"),
                     ("LaLiga", "La Liga")):
        for k, market in (("C1", "corners"), ("K1", "yellows")):
            r = res[lg]
            lines.append(f"| {name} | {market} | {fmt(r[k])} | {fmt(r[k + '_team'])} | "
                         f"{r[k + '_means']['forecast']:.2f} | {r[k + '_means']['actual']:.2f} |")
    lines += ["", "## Confidence levels with the live cut points (home, draw, away)", "",
              "Report only. The live cut points were set on EPL and La Liga forecasts.", ""]
    for lg, name in (("SerieA", "Serie A"), ("Ligue1", "Ligue 1")):
        lines += [f"### {name}", "", md(table_tiers(trial_frame, lg)), ""]
    hist = trial_extra["history"]
    last = [h for h in hist if h[0] >= "2023-08"][:1] + hist[-1:]
    lines += ["## Goals fix numbers on the trial leagues", "",
              "Refitted at the first lock of each month on the previous 730 days of the two "
              "trial leagues' own forecasts.", "",
              "| Month | Matches of history | Home dispersion | Away dispersion | Rho | Stretch |",
              "|---|---|---|---|---|---|"]
    for mth, n, sh in last:
        lines.append(f"| {mth} | {n} | {sh.vh:.3f} | {sh.va:.3f} | {sh.rho:+.4f} | {sh.s:+.4f} |")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT} and {RESULTS}")
    for lg in ("SerieA", "Ligue1"):
        print(lg, res[lg]["pass"])
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    for name in ("goals", "corners", "cards", "challengers"):
        c.add_argument(name)
    sub.add_parser("report")
    args = ap.parse_args(argv)
    if args.cmd == "collect":
        collect(args.goals, args.corners, args.cards, args.challengers)
        return 0
    return report()


if __name__ == "__main__":
    sys.exit(main())
