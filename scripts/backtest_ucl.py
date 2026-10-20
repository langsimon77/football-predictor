"""Champions League walk-forward test. Rules fixed beforehand:
data/audit/preregistration_ucl_2026_10.md (written 20 Oct 2026, before any forecast).

Every Champions League match of 2021/22 to 2025/26 with a result is predicted at its
lock time (fp.validate.leakage.lock_time) by:
- club_dc: fp.models.club_dc on domestic and European results known at the lock;
- elo: a goal-difference Elo over the same results, its rating gap mapped to home,
  draw, away by an ordered logit refitted at each lock on earlier European matches;
- base: Champions League home, draw, away and over 2.5 frequencies (previous 1,100 days,
  neutral grounds left out);
- club_dc_europe (report only): the same model on European results alone.

    uv run python scripts/backtest_ucl.py [--matches PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import backtest_trial  # noqa: E402

from fp.evaluate import metrics  # noqa: E402
from fp.ingest import europe  # noqa: E402
from fp.models import club_dc  # noqa: E402
from fp.models.elo import margin_multiplier  # noqa: E402
from fp.validate.leakage import lock_time  # noqa: E402

SEASONS = (2021, 2022, 2023, 2024, 2025)
OUT = ROOT / "data" / "backtests" / "ucl" / "club_dc_walkforward_2021_2025.parquet"
REPORT = ROOT / "reports" / "ucl_backtest_2026_10.md"
RESULTS = ROOT / "data" / "audit" / "ucl_backtest_2026_10.json"
ELO_K, ELO_HOME, WINDOW = 20.0, 60.0, pd.Timedelta(days=1100)


def country_map() -> dict[str, str]:
    a = pd.read_csv(europe.ALIASES_CSV)
    return dict(zip(a["club_id"], a["country"], strict=True))


def elo_gaps(matches: pd.DataFrame, targets: pd.DataFrame) -> tuple[dict, dict]:
    """Pre-match rating gaps: for every European match at its kickoff (for fitting the
    gap curve) and for every target at its lock. Ratings move only when a result is
    known (result_available_utc), so nothing after a lock reaches its forecast."""
    events = []
    for r in matches.itertuples():
        if pd.notna(r.home_goals):
            events.append((r.result_available_utc, 1, "update", r))
        if r.kind == "europe":
            events.append((r.kickoff_utc, 0, "europe", r))
    for r in targets.itertuples():
        events.append((r.lock_utc, 0, "target", r))
    events.sort(key=lambda e: (e[0], e[1]))
    rating: dict[str, float] = {}
    europe_gap, target_gap = {}, {}
    for _, _, what, r in events:
        h = 0.0 if r.neutral else ELO_HOME
        gap = rating.get(r.home_id, 1500.0) + h - rating.get(r.away_id, 1500.0)
        if what == "europe":
            europe_gap[r.match_id] = gap
        elif what == "target":
            target_gap[r.match_id] = gap
        else:
            exp = 1 / (1 + 10 ** (-gap / 400))
            hg, ag = int(r.home_goals), int(r.away_goals)
            act = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
            delta = ELO_K * margin_multiplier(abs(hg - ag)) * (act - exp)
            rating[r.home_id] = rating.get(r.home_id, 1500.0) + delta
            rating[r.away_id] = rating.get(r.away_id, 1500.0) - delta
    return europe_gap, target_gap


def ordered_logit(gap: np.ndarray, y: np.ndarray) -> np.ndarray:
    """(c1, c2, b): P(away) = s(c1 - b g), P(away or draw) = s(c2 - b g)."""
    def nll(th):
        c1, c2, b = th[0], th[0] + np.exp(th[1]), th[2]
        pa = expit(c1 - b * gap)
        pad = expit(c2 - b * gap)
        p = np.where(y == 2, pa, np.where(y == 1, pad - pa, 1 - pad))
        return -np.sum(np.log(np.clip(p, 1e-12, 1)))
    th = minimize(nll, np.array([-1.0, 0.0, 0.005]), method="Nelder-Mead",
                  options={"maxiter": 4000, "xatol": 1e-7, "fatol": 1e-9}).x
    return np.array([th[0], th[0] + np.exp(th[1]), th[2]])


def ol_probs(th: np.ndarray, gap: float) -> tuple[float, float, float]:
    pa = float(expit(th[0] - th[2] * gap))
    pad = float(expit(th[1] - th[2] * gap))
    return 1 - pad, pad - pa, pa


def run(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cmap = club_dc.countries(matches, country_map())
    ucl = matches[(matches["competition"] == "UCL")]
    targets = ucl[ucl["season"].isin(SEASONS) & ucl["home_goals"].notna()].copy()
    targets["lock_utc"] = lock_time(targets["kickoff_utc"])
    eu_gap, tg_gap = elo_gaps(matches, targets)
    eu = matches[matches["kind"] == "europe"].dropna(subset=["home_goals"]).copy()
    eu["gap"] = eu["match_id"].map(eu_gap)
    eu["y"] = metrics.outcome_1x2(eu["home_goals"].to_numpy(int), eu["away_goals"].to_numpy(int))
    europe_only = matches[matches["kind"] == "europe"]
    rows, fits = [], []
    for lock_key, group in targets.groupby("lock_utc", sort=True):
        lock = cast(pd.Timestamp, lock_key)
        clubs = tuple(sorted(set(group["home_id"]) | set(group["away_id"])))
        t0 = time.time()
        f = club_dc.fit(matches, lock, cmap, clubs)
        fe = club_dc.fit(europe_only, lock, cmap, clubs)
        fits.append({"lock_utc": lock, "seconds": time.time() - t0, "converged": f.converged,
                     "converged_europe": fe.converged, "n_matches": f.n_matches})
        past = eu[(eu["result_available_utc"] <= lock)
                  & (eu["kickoff_utc"] >= lock - WINDOW)]
        th = ordered_logit(past["gap"].to_numpy(), past["y"].to_numpy())
        cl_past = past[(past["competition"] == "UCL") & ~past["neutral"].astype(bool)]
        base = np.bincount(cl_past["y"], minlength=3) / len(cl_past)
        base_o25 = float(((cl_past["home_goals"] + cl_past["away_goals"]) > 2.5).mean())
        source_max = matches.loc[matches["result_available_utc"] <= lock,
                                 "result_available_utc"].max()
        for r in group.itertuples():
            m = f.markets(r.home_id, r.away_id, bool(r.neutral))
            me = fe.markets(r.home_id, r.away_id, bool(r.neutral))
            e = ol_probs(th, tg_gap[r.match_id])
            rows.append({
                "match_id": r.match_id, "season": r.season, "round": r.round,
                "kickoff_utc": r.kickoff_utc, "lock_utc": lock, "as_of_utc": lock,
                "source_max_utc": source_max, "neutral": bool(r.neutral),
                "home_id": r.home_id, "away_id": r.away_id,
                "home_goals": int(r.home_goals), "away_goals": int(r.away_goals),
                "club_dc_home": m["p_home"], "club_dc_draw": m["p_draw"],
                "club_dc_away": m["p_away"], "club_dc_over_2_5": m["p_over_2_5"],
                "club_dc_over_1_5": m["p_over_1_5"], "club_dc_over_3_5": m["p_over_3_5"],
                "club_dc_europe_home": me["p_home"], "club_dc_europe_draw": me["p_draw"],
                "club_dc_europe_away": me["p_away"], "club_dc_europe_over_2_5": me["p_over_2_5"],
                "elo_home": e[0], "elo_draw": e[1], "elo_away": e[2],
                "base_home": base[0], "base_draw": base[1], "base_away": base[2],
                "base_over_2_5": base_o25,
                "home_country": cmap[r.home_id], "away_country": cmap[r.away_id],
            })
        print(f"{lock:%Y-%m-%d} {len(group)} matches, fit {time.time() - t0:.1f}s", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(fits)


def score(out: pd.DataFrame, fits: pd.DataFrame) -> dict:
    y = metrics.outcome_1x2(out["home_goals"].to_numpy(), out["away_goals"].to_numpy())
    o25 = (out["home_goals"] + out["away_goals"]).to_numpy() > 2.5
    P = {m: out[[f"{m}_home", f"{m}_draw", f"{m}_away"]].to_numpy(float)
         for m in ("club_dc", "club_dc_europe", "elo", "base")}
    rps = {m: metrics.rps(p, y) for m, p in P.items()}
    ll = {m: metrics.log_loss(p, y) for m, p in P.items()}
    ou = {m: metrics.binary_log_loss(out[f"{m}_over_2_5"].to_numpy(float), o25)
          for m in ("club_dc", "club_dc_europe", "base")}
    def ci(d, s):
        return dict(zip(("mean", "lo", "hi"), audit.interval(np.asarray(d), s)[:3], strict=True))
    res: dict = {"n": len(out), "dates": [f"{out['kickoff_utc'].min():%Y-%m-%d}",
                                         f"{out['kickoff_utc'].max():%Y-%m-%d}"]}
    res["U1"] = ci(rps["club_dc"] - rps["base"], 1)
    res["U2"] = ci(rps["club_dc"] - rps["elo"], 2)
    res["U3"] = ci(ou["club_dc"] - ou["base"], 3)
    res["europe_only_minus_full"] = ci(rps["club_dc_europe"] - rps["club_dc"], 4)
    res["table"] = {m: {"rps": float(rps[m].mean()), "log_loss": float(ll[m].mean()),
                        "brier": float(metrics.brier(P[m], y).mean()),
                        "top_pick": float((P[m].argmax(1) == y).mean()),
                        "slope": backtest_trial.slope(P[m], y) if m != "base" else None,
                        "over_2_5_log_loss": float(ou[m].mean()) if m in ou else None}
                    for m in P}
    res["U4"] = {"fits": len(fits), "converged": int(fits["converged"].sum()),
                 "top_pick_max": max(v["top_pick"] for v in res["table"].values())}
    res["pass"] = {"U1": res["U1"]["hi"] < 0, "U2": res["U2"]["hi"] < 0.002,
                   "U3": res["U3"]["hi"] < 0,
                   "U4": res["U4"]["converged"] == res["U4"]["fits"]
                   and res["U4"]["top_pick_max"] < 0.60}
    res["by_season"] = {int(s): {"n": int((out["season"] == s).sum()),
                                 "club_dc_minus_elo_rps": float((rps["club_dc"] - rps["elo"])[
                                     (out["season"] == s).to_numpy()].mean())}
                        for s in SEASONS}
    return res


def write_report(res: dict) -> None:
    f = lambda c: f"{c['mean']:+.4f} ({c['lo']:+.4f} to {c['hi']:+.4f})"  # noqa: E731
    ok = lambda k: "pass" if res["pass"][k] else "**fail**"  # noqa: E731
    names = {"club_dc": "Club Dixon-Coles (domestic and European results)",
             "club_dc_europe": "Same model, European results only (report only)",
             "elo": "Elo (same results)", "base": "Champions League base rates"}
    lines = ["# Champions League walk-forward test", "",
             "Generated by `scripts/backtest_ucl.py`. Rules fixed beforehand: "
             "`data/audit/preregistration_ucl_2026_10.md`. Every Champions League match of "
             f"2021/22 to 2025/26 with a result ({res['n']} matches, {res['dates'][0]} to "
             f"{res['dates'][1]}), each predicted at its lock time from results known then. "
             "Differences: model minus benchmark, 95% paired bootstrap intervals; negative "
             "means the model is better. No market benchmark (no free Champions League odds).",
             "", "## The checks", "", "| Check | Rule | Result |", "|---|---|---|",
             f"| U1 | RPS minus base rates, upper end < 0 | {f(res['U1'])}, {ok('U1')} |",
             f"| U2 | RPS minus Elo, upper end < +0.002 | {f(res['U2'])}, {ok('U2')} |",
             f"| U3 | Over 2.5 log loss minus base rate, upper end < 0 | {f(res['U3'])}, "
             f"{ok('U3')} |",
             f"| U4 | Every fit converges; top pick below 60% | {res['U4']['converged']} of "
             f"{res['U4']['fits']} fits; highest top pick {res['U4']['top_pick_max']:.1%}, "
             f"{ok('U4')} |", "",
             "## Every forecast", "",
             "| Forecast | RPS | Log loss | Brier | Top pick right | Calibration slope "
             "| Over 2.5 log loss |",
             "|---|---|---|---|---|---|---|"]
    for m, v in res["table"].items():
        lines.append(f"| {names[m]} | {v['rps']:.4f} | {v['log_loss']:.4f} | {v['brier']:.4f} | "
                     f"{v['top_pick']:.1%} | "
                     + (f"{v['slope']:.3f}" if v["slope"] is not None else "") + " | "
                     + (f"{v['over_2_5_log_loss']:.4f}" if v["over_2_5_log_loss"] is not None
                        else "") + " |")
    lines += ["", f"European results only, minus the full model (RPS): "
              f"{f(res['europe_only_minus_full'])}. Positive means the domestic results help.",
              "", "Model minus Elo (RPS) by season: " + ", ".join(
                  f"{s}/{(s + 1) % 100:02d} {v['club_dc_minus_elo_rps']:+.4f} (n {v['n']})"
                  for s, v in res["by_season"].items()) + ".", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=Path, help="a saved fp.ingest.europe.all_matches() table")
    args = ap.parse_args(argv)
    matches = pd.read_parquet(args.matches) if args.matches else europe.all_matches()
    out, fits = run(matches)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    fits.to_parquet(OUT.with_name(OUT.stem + "_fits.parquet"), index=False)
    res = score(out, fits)
    RESULTS.write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    write_report(res)
    print(REPORT.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
