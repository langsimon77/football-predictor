"""Backtest the tip products on held-out seasons.

Usage: python scripts/backtest_tips.py [MATCHES_PARQUET]

Inputs (walk-forward forecasts, each made at its lock time on data known then):
  data/backtests/dc_bayes_v1_walkforward_2021_2025.parquet   1X2, over 2.5, BTTS
  data/backtests/corners_total_poisson_walkforward_2021_2025.parquet
  data/backtests/cards_nb_walkforward_2021_2025.parquet
  data/tiers/thresholds.json   cut points fitted on 2021/22 and 2022/23 only
  data/processed/matches.parquet   results and Pinnacle closing odds (benchmark only)

Test seasons: 2023/24, 2024/25, 2025/26. A "day" is one calendar match date.
Writes reports/tips_backtest_2026_11.md and data/tips/backtest_picks.parquet.

Known differences from live (they make this backtest slightly kind):
- No ensemble-disagreement demotion (the stack is not in these files).
- No data-quality flags (not stored in the walk-forward files).
- Goals forecasts are dc_bayes_v1 before the shape_v1 refit of 9 Oct 2026.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fp.ensemble import tiers  # noqa: E402
from fp.tips import picks as tp  # noqa: E402

TEST_SEASONS = (2023, 2024, 2025)
MIN_PRICED = 30   # below this many priced picks, the return is not reported
BT = ROOT / "data" / "backtests"
ODDS = {("1x2", "home"): "odds_pin_close_home", ("1x2", "draw"): "odds_pin_close_draw",
        ("1x2", "away"): "odds_pin_close_away",
        ("over_2_5", "over"): "odds_pin_close_over25",
        ("over_2_5", "under"): "odds_pin_close_under25"}


def forecasts(matches: pd.DataFrame) -> pd.DataFrame:
    g = pd.read_parquet(BT / "dc_bayes_v1_walkforward_2021_2025.parquet")
    co = pd.read_parquet(BT / "corners_total_poisson_walkforward_2021_2025.parquet")
    ca = pd.read_parquet(BT / "cards_nb_walkforward_2021_2025.parquet")
    g = g[g["season"].isin(TEST_SEASONS) & g["fit_ok"]]
    f = pd.DataFrame({"match_id": g["match_id"], "league": g["league"],
                      "p_home": g["bdc_home"], "p_draw": g["bdc_draw"],
                      "p_away": g["bdc_away"], "p_over_2_5": g["bdc_over_2_5"],
                      "p_btts": g["bdc_btts"], "intervals": g["bdc_intervals"]})
    # Over 1.5 and 3.5 goals from the 11 x 11 scoreline table (rows home goals); the same
    # table reproduces the stored over 2.5 exactly.
    goals = np.add.outer(np.arange(11), np.arange(11))
    mats = np.stack([np.asarray(m, dtype=float).reshape(11, 11) for m in g["bdc_matrix"]])
    for line in (1.5, 3.5):
        f[f"p_over_{str(line).replace('.', '_')}"] = mats[:, goals > line].sum(axis=1)
    co = co.set_index("match_id")
    ca = ca.set_index("match_id")
    for line in ("8_5", "9_5", "10_5", "11_5"):
        f[f"p_corners_over_{line}"] = f["match_id"].map(co[f"p_over_{line}"])
    for line in ("3_5", "4_5", "5_5"):
        f[f"p_yellows_over_{line}"] = f["match_id"].map(ca[f"p_over_{line}"])
    f["referee_known"] = f["match_id"].map(ca["referee_known"]).fillna(False)
    m = matches.set_index("match_id")
    f["kickoff_utc"] = f["match_id"].map(m["match_date"])
    f["home_id"] = f["match_id"].map(m["home_id"])
    f["away_id"] = f["match_id"].map(m["away_id"])
    return f.reset_index(drop=True)


def add_tiers(f: pd.DataFrame) -> pd.DataFrame:
    th = tiers.load(ROOT / "data" / "tiers" / "thresholds.json")
    out = []
    for rec in f.to_dict("records"):
        iv = json.loads(rec["intervals"]) if isinstance(rec["intervals"], str) else {}

        def width(key: str, iv: dict = iv) -> np.ndarray:
            lo_hi = iv.get(key)
            return np.array([lo_hi[1] - lo_hi[0] if lo_hi else np.nan])

        t = {"rule": "tiers_v1"}
        p = np.array([rec["p_home"], rec["p_draw"], rec["p_away"]])
        key = ("p_home", "p_draw", "p_away")[int(p.argmax())]
        t["1x2"] = str(tiers.assign(th["1x2"], np.array([p.max()]), np.array([0]),
                                    width=width(key))[0])
        for market in tp.LINE_MARKETS:
            v = rec.get(f"p_{market}")
            if market not in th or v is None or not np.isfinite(v):
                continue
            flags = int(market.startswith("yellows_") and
                        (rec["league"] != "EPL" or not rec["referee_known"]))
            t[market] = str(tiers.assign(th[market], np.array([max(v, 1 - v)]),
                                         np.array([flags]), width=width(f"p_{market}"))[0])
        out.append(t)
    return f.assign(tiers=out)


def odds_for(rec: dict, m: pd.DataFrame) -> float:
    col = ODDS.get((rec["market"], rec["side"]))
    if col is None or rec["match_id"] not in m.index:
        return float("nan")
    v = m.at[rec["match_id"], col]
    return float(v) if pd.notna(v) and v > 1 else float("nan")


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def run(matches_path: Path) -> None:
    matches = pd.read_parquet(matches_path)
    m = matches.set_index("match_id")
    results = matches[["match_id", "home_goals", "away_goals", "home_corners",
                       "away_corners", "home_yellows", "away_yellows"]]
    cand = tp.candidates(add_tiers(forecasts(matches)))
    cand["day"] = pd.to_datetime(cand["kickoff_utc"]).dt.date
    rows, coupon_rows = [], []
    for day, c in cand.groupby("day", sort=True):
        prod = tp.build_day(c)
        for name in ("free", "premium", "diamond"):
            for rec in tp.settle(prod[name], results).to_dict("records"):
                rows.append({**rec, "product": name, "day": day,
                             "close_odds": odds_for(rec, m)})
        for cp in prod["coupons"]:
            odds = [odds_for(leg, m) for leg in cp["legs"]]
            coupon_rows.append({"product": cp["name"], "day": day, "prob": cp["prob"],
                                "status": tp.settle_coupon(cp, results),
                                "close_odds": float(np.prod(odds))})
    singles = pd.DataFrame(rows)
    coupons = pd.DataFrame(coupon_rows)
    out_dir = ROOT / "data" / "tips"
    out_dir.mkdir(parents=True, exist_ok=True)
    singles.drop(columns=["tier_rank"]).to_parquet(out_dir / "backtest_picks.parquet")
    # Tested win rate of every candidate by market and tier: the evidence line in each
    # tip's written reason (scripts/make_tips.py).
    allc = tp.settle(cand, results)
    allc = allc[allc["status"] != "pending"]
    rec = {}
    for (mk, tier), g in allc.groupby(["market", "tier"]):
        rec.setdefault(mk, {})[tier] = {"picks": int(len(g)),
                                        "won": round(float((g["status"] == "won").mean()), 3),
                                        "promised": round(float(g["prob"].mean()), 3)}
    (out_dir / "market_record.json").write_text(json.dumps(
        {"basis": "walk-forward forecasts, EPL and La Liga, 2023/24 to 2025/26",
         "markets": rec}, indent=1) + "\n", encoding="utf-8")
    report(singles, coupons, cand)


def summarise(df: pd.DataFrame, label: str) -> str:
    d = df[df["status"] != "pending"]
    n, k = len(d), int((d["status"] == "won").sum())
    lo, hi = wilson(k, n)
    priced = d[d["close_odds"].notna()]
    if len(priced) < MIN_PRICED:
        roi_txt = "too few to judge"
    else:
        pnl = np.where(priced["status"] == "won", priced["close_odds"] - 1, -1.0)
        rng = np.random.default_rng(7)
        boot = rng.choice(pnl, size=(2000, len(pnl))).mean(axis=1)
        roi_txt = (f"{pnl.mean():+.1%} ({np.quantile(boot, 0.025):+.1%} to "
                   f"{np.quantile(boot, 0.975):+.1%})")
    return (f"| {label} | {n} | {d['prob'].mean():.1%} | {k / n:.1%} "
            f"({lo:.1%} to {hi:.1%}) | {len(priced)} | {roi_txt} |")


def report(singles: pd.DataFrame, coupons: pd.DataFrame, cand: pd.DataFrame) -> None:
    head = ("| Product | Picks settled | Model promised (mean) | Hit rate (95% range) "
            "| Picks with closing odds | Return per 1 unit at Pinnacle close (95% range) |\n"
            "|---|---|---|---|---|---|")
    lines = [summarise(singles[singles["product"] == p], n)
             for p, n in (("free", "Free tips"), ("premium", "Premium"),
                          ("diamond", "Diamond"))]
    lines += [summarise(coupons[coupons["product"] == p], p)
              for p in ("Double", "Treble") if (coupons["product"] == p).any()]
    by_market = [summarise(g, mk) for mk, g in
                 singles[singles["product"] == "premium"].groupby("market")]
    days = singles["day"].nunique()
    text = f"""# Tip products backtest, November 2026

Test seasons 2023/24 to 2025/26, EPL and La Liga, {days} match days.
Forecasts are walk-forward (each made at its lock time on data known then).
Tier cut points come from 2021/22 and 2022/23 only (`data/tiers/thresholds.json`).
Script: `scripts/backtest_tips.py`. Picks: `data/tips/backtest_picks.parquet`.

## Products

{head}
{chr(10).join(lines)}

How to read it:
- "Model promised" is the average model probability of the picks. If the hit rate's
  95% range covers it, the products are honest: they win about as often as they claim.
- "Return per 1 unit" uses Pinnacle closing odds, only for picks that have them
  (1X2 and over/under 2.5 goals; coupons only when every leg has odds). A negative
  number means a bettor following the picks at closing prices lost money. [Verified, this run]
- Coupons assume independent legs. A double needs both legs to win.

## Premium picks by market

{head}
{chr(10).join(by_market)}

## Limits of this test

- No ensemble-disagreement demotion and no data-quality flags, so a few picks
  rated High here would be Medium live. The record shown is therefore slightly kind. [Assumption]
- Goals forecasts are dc_bayes_v1 before the shape_v1 refit; live tiers use refit cut points.
- Closing odds are a benchmark only. We have no free live odds, so live tips show
  fair odds (1 / probability): a bet only has value if the bookmaker pays more.
"""
    path = ROOT / "reports" / "tips_backtest_2026_11.md"
    path.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    default = ROOT.parent / "football-predictor" / "data" / "processed" / "matches.parquet"
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else default)
