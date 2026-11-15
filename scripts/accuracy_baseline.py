"""Baseline accuracy of every live market on matches the models never saw.

Review of Nov 2026 (checklist C1 and C5). Nothing is fitted here: the script reads the
stored walk-forward forecasts and results, scores them, and writes
reports/accuracy_baseline_2026_11.md and data/audit/accuracy_baseline_2026_11.json.

    uv run python scripts/accuracy_baseline.py

Scores (lower is better for all but the slope):
- log loss, with a 95% bootstrap interval (2,000 resamples of matches);
- Brier score; ranked probability score (RPS) for home, draw, away;
- calibration slope: a logistic fit of the outcome on the forecast's log-odds. 1 is honest,
  above 1 too cautious, below 1 too bold. Outside 0.8 to 1.2 the market is flagged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_trial as trial  # noqa: E402

from fp import ROOT  # noqa: E402
from fp.evaluate import metrics  # noqa: E402
from fp.ingest.matches import PROCESSED, TRIAL_DIR  # noqa: E402

REPORT = ROOT / "reports" / "accuracy_baseline_2026_11.md"
RESULTS = ROOT / "data" / "audit" / "accuracy_baseline_2026_11.json"
BT = ROOT / "data" / "backtests"
LOW, HIGH = 0.8, 1.2
NAMES = {"EPL": "Premier League", "LaLiga": "La Liga", "SerieA": "Serie A", "Ligue1": "Ligue 1"}


def interval(values: np.ndarray, seed: int = 0, n_boot: int = 2000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    lo, hi = np.quantile(values[idx].mean(axis=1), [0.025, 0.975])
    return float(lo), float(hi)


def binary_slope(p: np.ndarray, y: np.ndarray, steps: int = 50) -> float:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.column_stack([np.ones_like(p), np.log(p / (1 - p))])
    b = np.zeros(2)
    for _ in range(steps):
        q = 1 / (1 + np.exp(-(x @ b)))
        step = np.linalg.solve(x.T @ (x * (q * (1 - q))[:, None]), x.T @ (y - q))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(b[1])


def slope_interval(fit, n: int, seed: int = 1, n_boot: int = 500) -> tuple[float, float]:
    """95% bootstrap interval of a calibration slope; `fit(idx)` refits on resampled rows."""
    rng = np.random.default_rng(seed)
    draws = [fit(rng.integers(0, n, size=n)) for _ in range(n_boot)]
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return float(lo), float(hi)


def row_1x2(where: str, p: np.ndarray, y: np.ndarray) -> dict:
    ll = metrics.log_loss(p, y)
    lo, hi = interval(ll)
    return {"where": where, "market": "home, draw, away", "n": len(y),
            "log_loss": float(ll.mean()), "lo": lo, "hi": hi,
            "brier": float(metrics.brier(p, y).mean()), "rps": float(metrics.rps(p, y).mean()),
            "slope": trial.slope(p, y),
            "slope_ci": slope_interval(lambda i: trial.slope(p[i], y[i]), len(y), n_boot=200)}


def row_binary(where: str, market: str, p: np.ndarray, happened: np.ndarray) -> dict:
    keep = np.isfinite(p)
    p, happened = p[keep], happened[keep].astype(bool)
    ll = metrics.binary_log_loss(p, happened)
    lo, hi = interval(ll)
    return {"where": where, "market": market, "n": int(len(p)), "log_loss": float(ll.mean()),
            "lo": lo, "hi": hi, "brier": float(metrics.binary_brier(p, happened).mean()),
            "rps": None, "slope": binary_slope(p, happened.astype(float)),
            "slope_ci": slope_interval(
                lambda i: binary_slope(p[i], happened[i].astype(float)), len(p))}


def binary_markets() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Every stored yes/no forecast of a shown market, all walk-forward seasons, one row per
    match and market: league, season, market, p, happened. Also the 1X2 frames per group."""
    parts, frames = [], {}
    for group, leagues in (("live", ("EPL", "LaLiga")), ("trial", ("SerieA", "Ligue1"))):
        frame, _ = trial.build(group)
        frames[group] = frame
        matches = pd.read_parquet((TRIAL_DIR if group == "trial" else PROCESSED)
                                  / "matches.parquet").set_index("match_id")
        cards = pd.read_parquet(trial.path(group, "cards_nb_walkforward_2021_2025.parquet"))
        corners = pd.read_parquet(
            trial.path(group, "corners_total_poisson_walkforward_2021_2025.parquet"))

        def add(src: pd.DataFrame, market: str, p: pd.Series, happened: pd.Series) -> None:
            part = pd.DataFrame({"league": src["league"].to_numpy(),
                                 "season": src["season"].to_numpy(int), "market": market,
                                 "p": np.asarray(p, float),
                                 "happened": np.asarray(happened, float)})
            parts.append(part[np.isfinite(part["p"]) & np.isfinite(part["happened"])])

        def total(src: pd.DataFrame, a: str, b: str, m: pd.DataFrame = matches) -> pd.Series:
            return src["match_id"].map(m[a]) + src["match_id"].map(m[b])

        k = cards[cards["league"].isin(leagues)]
        y = total(k, "home_yellows", "away_yellows")
        add(k, "over 4.5 yellow cards", k["p_over_4_5"], (y > 4.5).where(y.notna()))
        if group == "live":  # goals and corners are shown for these two leagues only
            t = frame[frame["league"].isin(leagues)].dropna(subset=["pub_home"])
            add(t, "over 2.5 goals", t["pub_over_2_5"], t["over_2_5"].astype(float))
            add(t, "both teams score", t["pub_btts"],
                ((t["home_goals"] > 0) & (t["away_goals"] > 0)).astype(float))
            c = corners[corners["league"].isin(leagues)]
            y = total(c, "home_corners", "away_corners")
            add(c, "over 9.5 corners", c["p_over_9_5"], (y > 9.5).where(y.notna()))
    return pd.concat(parts, ignore_index=True), frames


MARKET_ORDER = ["over 2.5 goals", "both teams score", "over 9.5 corners", "over 4.5 yellow cards"]


def football() -> list[dict]:
    long, frames = binary_markets()
    long = long[long["season"].isin(trial.TEST)]
    rows = []
    for group, leagues in (("live", ("EPL", "LaLiga")), ("trial", ("SerieA", "Ligue1"))):
        for lg in leagues:
            frame = frames[group]
            t = frame[(frame["league"] == lg) & frame["season"].isin(trial.TEST)]
            t = t.dropna(subset=["pub_home"])
            rows.append(row_1x2(NAMES[lg], trial.probs(t, "pub"), t["outcome"].to_numpy(int)))
            for market in MARKET_ORDER:
                m = long[(long["league"] == lg) & (long["market"] == market)]
                if len(m):
                    rows.append(row_binary(NAMES[lg], market, m["p"].to_numpy(float),
                                           m["happened"].to_numpy(bool)))
    return rows


def champions_league() -> dict:
    u = json.loads((ROOT / "data" / "audit" / "ucl_backtest_2026_10.json").read_text("utf-8"))
    t = u["table"]["club_dc"]
    return {"where": "Champions League", "market": "home, draw, away", "n": u["n"],
            "log_loss": t["log_loss"], "lo": None, "hi": None, "brier": t["brier"],
            "rps": t["rps"], "slope": t["slope"], "slope_ci": None,
            "gain_vs_base_rps": u["U1"]}  # the stored paired interval against base rates


def basketball() -> list[dict]:
    rows = []
    for name in ("b1", "b5"):
        res = json.loads((ROOT / "data" / "basketball" / f"{name}_results.json").read_text("utf-8"))
        for lg, v in res.items():
            m, c = v["means"], v["checks"]
            rows.append({"league": lg, "n": v["test_games"],
                         "winner_log_loss": m["winner_log_loss"]["elo"],
                         "winner_vs_naive": c["W1"], "slope": c["K1"]["slope"],
                         "margin_crps": m["margin_crps"]["elo"],
                         "total_crps": m["total_crps"]["points"],
                         "cover_margin": c["K2"]["margin"], "cover_total": c["K2"]["total"],
                         "shown": v["decision"]})
    return rows


def flag(slope: float, ci: tuple[float, float] | None = None) -> str:
    """Outside 0.8 to 1.2 is flagged. When the 95% interval still reaches into that band,
    the evidence is weak and the flag says so."""
    if LOW <= slope <= HIGH:
        return "ok"
    word = "too cautious" if slope > HIGH else "too bold"
    weak = ci is not None and ci[0] <= HIGH and ci[1] >= LOW
    return f"**{word}**" + (" (weak evidence)" if weak else "")


def write(fb: list[dict], ucl: dict, bb: list[dict]) -> None:
    def num(v: float | None, d: int = 3) -> str:
        return "" if v is None else f"{v:.{d}f}"

    lines = ["# Baseline accuracy of every live market (review of November 2026)", "",
             "Every number is from matches the model had not seen when it made the forecast "
             "(walk-forward). Nothing was fitted for this report: it scores the stored test "
             "forecasts. [V] verified by `scripts/accuracy_baseline.py`.", "",
             "How to read it: lower log loss, Brier and RPS are better. The calibration slope "
             "says whether a 70% forecast happens 70% of the time: 1 is honest, above 1 the "
             f"model is too cautious, below 1 too bold. Outside {LOW} to {HIGH} is flagged.", "",
             "## Football", "",
             "Premier League, La Liga, Serie A and Ligue 1: test seasons 2023/24 to 2025/26, "
             "the published model (Bayesian Dixon-Coles with the goals fix). Champions League: "
             "2021/22 to 2025/26, from `data/audit/ucl_backtest_2026_10.json`.", "",
             "| Competition | Market | Matches | Log loss (95% interval) | Brier | RPS | Slope | "
             "Calibration |", "|---|---|---|---|---|---|---|---|"]
    for r in [*fb, ucl]:
        ci = f" ({r['lo']:.3f} to {r['hi']:.3f})" if r["lo"] is not None else ""
        lines.append(f"| {r['where']} | {r['market']} | {r['n']:,} | {r['log_loss']:.3f}{ci} | "
                     f"{num(r['brier'])} | {num(r['rps'])} | {r['slope']:.2f}"
                     + (f" ({r['slope_ci'][0]:.2f} to {r['slope_ci'][1]:.2f})"
                        if r["slope_ci"] else "")
                     + f" | {flag(r['slope'], r['slope_ci'])} |")
    g = ucl["gain_vs_base_rps"]
    lines += ["", f"Champions League gain over base rates, RPS: {g['mean']:.3f} "
              f"(95% interval {g['lo']:.3f} to {g['hi']:.3f}; below 0 is better).", "",
              "## Basketball", "",
              "Test seasons as in each league's report. Winner: log loss of the Elo model and "
              "its gain over a naive forecast. Margin and total: CRPS in points, and how often "
              "the 90% range held the result (target 0.90, pass from 0.87 to 0.93).", "",
              "| League | Games | Winner log loss | Gain over naive (95% interval) | Slope | "
              "Calibration | Margin CRPS | Total CRPS | 90% range held: margin, total | Shown "
              "on the page |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in bb:
        w = r["winner_vs_naive"]
        shown = ", ".join(k.replace("_", " ") for k, v in r["shown"].items() if v) or "nothing"
        lines.append(f"| {r['league']} | {r['n']:,} | {r['winner_log_loss']:.3f} | "
                     f"{w['mean']:.3f} ({w['low']:.3f} to {w['high']:.3f}) | {r['slope']:.2f} | "
                     f"{flag(r['slope'])} | {r['margin_crps']:.2f} | {r['total_crps']:.2f} | "
                     f"{r['cover_margin']:.2f}, {r['cover_total']:.2f} | {shown} |")
    flagged = [f"{r['where']} {r['market']} ({r['slope']:.2f}): "
               + flag(r["slope"], r["slope_ci"]).replace("*", "") for r in [*fb, ucl]
               if flag(r["slope"]) != "ok"]
    flagged += [f"{r['league']} basketball winner ({r['slope']:.2f}): "
                + flag(r["slope"]).replace("*", "") for r in bb if flag(r["slope"]) != "ok"]
    lines += ["", "## Flagged markets", ""]
    lines += [f"- {f}" for f in flagged] or ["- none"]
    lines += ["", "A flagged basketball winner market is not shown on the page (the league's "
              "handicap and total are). A flagged football market keeps its forecast, and the "
              "page says on that section which way it leans.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    RESULTS.write_text(json.dumps({"football": fb, "champions_league": ucl, "basketball": bb,
                                   "flagged": flagged, "limits": [LOW, HIGH]}, indent=1),
                       encoding="utf-8")


def main() -> int:
    fb, ucl, bb = football(), champions_league(), basketball()
    write(fb, ucl, bb)
    print(REPORT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
