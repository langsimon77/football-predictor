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
    high = c[(c["tier"] == "High") & (c["fair_odds"] >= s.diamond_min_odds)]
    return high.sort_values("prob", ascending=False, kind="stable").head(1).reset_index(drop=True)


def coupons(c: pd.DataFrame, s: Settings = DEFAULT) -> list[dict]:
    """Double and treble from the strongest High picks, one leg per match."""
    legs = _best_per_match(c[c["tier"] == "High"]).sort_values("prob", ascending=False,
                                                               kind="stable")
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


def _won(market: str, side: str, res: dict) -> bool | None:
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


def build_day(c: pd.DataFrame, s: Settings = DEFAULT) -> dict:
    """All products for one batch of candidates (one day or one lock run)."""
    return {"free": free_tips(c, s), "premium": premium(c, s), "diamond": diamond(c, s),
            "coupons": coupons(c, s)}
