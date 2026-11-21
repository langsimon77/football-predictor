"""Turn forecasts into tips, VIP products and a settled record.

Plain English:
1. Every market of every match gives one candidate pick: the side the model
   thinks is likelier (home, draw or away; over or under; yes or no).
2. Each candidate carries the model probability, the fair odds (1 / probability)
   and the confidence tier already stored in the ledger (spec S7, tiers_v1).
3. The products only filter and rank these candidates:
   - Free tips: the best pick of each match, Medium tier or better.
   - Premium: High-tier picks only, the strongest few of the day.
   - Coupons: a double and a treble made of the strongest High-tier picks from
     different matches. Combined probability = product of the legs (we assume
     the matches are independent).
   - Diamond: the single strongest High-tier pick of the day with fair odds of
     at least `diamond_min_odds`, so it is not a near-certain pick with no price.
4. `settle` marks each pick won, lost or pending from the results.

5. Basketball adds one winner pick per game (EuroLeague, NBL, ACB), tiered by
   bb_tiers_v1 (data/tips/basketball_tiers.json), and joins the same products.

Nothing here changes a forecast. A tip is never more certain than its forecast.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

TIER_RANK = {"Low": 0, "Medium": 1, "High": 2}

# market key in the ledger tiers -> (probability column, label for "over" side,
# label for "under" side, result quantity, line)
LINE_MARKETS = {
    "over_1_5": ("p_over_1_5", "Over 1.5 goals", "Under 1.5 goals", "goals", 1.5),
    "over_2_5": ("p_over_2_5", "Over 2.5 goals", "Under 2.5 goals", "goals", 2.5),
    "over_3_5": ("p_over_3_5", "Over 3.5 goals", "Under 3.5 goals", "goals", 3.5),
    "btts": ("p_btts", "Both teams score: yes", "Both teams score: no", "btts", 0.5),
    "corners_over_8_5": ("p_corners_over_8_5", "Over 8.5 corners", "Under 8.5 corners",
                         "corners", 8.5),
    "corners_over_9_5": ("p_corners_over_9_5", "Over 9.5 corners", "Under 9.5 corners",
                         "corners", 9.5),
    "corners_over_10_5": ("p_corners_over_10_5", "Over 10.5 corners", "Under 10.5 corners",
                          "corners", 10.5),
    "corners_over_11_5": ("p_corners_over_11_5", "Over 11.5 corners", "Under 11.5 corners",
                          "corners", 11.5),
    "yellows_over_3_5": ("p_yellows_over_3_5", "Over 3.5 yellow cards",
                         "Under 3.5 yellow cards", "yellows", 3.5),
    "yellows_over_4_5": ("p_yellows_over_4_5", "Over 4.5 yellow cards",
                         "Under 4.5 yellow cards", "yellows", 4.5),
    "yellows_over_5_5": ("p_yellows_over_5_5", "Over 5.5 yellow cards",
                         "Under 5.5 yellow cards", "yellows", 5.5),
}
OUTCOMES = (("p_home", "home", "Home win"), ("p_draw", "draw", "Draw"),
            ("p_away", "away", "Away win"))


@dataclass(frozen=True)
class Settings:
    free_min_tier: str = "Medium"
    premium_max: int = 5
    premium_min_prob: float = 0.0
    diamond_min_odds: float = 1.25
    coupon_sizes: tuple[int, ...] = (2, 3)


DEFAULT = Settings()

# Kept out of Diamond, Double and Treble (Lang, 21 Nov 2026): NBL High-tier winner picks
# tested weakest (won 71% of 55 games, promised 79%). They stay in Free and Premium.
TOP_EXCLUDED = {("bb_winner", "NBL")}


def _top_ok(c: pd.DataFrame) -> pd.Series:
    return ~pd.Series([(m, lg) in TOP_EXCLUDED for m, lg in zip(c["market"], c["league"],
                                                                  strict=True)], index=c.index)


def _tiers(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        return json.loads(value)
    return {}


def candidates(forecasts: pd.DataFrame) -> pd.DataFrame:
    """One candidate pick per match and market (the likelier side).

    `forecasts` needs match_id, league, kickoff_utc, home_id, away_id, the
    probability columns it has, and `tiers` (dict or JSON text)."""
    rows = []
    for rec in forecasts.to_dict("records"):
        tiers = _tiers(rec.get("tiers"))
        base = {k: rec.get(k) for k in ("match_id", "league", "kickoff_utc", "home_id",
                                         "away_id")}
        p = np.array([np.nan if rec.get(c) is None else rec[c] for c, _, _ in OUTCOMES],
                     dtype=float)
        if np.isfinite(p).all() and "1x2" in tiers:
            i = int(np.argmax(p))
            rows.append({**base, "market": "1x2", "side": OUTCOMES[i][1],
                         "pick": OUTCOMES[i][2], "prob": float(p[i]), "tier": tiers["1x2"]})
        for market, (col, over_label, under_label, _, _) in LINE_MARKETS.items():
            v = rec.get(col)
            if v is None or not np.isfinite(v) or market not in tiers:
                continue
            over = v >= 0.5
            rows.append({**base, "market": market, "side": "over" if over else "under",
                         "pick": over_label if over else under_label,
                         "prob": float(v if over else 1 - v), "tier": tiers[market]})
    out = pd.DataFrame(rows, columns=["match_id", "league", "kickoff_utc", "home_id",
                                      "away_id", "market", "side", "pick", "prob", "tier"])
    out["fair_odds"] = (1 / out["prob"]).round(2)
    out["tier_rank"] = out["tier"].map(TIER_RANK).fillna(0).astype(int)
    return out


def _best_per_match(c: pd.DataFrame) -> pd.DataFrame:
    c = c.sort_values(["tier_rank", "prob"], ascending=[False, False], kind="stable")
    return c.drop_duplicates("match_id", keep="first")


def free_tips(c: pd.DataFrame, s: Settings = DEFAULT) -> pd.DataFrame:
    ok = c[c["tier_rank"] >= TIER_RANK[s.free_min_tier]]
    return _best_per_match(ok).sort_values("kickoff_utc", kind="stable").reset_index(drop=True)


def premium(c: pd.DataFrame, s: Settings = DEFAULT) -> pd.DataFrame:
    high = c[(c["tier"] == "High") & (c["prob"] >= s.premium_min_prob)]
    best = _best_per_match(high).sort_values("prob", ascending=False, kind="stable")
    return best.head(s.premium_max).reset_index(drop=True)


def diamond(c: pd.DataFrame, s: Settings = DEFAULT) -> pd.DataFrame:
    high = c[(c["tier"] == "High") & (c["fair_odds"] >= s.diamond_min_odds) & _top_ok(c)]
    return high.sort_values("prob", ascending=False, kind="stable").head(1).reset_index(drop=True)


def coupons(c: pd.DataFrame, s: Settings = DEFAULT) -> list[dict]:
    """Double and treble from the strongest High picks, one leg per match."""
    high = c[(c["tier"] == "High") & _top_ok(c)]
    legs = _best_per_match(high).sort_values("prob", ascending=False, kind="stable")
    out = []
    for size in s.coupon_sizes:
        if len(legs) < size:
            continue
        chosen = legs.head(size)
        prob = float(np.prod(chosen["prob"].to_numpy()))
        out.append({"name": {2: "Double", 3: "Treble"}.get(size, f"{size}-fold"),
                    "prob": prob, "fair_odds": round(1 / prob, 2),
                    "legs": chosen.drop(columns="tier_rank").to_dict("records")})
    return out


def basketball_candidates(games: pd.DataFrame, high: float, low: float) -> pd.DataFrame:
    """Winner picks for basketball games (bb_tiers_v1).

    `games` needs game_id, league, tip_utc, home_name, away_name, p_home. Only leagues
    whose winner forecast passed its test should be passed in (EuroLeague, NBL, ACB).
    Tier from the favourite's chance: at or above `high` High, below `low` Low."""
    rows = []
    for rec in games.to_dict("records"):
        p = rec.get("p_home")
        if p is None or not np.isfinite(p):
            continue
        home = p >= 0.5
        prob = float(p if home else 1 - p)
        team = rec["home_name"] if home else rec["away_name"]
        tier = "High" if prob >= high - 1e-9 else "Low" if prob < low - 1e-9 else "Medium"
        rows.append({"match_id": rec["game_id"], "league": rec["league"],
                     "kickoff_utc": rec["tip_utc"], "home_id": rec["home_name"],
                     "away_id": rec["away_name"], "market": "bb_winner",
                     "side": "home" if home else "away",
                     "pick": f"{team} to win (overtime counts)", "prob": prob, "tier": tier})
    out = pd.DataFrame(rows, columns=["match_id", "league", "kickoff_utc", "home_id",
                                      "away_id", "market", "side", "pick", "prob", "tier"])
    out["fair_odds"] = (1 / out["prob"]).round(2)
    out["tier_rank"] = out["tier"].map(TIER_RANK).fillna(0).astype(int)
    return out


def _won(market: str, side: str, res: dict) -> bool | None:
    if market == "correct_score":
        hg, ag = res.get("home_goals"), res.get("away_goals")
        if hg is None or ag is None or pd.isna(hg) or pd.isna(ag):
            return None
        return f"{int(hg)}-{int(ag)}" == side
    if market == "bb_winner":
        hp, ap = res.get("home_pts"), res.get("away_pts")
        if hp is None or ap is None or pd.isna(hp) or pd.isna(ap) or hp == ap:
            return None
        return bool((hp > ap) == (side == "home"))
    hg, ag = res.get("home_goals"), res.get("away_goals")
    if hg is None or ag is None or pd.isna(hg) or pd.isna(ag):
        return None
    if market == "1x2":
        actual = "home" if hg > ag else "away" if ag > hg else "draw"
        return actual == side
    _, _, _, qty, line = LINE_MARKETS[market]
    if qty == "goals":
        value = hg + ag
    elif qty == "btts":
        value = float(hg > 0 and ag > 0)
    else:
        h, a = res.get(f"home_{qty}"), res.get(f"away_{qty}")
        if h is None or a is None or pd.isna(h) or pd.isna(a):
            return None
        value = h + a
    return (value > line) == (side == "over")


def settle(picks: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """Add `status`: won, lost or pending (no result yet)."""
    by_match = results.set_index("match_id").to_dict("index")
    status = []
    for rec in picks.to_dict("records"):
        res = by_match.get(rec["match_id"])
        won = None if res is None else _won(rec["market"], rec["side"], res)
        status.append("pending" if won is None else "won" if won else "lost")
    return picks.assign(status=status)


def settle_coupon(coupon: dict, results: pd.DataFrame) -> str:
    legs = settle(pd.DataFrame(coupon["legs"]), results)["status"]
    if (legs == "lost").any():
        return "lost"
    return "won" if (legs == "won").all() else "pending"


FAMILY = {"1x2": "result", "over_1_5": "goals", "over_2_5": "goals", "over_3_5": "goals",
          "btts": "goals", "bb_winner": "basketball"}


def family(market: str) -> str:
    if market.startswith("corners_"):
        return "corners"
    if market.startswith("yellows_"):
        return "yellows"
    return FAMILY.get(market, market)


def top3(c: pd.DataFrame, s: Settings = DEFAULT) -> pd.DataFrame:
    """Today's Top 3: the three likeliest picks, one per game, Medium tier or better.
    The caller passes only today's candidates."""
    ok = c[c["tier_rank"] >= TIER_RANK[s.free_min_tier]]
    best = _best_per_match(ok).sort_values("prob", ascending=False, kind="stable")
    return best.head(3).reset_index(drop=True)


def bankers(c: pd.DataFrame) -> pd.DataFrame:
    """VIP Bankers: every game's strongest High-tier pick, strongest first (no cap)."""
    best = _best_per_match(c[c["tier"] == "High"])
    return best.sort_values("prob", ascending=False, kind="stable").reset_index(drop=True)


def full_card(c: pd.DataFrame, s: Settings = DEFAULT) -> pd.DataFrame:
    """VIP Full Card: up to two picks per game, Medium tier or better, from different market
    families (result, goals, corners, yellows), so the two picks are not the same bet twice."""
    ok = c[c["tier_rank"] >= TIER_RANK[s.free_min_tier]].assign(
        family=lambda d: d["market"].map(family))
    ok = ok.sort_values(["tier_rank", "prob"], ascending=[False, False], kind="stable")
    ok = ok.drop_duplicates(["match_id", "family"], keep="first")
    out = ok.groupby("match_id", sort=False).head(2)
    return out.sort_values(["kickoff_utc", "match_id", "prob"], ascending=[True, True, False],
                           kind="stable").drop(columns="family").reset_index(drop=True)


def correct_scores(forecasts: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """VIP Correct Score: each game's likeliest exact score, the `n` likeliest games.

    `forecasts` needs match_id, league, kickoff_utc, home_id, away_id and top_scorelines
    (JSON list of {"score": "h-a", "p": chance})."""
    rows = []
    for rec in forecasts.to_dict("records"):
        raw = rec.get("top_scorelines")
        top = json.loads(raw) if isinstance(raw, str) and raw else []
        if not top:
            continue
        best = max(top, key=lambda t: t["p"])
        rows.append({k: rec.get(k) for k in ("match_id", "league", "kickoff_utc", "home_id",
                                              "away_id")} |
                    {"market": "correct_score", "side": best["score"],
                     "pick": f"Correct score {best['score']}", "prob": float(best["p"]),
                     "tier": "Low"})
    out = pd.DataFrame(rows, columns=["match_id", "league", "kickoff_utc", "home_id", "away_id",
                                      "market", "side", "pick", "prob", "tier"])
    out["fair_odds"] = (1 / out["prob"]).round(2)
    out["tier_rank"] = 0
    return out.sort_values("prob", ascending=False, kind="stable").head(n).reset_index(drop=True)


def accumulators(c: pd.DataFrame, sizes: tuple[int, ...] = (3, 4)) -> list[dict]:
    """VIP Accumulator: 3-fold and 4-fold from the strongest High picks, one leg per game,
    NBL kept out (TOP_EXCLUDED)."""
    out = coupons(c, Settings(coupon_sizes=sizes))
    for cp in out:
        cp["name"] = f"{len(cp['legs'])}-fold"
    return out


def build_day(c: pd.DataFrame, s: Settings = DEFAULT) -> dict:
    """All products for one batch of candidates (one day or one lock run)."""
    return {"free": free_tips(c, s), "premium": premium(c, s), "diamond": diamond(c, s),
            "coupons": coupons(c, s)}
