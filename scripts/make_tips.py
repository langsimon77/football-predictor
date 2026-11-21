"""Build today's tip products from the locked ledger.

Usage: python scripts/make_tips.py [--days N]

Reads ledger/predictions.parquet (primary rows: the ones carrying tiers) and
ledger/results.parquet. Writes data/tips/tips.json with:
  free, premium, diamond, coupons   for matches kicking off in the next N days
  record                            won/lost count per product over settled picks
Each pick has: match, league, kickoff (UTC), pick, model probability, fair odds,
tier, status. Fair odds = 1 / probability; a bet has value only above them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fp import teams as fpteams  # noqa: E402
from fp.tips import picks as tp  # noqa: E402


def primary_rows(pred: pd.DataFrame) -> pd.DataFrame:
    has = pred["tiers"].map(lambda t: "rule" in tp._tiers(t))
    p = pred[has].sort_values("lock_utc")
    return p.drop_duplicates("match_id", keep="last")


BB_WINNER_LEAGUES = ("EuroLeague", "NBL", "ACB")   # winner forecasts that passed their tests
MARKET_NAME = {"1x2": "result", "over_1_5": "over/under 1.5 goals",
               "over_2_5": "over/under 2.5 goals", "over_3_5": "over/under 3.5 goals",
               "btts": "both teams score", "bb_winner": "basketball winner"}


def basketball_games() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Locked basketball forecasts (past and future) plus not-yet-locked upcoming games,
    winner leagues only; and the results, keyed like the football ones."""
    bb = ROOT / "ledger" / "basketball"
    cols = ["game_id", "league", "tip_utc", "home_name", "away_name", "p_home",
            "margin_mean", "lock_utc"]
    locked = pd.read_parquet(bb / "predictions.parquet")
    up = pd.read_parquet(bb / "upcoming.parquet")
    up = up[~up["game_id"].isin(locked["game_id"])]
    games = pd.concat([locked[cols], up[[c for c in cols if c in up.columns]]],
                      ignore_index=True)
    games = games[games["league"].isin(BB_WINNER_LEAGUES)]
    games = games.sort_values("lock_utc", na_position="last").drop_duplicates("game_id")
    res = pd.read_parquet(bb / "results.parquet").rename(columns={"game_id": "match_id"})
    return games.reset_index(drop=True), res


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def reason(rec: dict, fc: dict, record: dict, bb: dict) -> str:
    """The written reason on a tip (Winning Gang's Premium 'yorum'), from our numbers only."""
    p, mk, tier = rec["prob"], rec["market"], rec["tier"]
    lead = f"Our model gives this {round(100 * p)} in 100."
    ctx = ""
    if mk == "bb_winner":
        m = fc.get("margin_mean")
        if m is not None and pd.notna(m):
            ctx = f" Expected margin about {abs(m):.0f} points."
        tested = next((r for r in bb.get("test", []) if r["league"] == rec["league"]
                       and r["tier"] == tier), None)
        if tested:
            ctx += (f" Tested: {tier}-tier {rec['league']} winner picks won "
                    f"{_pct(tested['won'])} of {tested['games']} games "
                    f"(promised {_pct(tested['promised'])}).")
        return lead + ctx
    eh, ea = fc.get("exp_goals_home"), fc.get("exp_goals_away")
    if mk.startswith("corners_"):
        ch, ca = fc.get("exp_corners_home"), fc.get("exp_corners_away")
        if ch is not None and pd.notna(ch) and pd.notna(ca):
            ctx = f" About {ch + ca:.1f} corners expected."
    elif mk.startswith("yellows_"):
        y = fc.get("exp_yellows")
        if y is not None and pd.notna(y):
            ctx = f" About {y:.1f} yellow cards expected."
    elif eh is not None and pd.notna(eh) and pd.notna(ea):
        ctx = f" Expected goals {eh:.1f} v {ea:.1f}."
    t = record.get(mk, {}).get(tier)
    if t:
        name = MARKET_NAME.get(mk, mk.replace("_", " "))
        ctx += (f" Tested: {tier}-tier {name} picks won {_pct(t['won'])} of {t['picks']} "
                f"(promised {_pct(t['promised'])}), 2023/24 to 2025/26.")
    return lead + ctx


def _records(df: pd.DataFrame, why: dict | None = None) -> list[dict]:
    keep = ["match_id", "league", "kickoff_utc", "home_id", "away_id", "market", "pick",
            "prob", "fair_odds", "tier", "status"]
    out = df[[c for c in keep if c in df.columns]].copy()
    names = dict(zip(fpteams.teams()["team_id"], fpteams.teams()["name"], strict=False))
    for side in ("home", "away"):
        if f"{side}_id" in out:
            # Basketball ids are already display names; football ids are slugs.
            out[side] = [t if m == "bb_winner" else names.get(t, str(t).replace("_", " ").title())
                         for t, m in zip(out[f"{side}_id"], out["market"], strict=True)]
    out["kickoff_utc"] = out["kickoff_utc"].astype(str)
    out["prob"] = out["prob"].round(3)
    if why is not None:
        out["sport"] = out["market"].map(lambda m: "basketball" if m == "bb_winner"
                                         else "football")
        out["reason"] = [why.get((r["match_id"], r["market"]), "")
                         for r in out.to_dict("records")]
    return out.to_dict("records")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()
    pred = pd.read_parquet(ROOT / "ledger" / "predictions.parquet")
    prim = primary_rows(pred)
    bb_games, bb_res = basketball_games()
    bbt = json.loads((ROOT / "data" / "tips" / "basketball_tiers.json").read_text())
    mrec = json.loads((ROOT / "data" / "tips" / "market_record.json").read_text())["markets"]
    results = pd.concat([pd.read_parquet(ROOT / "ledger" / "results.parquet"), bb_res],
                        ignore_index=True)
    cand = pd.concat([tp.candidates(prim),
                      tp.basketball_candidates(bb_games, bbt["high"], bbt["low"])],
                     ignore_index=True)
    cand["kickoff_utc"] = pd.to_datetime(cand["kickoff_utc"], utc=True)
    fc = {**prim.set_index("match_id").to_dict("index"),
          **bb_games.set_index("game_id").to_dict("index")}
    why = {(r["match_id"], r["market"]): reason(r, fc.get(r["match_id"], {}), mrec, bbt)
           for r in cand.to_dict("records")}
    kick = pd.to_datetime(cand["kickoff_utc"], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    upcoming = cand[(kick >= now) & (kick < now + pd.Timedelta(days=args.days))]
    prod = tp.build_day(upcoming)
    out = {"generated_utc": now.isoformat(),
           "rule": "tips_v2: football tiers_v1, basketball bb_tiers_v1",
           "note": "Fair odds = 1 / model probability. Bet only if the bookmaker pays more.",
           **{k: _records(tp.settle(prod[k], results), why)
              for k in ("free", "premium", "diamond")},
           "coupons": [{**c, "legs": _records(tp.settle(pd.DataFrame(c["legs"]), results), why),
                        "prob": round(c["prob"], 3)} for c in prod["coupons"]]}
    # Track record: replay every past day from the ledger, settled against results.
    record = {}
    cand["day"] = kick.dt.date
    past = cand[kick < now]
    for _, c in past.groupby("day"):
        day = tp.build_day(c)
        for name in ("free", "premium", "diamond"):
            st = tp.settle(day[name], results)["status"].value_counts()
            r = record.setdefault(name, {"won": 0, "lost": 0, "pending": 0})
            for s in r:
                r[s] += int(st.get(s, 0))
        for cp in day["coupons"]:
            r = record.setdefault(cp["name"].lower(), {"won": 0, "lost": 0, "pending": 0})
            r[tp.settle_coupon(cp, results)] += 1
    out["record"] = record
    out["basketball_note"] = ("Basketball: winner picks only, EuroLeague, NBL and ACB. "
                              "NBL High-tier picks were weaker in testing: "
                              + next((f"won {_pct(r['won'])} of {r['games']}, promised "
                                      f"{_pct(r['promised'])}" for r in bbt["test"]
                                      if r["league"] == "NBL" and r["tier"] == "High"), "")
                              + ".")
    path = ROOT / "data" / "tips" / "tips.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
