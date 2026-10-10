"""Pairs for the Model Lab: the most likely pairs of outcomes on a matchday.

Lang's rules (10 Oct 2026):
- a pair is two picks, from the same match or from two matches;
- picks are the published lines, both sides: home win, draw, away win; over or under
  1.5, 2.5, 3.5 goals; both teams score yes or no; over or under 8.5 to 11.5 corners;
  over or under 3.5 to 5.5 yellow cards;
- ranked by the chance that both happen, using the goals fix shape_v1;
- no pick used twice.

Joint chances: two goals picks from one match (result, goal lines, both teams score)
come from the score grid, so their link is exact. A corners or cards pick is treated
as unrelated to the other picks of its match [A]. Picks from two matches multiply.
A pair where one pick implies the other (over 2.5 and over 1.5), or two lines of the
same count, is skipped: it is one pick in disguise.

This is a view of likelihood, not betting advice (spec S14).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fp.evaluate import metrics
from fp.models import shape
from fp.teams import to_team_id

K = np.arange(11)
TOTAL = K[:, None] + K[None, :]
HOME = K[:, None] > K[None, :]
DRAW = K[:, None] == K[None, :]
AWAY = K[:, None] < K[None, :]
GOAL_LINES = (1.5, 2.5, 3.5)
CORNER_LINES = (8.5, 9.5, 10.5, 11.5)
YELLOW_LINES = (3.5, 4.5, 5.5)
JUBA = "Africa/Juba"
TOP_PAIRS = 10
TEST = (2023, 2024, 2025)


def _n(x: float) -> int:
    return int(np.ceil(x))


def picks(mat: np.ndarray, cpmf: np.ndarray | None, ypmf: np.ndarray | None,
          home: str, away: str) -> list[dict]:
    """Every allowed pick for one match. Goals picks carry a grid mask, so the joint
    chance of two of them is exact."""
    out = []
    for key, label, mask in (("H", f"{home} win", HOME), ("D", "Draw", DRAW),
                             ("A", f"{away} win", AWAY)):
        out.append({"k": key, "fam": "result", "label": label, "mask": mask})
    for line in GOAL_LINES:
        out.append({"k": f"G>{line}", "fam": "goals", "label": f"{_n(line)} or more goals",
                    "mask": TOTAL > line})
        out.append({"k": f"G<{line}", "fam": "goals",
                    "label": f"{int(line)} goal{'s' if int(line) != 1 else ''} or fewer",
                    "mask": TOTAL < line})
    both = (K[:, None] > 0) & (K[None, :] > 0)
    out.append({"k": "BTTS", "fam": "btts", "label": "Both teams score", "mask": both})
    out.append({"k": "NoBTTS", "fam": "btts", "label": "Not both teams score", "mask": ~both})
    for p in out:
        p["p"] = float(mat[p["mask"]].sum())
    for fam, pmf, lines, noun in (("corners", cpmf, CORNER_LINES, "corners"),
                                  ("yellows", ypmf, YELLOW_LINES, "yellow cards")):
        if pmf is None:
            continue
        pmf = np.asarray(pmf, dtype=float)
        pmf = pmf / pmf.sum()
        kk = np.arange(len(pmf))
        for line in lines:
            over = float(pmf[kk > line].sum())
            out.append({"k": f"{fam[0].upper()}>{line}", "fam": fam,
                        "label": f"{_n(line)} or more {noun}", "p": over})
            out.append({"k": f"{fam[0].upper()}<{line}", "fam": fam,
                        "label": f"{int(line)} {noun} or fewer", "p": 1 - over})
    return out


def same_match_joint(a: dict, b: dict, mat: np.ndarray) -> float | None:
    """Joint chance of two picks from one match, or None when the pair is not
    allowed (same count twice, impossible together, or one implies the other)."""
    if a["fam"] == b["fam"] and a["fam"] in ("result", "goals", "btts", "corners", "yellows"):
        return None
    if "mask" in a and "mask" in b:
        joint = float(mat[a["mask"] & b["mask"]].sum())
    else:
        joint = a["p"] * b["p"]  # [A] corners and cards unrelated to the rest
    if joint < 1e-6 or joint >= min(a["p"], b["p"]) - 1e-6:
        return None
    return joint


def match_block(mid: str, mat: np.ndarray, cpmf, ypmf, home: str, away: str) -> dict:
    ps = picks(mat, cpmf, ypmf, home, away)
    joint = {}
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            v = same_match_joint(ps[i], ps[j], mat)
            if v is not None:
                joint[f"{i},{j}"] = round(v, 5)
    return {"picks": [{k: v for k, v in p.items() if k != "mask"} for p in ps],
            "joint": joint}


def best_pairs(blocks: dict[str, dict], kind: str = "either", families: set[str] | None = None,
               n: int = TOP_PAIRS) -> list[dict]:
    """Greedy: highest joint chance first, no pick used twice (same as the page)."""
    cands = []
    ids = list(blocks)
    allowed = (lambda p: p["fam"] in families) if families else (lambda p: True)
    if kind in ("either", "same"):
        for mid in ids:
            ps = blocks[mid]["picks"]
            for key, v in blocks[mid]["joint"].items():
                i, j = (int(x) for x in key.split(","))
                if allowed(ps[i]) and allowed(ps[j]):
                    cands.append((v, (mid, i), (mid, j)))
    if kind in ("either", "two"):
        flat = [(mid, i, p["p"]) for mid in ids for i, p in enumerate(blocks[mid]["picks"])
                if allowed(p)]
        flat.sort(key=lambda x: -x[2])
        top = flat[:60]  # the best two-match pairs only use the strongest picks
        for x in range(len(top)):
            for y in range(x + 1, len(top)):
                if top[x][0] != top[y][0]:
                    cands.append((top[x][2] * top[y][2], top[x][:2], top[y][:2]))
    cands.sort(key=lambda c: -c[0])
    used, out = set(), []
    for v, a, b in cands:
        if a in used or b in used:
            continue
        used |= {a, b}
        out.append({"p": v, "a": a, "b": b})
        if len(out) == n:
            break
    return out


def happened(pick: dict, hg: int, ag: int, corners: float, yellows: float) -> bool | None:
    k = pick["k"]
    if k == "H":
        return hg > ag
    if k == "D":
        return hg == ag
    if k == "A":
        return hg < ag
    if k in ("BTTS", "NoBTTS"):
        return (hg > 0 and ag > 0) == (k == "BTTS")
    count = {"G": hg + ag, "C": corners, "Y": yellows}[k[0]]
    if count is None or not np.isfinite(count):
        return None
    line = float(k[2:])
    return count > line if k[1] == ">" else count < line


def track_record(fixed: np.ndarray, gf: pd.DataFrame, backtests: Path,
                 matches: pd.DataFrame, names: dict[str, str]) -> dict:
    """The default pairs (either kind, every market, top 10, no pick twice) on every
    matchday of the test seasons: what the model promised and what happened."""
    corners = pd.read_parquet(backtests / "corners_total_poisson_walkforward_2021_2025.parquet"
                              ).set_index("match_id")
    cards = pd.read_parquet(backtests / "cards_nb_walkforward_2021_2025.parquet").set_index(
        "match_id")
    m = matches.set_index("match_id")
    frame = gf.assign(day=pd.to_datetime(gf["kickoff_utc"], utc=True).dt.tz_convert(JUBA)
                      .dt.date)
    rows = []
    for day, g in frame[frame["season"].isin(TEST)].groupby("day"):
        if len(g) < 2:
            continue
        blocks, facts = {}, {}
        for idx, r in g.iterrows():
            mid = r["match_id"]
            blocks[mid] = match_block(mid, fixed[idx], corners.at[mid, "pmf"] if mid in
                                      corners.index else None,
                                      cards.at[mid, "pmf"] if mid in cards.index else None,
                                      names.get(m.at[mid, "home_id"], ""),
                                      names.get(m.at[mid, "away_id"], ""))
            facts[mid] = (int(r["hg"]), int(r["ag"]),
                          float(m.at[mid, "home_corners"] + m.at[mid, "away_corners"]),
                          float(m.at[mid, "home_yellows"] + m.at[mid, "away_yellows"]))
        for rank, pair in enumerate(best_pairs(blocks), 1):
            res = [happened(blocks[mid]["picks"][i], *facts[mid]) for mid, i in
                   (pair["a"], pair["b"])]
            if None in res:
                continue
            rows.append({"day": str(day), "rank": rank, "p": pair["p"], "hit": all(res),
                         "same": pair["a"][0] == pair["b"][0]})
    t = pd.DataFrame(rows)
    bands = []
    for lo, hi in ((0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)):
        s = t[(t["p"] >= lo) & (t["p"] < hi)]
        if len(s) < 10:
            continue
        hits = s["hit"].to_numpy(float)
        rng = np.random.default_rng(int(lo * 100))
        boot = hits[rng.integers(0, len(hits), (2000, len(hits)))].mean(1)
        bands.append({"band": f"{lo:.0%} to {min(hi, 1):.0%}", "n": len(s),
                      "promised": float(s["p"].mean()), "won": float(hits.mean()),
                      "lo": float(np.quantile(boot, 0.025)),
                      "hi": float(np.quantile(boot, 0.975))})
    by_rank = t.groupby("rank").agg(n=("hit", "size"), promised=("p", "mean"),
                                    won=("hit", "mean")).reset_index()
    return {"days": int(t["day"].nunique()), "pairs": len(t),
            "promised": float(t["p"].mean()), "won": float(t["hit"].mean()),
            "same_share": float(t["same"].mean()), "bands": bands,
            "by_rank": by_rank.round(4).to_dict("records")}


def bookmaker(raw: Path | None) -> dict[str, dict]:
    """Bookmaker chances (average odds, margin removed) for home, draw, away and 3+
    goals, keyed by our match id. Shown beside picks, never used to rank them."""
    if raw is None or not raw.exists():
        return {}
    d = pd.read_csv(raw, encoding="utf-8-sig")
    d = d[d["Div"].isin(["E0", "SP1"])]
    out: dict[str, dict] = {}
    for _, r in d.iterrows():
        try:
            h = to_team_id(str(r["HomeTeam"]), "football_data_co_uk")
            a = to_team_id(str(r["AwayTeam"]), "football_data_co_uk")
        except Exception:
            continue
        lg = "EPL" if r["Div"] == "E0" else "LaLiga"
        x12 = metrics.demargin_power(np.array([[r["AvgH"], r["AvgD"], r["AvgA"]]], dtype=float))[0]
        ou = metrics.demargin_power(np.array([[r.get("Avg>2.5"), r.get("Avg<2.5")]],
                                             dtype=float))[0]
        rec = {"H": x12[0], "D": x12[1], "A": x12[2], "G>2.5": ou[0], "G<2.5": ou[1]}
        out[f"{lg}_2627_{h}_{a}"] = {k: (round(float(v), 4) if np.isfinite(v) else None)
                                     for k, v in rec.items()}
    return out


def upcoming(pages: Path, sh: shape.Shape, names_by_id: dict[str, str], raw_odds: Path | None
             ) -> dict:
    """Pair data for every day of the published snapshot, in Juba time."""
    fx = pd.read_parquet(pages / "fixtures.parquet")
    det = pd.read_parquet(pages / "details.parquet").set_index("match_id")
    odds = bookmaker(raw_odds)
    blocks, days = {}, {}
    for r in fx.itertuples():
        if r.match_id not in det.index:
            continue
        d = det.loc[r.match_id]
        if shape.RULE in str(r.flags):
            mat = np.asarray(d["matrix"], dtype=float).reshape(11, 11)
        else:  # locked before the fix: apply it to the plain expected goals, as live
            mat = shape.shaped(np.array([r.exp_goals_home]), np.array([r.exp_goals_away]), sh)[0]
        cp = d["corners_pmf"] if isinstance(d["corners_pmf"], (list, np.ndarray)) else None
        yp = d["cards_pmf"] if isinstance(d["cards_pmf"], (list, np.ndarray)) else None
        b = match_block(r.match_id, mat, cp, yp, str(r.home_name), str(r.away_name))
        kick = pd.Timestamp(r.kickoff_utc)
        b.update({"h": str(r.home_name), "a": str(r.away_name),
                  "lg": "La Liga" if r.league == "LaLiga" else "Premier League",
                  "kickoff": f"{kick:%Y-%m-%dT%H:%MZ}", "locked": bool(r.locked),
                  "odds": odds.get(r.match_id, {})})
        for p in b["picks"]:
            p["p"] = round(p["p"], 5)
        blocks[r.match_id] = b
        day = kick.tz_convert(JUBA)
        days.setdefault(f"{day:%Y-%m-%d}", {"label": f"{day:%a %d %b}", "ids": []})["ids"].append(
            r.match_id)
    return {"matches": blocks,
            "days": [{"key": k, **v} for k, v in sorted(days.items())]}


def dumps(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"))
