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
# Markets each basketball league publishes (tests passed); mirrors basketball/live.py MARKETS.
BB_MARKETS = {"EuroLeague": ("winner", "handicap", "total"), "NBL": ("winner",),
              "ACB": ("winner", "handicap"), "LBA": ("handicap", "total"),
              "ABA": ("handicap", "total")}
JUBA = "Africa/Juba"
MARKET_NAME = {"1x2": "result", "over_1_5": "over/under 1.5 goals",
               "over_2_5": "over/under 2.5 goals", "over_3_5": "over/under 3.5 goals",
               "btts": "both teams score", "bb_winner": "basketball winner"}


def basketball_games() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Locked basketball forecasts (past and future) plus not-yet-locked upcoming games,
    every league; and the results, keyed like the football ones."""
    bb = ROOT / "ledger" / "basketball"
    cols = ["game_id", "league", "tip_utc", "date", "home_name", "away_name", "p_home",
            "margin_mean", "total_mean", "lock_utc"]
    locked = pd.read_parquet(bb / "predictions.parquet")
    up = pd.read_parquet(bb / "upcoming.parquet")
    up = up[~up["game_id"].isin(locked["game_id"])]
    games = pd.concat([locked[[c for c in cols if c in locked.columns]],
                       up[[c for c in cols if c in up.columns]]], ignore_index=True)
    games = games.sort_values("lock_utc", na_position="last").drop_duplicates("game_id")
    res = pd.read_parquet(bb / "results.parquet").rename(columns={"game_id": "match_id"})
    return games.reset_index(drop=True), res


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def basketball_card(games: pd.DataFrame, bbt: dict, now: pd.Timestamp,
                    days: int) -> list[dict]:
    """VIP Basketball: every coming game with only the forecasts whose test passed."""
    out = []
    for g in games.to_dict("records"):
        when = g.get("tip_utc")
        t = pd.Timestamp(when) if when is not None and pd.notna(when) else (
            pd.Timestamp(str(g.get("date")) + " 12:00") if g.get("date") else None)
        if t is None or pd.isna(t):
            continue
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        if not (now <= t < now + pd.Timedelta(days=days)):
            continue
        mk = BB_MARKETS.get(g["league"], ())
        row = {"league": g["league"], "kickoff_utc": str(t) if pd.notna(when) else None,
               "date": str(t.tz_convert(JUBA).date()), "home": g["home_name"],
               "away": g["away_name"], "match_id": g["game_id"]}
        p = g.get("p_home")
        if "winner" in mk and p is not None and pd.notna(p):
            fav = p >= 0.5
            prob = float(p if fav else 1 - p)
            row |= {"favourite": g["home_name"] if fav else g["away_name"],
                    "win_chance": round(prob, 3),
                    "tier": ("High" if prob >= bbt["high"] - 1e-9 else
                             "Low" if prob < bbt["low"] - 1e-9 else "Medium")}
        m = g.get("margin_mean")
        if "handicap" in mk and m is not None and pd.notna(m):
            row["margin"] = round(float(m), 1)   # home minus away, points
        tot = g.get("total_mean")
        if "total" in mk and tot is not None and pd.notna(tot):
            row["total"] = round(float(tot), 1)
        if len(row) > 6:
            out.append(row)
    return sorted(out, key=lambda r: (r["kickoff_utc"] or r["date"] + "T12"))


def score_text(results: pd.DataFrame) -> dict[str, str]:
    """Final score per match id: goals for football, points for basketball."""
    out = {}
    for r in results.to_dict("records"):
        hg, ag = r.get("home_goals"), r.get("away_goals")
        hp, ap = r.get("home_pts"), r.get("away_pts")
        if hg is not None and pd.notna(hg) and pd.notna(ag):
            out[r["match_id"]] = f"{int(hg)}-{int(ag)}"
        elif hp is not None and pd.notna(hp) and pd.notna(ap):
            out[r["match_id"]] = f"{int(hp)}-{int(ap)}"
    return out


def scorecard(c: pd.DataFrame, prim_day: pd.DataFrame, results: pd.DataFrame,
              why: dict, scores: dict[str, str]) -> dict:
    """Yesterday's tips under today's rules, from the forecasts locked before kickoff,
    settled against the results: what we said, the score, won or lost, and promised vs won."""
    cats = {"top3": tp.top3(c), "bankers": tp.bankers(c), "full_card": tp.full_card(c),
            "correct_score": tp.correct_scores(prim_day), "diamond": tp.diamond(c)}
    out: dict = {"categories": {}, "accumulators": []}
    for name, df in cats.items():
        st = tp.settle(df, results)
        recs = _records(st, why)
        for r in recs:
            r["score"] = scores.get(r["match_id"])
        done = st[st["status"] != "pending"]
        out["categories"][name] = {
            "picks": recs, "won": int((st["status"] == "won").sum()),
            "lost": int((st["status"] == "lost").sum()),
            "pending": int((st["status"] == "pending").sum()),
            "expected": round(float(done["prob"].sum()), 2)}
    for cp in tp.accumulators(c):
        legs = _records(tp.settle(pd.DataFrame(cp["legs"]), results), why)
        for r in legs:
            r["score"] = scores.get(r["match_id"])
        out["accumulators"].append({"name": cp["name"], "prob": round(cp["prob"], 3),
                                    "fair_odds": cp["fair_odds"], "legs": legs,
                                    "status": tp.settle_coupon(cp, results)})
    return out


def reason(rec: dict, fc: dict, record: dict, bb: dict, prod: dict | None = None) -> str:
    """The written reason on a tip (Winning Gang's Premium 'yorum'), from our numbers only."""
    p, mk, tier = rec["prob"], rec["market"], rec["tier"]
    lead = f"Our model gives this {round(100 * p)} in 100."
    ctx = ""
    if mk == "correct_score":
        eh, ea = fc.get("exp_goals_home"), fc.get("exp_goals_away")
        if eh is not None and pd.notna(eh) and pd.notna(ea):
            ctx = f" Expected goals {eh:.1f} v {ea:.1f}; this is the single likeliest score."
        cs = (prod or {}).get("correct_score")
        if cs:
            ctx += (f" Tested: the day's five likeliest scores came true {_pct(cs['won'])} of "
                    f"{cs['picks']} times (promised {_pct(cs['promised'])}), 2023/24 to "
                    "2025/26.")
        return lead + ctx
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
    prec = json.loads((ROOT / "data" / "tips" / "product_record.json").read_text())["products"]
    cand = pd.concat([tp.candidates(prim),
                      tp.basketball_candidates(bb_games[bb_games["league"].isin(
                          BB_WINNER_LEAGUES)], bbt["high"], bbt["low"])],
                     ignore_index=True)
    cand["kickoff_utc"] = pd.to_datetime(cand["kickoff_utc"], utc=True)
    fc = {**prim.set_index("match_id").to_dict("index"),
          **bb_games.set_index("game_id").to_dict("index")}
    prim_k = prim.assign(kickoff_utc=pd.to_datetime(prim["kickoff_utc"], utc=True))
    scores = tp.correct_scores(prim_k, n=len(prim_k))
    why = {(r["match_id"], r["market"]): reason(r, fc.get(r["match_id"], {}), mrec, bbt, prec)
           for r in pd.concat([cand, scores], ignore_index=True).to_dict("records")}
    kick = pd.to_datetime(cand["kickoff_utc"], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    upcoming = cand[(kick >= now) & (kick < now + pd.Timedelta(days=args.days))]
    prod = tp.build_day(upcoming)
    # Today's Top 3: today's games in Juba time; if none are left today, the next day with games.
    jday = kick.dt.tz_convert(JUBA).dt.date
    ahead = jday[(kick >= now)]
    first_day = ahead.min() if len(ahead) else None
    today = now.tz_convert(JUBA).date()
    top_day = today if (ahead == today).any() else first_day
    prod["top3"] = tp.top3(cand[(kick >= now) & (jday == top_day)])
    prod["bankers"] = tp.bankers(upcoming)
    prod["full_card"] = tp.full_card(upcoming)
    pk = prim_k["kickoff_utc"]
    prod["correct_score"] = tp.correct_scores(
        prim_k[(pk >= now) & (pk < now + pd.Timedelta(days=args.days))])
    prod["accumulators"] = tp.accumulators(upcoming)
    out = {"generated_utc": now.isoformat(),
           "rule": "tips_v3: football tiers_v1, basketball bb_tiers_v1",
           "top3_day": str(top_day) if top_day is not None else None,
           "note": "Fair odds = 1 / model probability. Bet only if the bookmaker pays more.",
           **{k: _records(tp.settle(prod[k], results), why)
              for k in ("top3", "bankers", "full_card", "correct_score", "diamond")},
           "accumulators": [{**c, "legs": _records(tp.settle(pd.DataFrame(c["legs"]), results),
                                                   why),
                             "prob": round(c["prob"], 3)} for c in prod["accumulators"]],
           "basketball": basketball_card(bb_games, bbt, now, args.days),
           "tested": prec}
    # Track record: replay every past day from the ledger, settled against results.
    record = {}
    cand["day"] = jday
    prim_k["day"] = prim_k["kickoff_utc"].dt.tz_convert(JUBA).dt.date
    past = cand[kick < now]
    for d, c in past.groupby("day"):
        day = {"top3": tp.top3(c), "bankers": tp.bankers(c), "full_card": tp.full_card(c),
               "diamond": tp.diamond(c),
               "correct_score": tp.correct_scores(prim_k[(prim_k["day"] == d)
                                                         & (prim_k["kickoff_utc"] < now)])}
        for name, df in day.items():
            st = tp.settle(df, results)["status"].value_counts()
            r = record.setdefault(name, {"won": 0, "lost": 0, "pending": 0})
            for s in r:
                r[s] += int(st.get(s, 0))
        for cp in tp.accumulators(c):
            r = record.setdefault(cp["name"].lower(), {"won": 0, "lost": 0, "pending": 0})
            r[tp.settle_coupon(cp, results)] += 1
    out["record"] = record
    # Yesterday's scorecard (Juba calendar day before today).
    yday = today - pd.Timedelta(days=1)
    out["yesterday"] = {"day": str(yday),
                        "note": "Today's tip rules applied to yesterday's forecasts, each "
                                "locked before kickoff, settled against the results.",
                        **scorecard(cand[cand["day"] == yday],
                                    prim_k[prim_k["day"] == yday], results, why,
                                    score_text(results))}
    out["basketball_note"] = ("Basketball tips: winner picks only, EuroLeague, NBL and ACB. "
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
