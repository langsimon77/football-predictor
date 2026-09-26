"""Precomputed files for the dashboard and the static fixtures page (spec S9).

The daily run calls `export` after locking. The dashboard only reads these files:
no model fitting there (spec S9, Performance). Everything goes to `app/data/`:

- fixtures.parquet: the next 8 days and each league's next round, one row per
  match: the locked primary
  forecast, or a provisional one (PRD item 26a) if the match has not locked yet.
- details.parquet: per match, the scoreline table, corners and yellows
  distributions, every model's forecast, plain-English drivers, the referee, and
  the numbers the what-if page needs. Frozen at lock: a locked match keeps the
  details from its lock run.
- ratings.parquet: attack and defence per club today; ratings_history.csv keeps
  one row per club per day (plain text, committed, so Git stores it cheaply).
- projection.parquet: season-end chances from 10,000 simulations.
- performance.parquet: every scored ledger row, plus base rates and the market.
- questions.json and meta.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from fp import ROOT
from fp.evaluate import metrics
from fp.models import bayes_dc
from fp.models import counts_nb as cn
from fp.publish import drivers, season
from fp.validate.leakage import known_as_of

OUT = ROOT / "app" / "data"
HORIZON_DAYS = 8
KEEP_DETAILS_DAYS = 14
WHATIF_DRAWS = 200
BASE_WINDOW_DAYS = 1100
PRIMARY_ORDER = ["dc_bayes_v1", "dc_mle_v0"]
FIXTURE_COLUMNS = [
    "match_id", "league", "season", "round", "home_id", "away_id", "home_name", "away_name",
    "kickoff_utc", "locked", "lock_utc", "model_name", "p_home", "p_draw", "p_away",
    "p_over_1_5", "p_over_2_5", "p_over_3_5", "p_btts", "exp_goals_home", "exp_goals_away",
    "exp_corners_home", "exp_corners_away", "exp_yellows", "p_corners_over_9_5",
    "p_yellows_over_4_5", "intervals", "tiers", "flags", "news_adjustments",
    "unanswered_questions",
]


@dataclass
class RunView:
    """What one daily run knows, handed to the exporter."""

    now: pd.Timestamp
    ledger: pd.DataFrame
    results: pd.DataFrame
    provisional: pd.DataFrame
    matches: pd.DataFrame
    fixtures: pd.DataFrame
    models: dict[str, Any]
    counts: dict[str, Any] | None = None
    features: pd.DataFrame | None = None
    referees: dict[str, str] = field(default_factory=dict)
    manager_flags: set[str] = field(default_factory=set)
    names: dict[str, str] = field(default_factory=dict)
    questions: list[dict] = field(default_factory=list)
    model_version: str = ""


def _primary(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per match: the primary model's latest lock (a re-lock after a moved
    kickoff replaces the original for display and scoring, PRD item 26b)."""
    rows = rows[rows["model_name"].isin(PRIMARY_ORDER)].copy()
    rows["rank"] = rows["model_name"].map({m: i for i, m in enumerate(PRIMARY_ORDER)})
    if "lock_utc" in rows:
        rows = rows.sort_values(["rank", "lock_utc"], ascending=[True, False],
                                na_position="last")
    else:
        rows = rows.sort_values("rank")
    return rows.drop_duplicates("match_id").drop(columns="rank")


def window(fixtures: pd.DataFrame, now: pd.Timestamp) -> set[str]:
    """Matches to show: every kickoff in the next 8 days, plus each league's next
    round in full (spec S9: next gameweek), so an international break is not blank."""
    ahead = fixtures[fixtures["kickoff_utc"] > now]
    ids = set(ahead.loc[ahead["kickoff_utc"] <= now + pd.Timedelta(days=HORIZON_DAYS),
                        "match_id"])
    for _, lg in ahead.groupby("league"):
        first = lg.sort_values("kickoff_utc").iloc[0]["round"]
        ids |= set(lg.loc[lg["round"] == first, "match_id"])
    return ids


def upcoming(view: RunView) -> pd.DataFrame:
    shown = window(view.fixtures, view.now)
    locked = _primary(view.ledger).assign(locked=True) if len(view.ledger) else pd.DataFrame()
    prov = _primary(view.provisional).assign(locked=False) if len(view.provisional) \
        else pd.DataFrame()
    if len(prov):
        prov["lock_utc"] = pd.Series(pd.NaT, index=prov.index, dtype="datetime64[us, UTC]")
    rows = pd.concat([locked, prov], ignore_index=True)
    if rows.empty:
        return pd.DataFrame(columns=FIXTURE_COLUMNS)
    rows = rows[(rows["kickoff_utc"] > view.now) & rows["match_id"].isin(shown)]
    rows = rows.drop_duplicates("match_id", keep="first")  # a locked row wins
    rounds = view.fixtures.set_index("match_id")["round"]
    rows["round"] = rows["match_id"].map(rounds)
    rows["home_name"] = rows["home_id"].map(view.names).fillna(rows["home_id"])
    rows["away_name"] = rows["away_id"].map(view.names).fillna(rows["away_id"])
    return rows.reindex(columns=FIXTURE_COLUMNS).sort_values("kickoff_utc").reset_index(drop=True)


def _thin(x: np.ndarray, n: int = WHATIF_DRAWS) -> list[float]:
    idx = np.linspace(0, len(x) - 1, min(n, len(x))).astype(int)
    return [round(float(v), 5) for v in np.asarray(x)[idx]]


def detail(view: RunView, row: pd.Series, all_rows: pd.DataFrame) -> dict | None:
    """Everything the match page needs for one match, from this run's fits."""
    m = view.models.get(str(row["league"]))
    home, away = str(row["home_id"]), str(row["away_id"])
    if m is None or m.bayes is None or home not in m.bayes.teams or away not in m.bayes.teams:
        return None
    news = json.loads(row["news_adjustments"]) if isinstance(row["news_adjustments"], str) else []
    scale = ((news[0]["scale_home_goals"], news[0]["scale_away_goals"]) if news else (1.0, 1.0))
    post = m.bayes
    mk = bayes_dc.markets(post, home, away, scale=scale)
    lam, nu = post.rates(home, away)
    out: dict[str, Any] = {
        "match_id": row["match_id"], "locked": bool(row["locked"]),
        "kickoff_utc": row["kickoff_utc"], "matrix": [round(float(v), 6) for v in
                                                      np.asarray(mk["matrix"]).ravel()],
        "models": json.dumps([
            {"model": str(r.model_name), "p_home": float(r.p_home), "p_draw": float(r.p_draw),
             "p_away": float(r.p_away)}
            for r in all_rows[all_rows["match_id"] == row["match_id"]].itertuples()]),
        "drivers": json.dumps(drivers.drivers(
            post, home, away, view.names, str(row["league"]),
            elo_gap=float(m.tracker.gap(home, away)), news=news[0] if news else None,
            promoted=m.promoted, manager_change=view.manager_flags,
            current=set(view.fixtures.loc[view.fixtures["league"] == row["league"],
                                          "home_id"]))),
        "whatif": json.dumps({
            "lam": _thin(lam), "nu": _thin(nu), "home": _thin(post.home), "rho": _thin(post.rho),
            "scale": list(scale)}),
        "corners_pmf": None, "cards_pmf": None, "referee": None,
    }
    counts = (view.counts or {}).get(str(row["league"]))
    features = view.features if view.features is not None else pd.DataFrame(
        columns=["match_id"])
    f = features[features["match_id"] == row["match_id"]]
    if counts is not None and len(f):
        if counts.corners is not None:
            r = cn.total_corner_rows(f, features).iloc[0].to_dict()
            out["corners_pmf"] = [round(float(v), 6) for v in cn.predict(counts.corners, r)["pmf"]]
        if counts.cards is not None:
            ref = view.referees.get(str(row["match_id"]))
            r = cn.card_rows(f.assign(referee=ref), features).iloc[0].to_dict()
            pred = cn.predict(counts.cards, r)
            out["cards_pmf"] = [round(float(v), 6) for v in pred["pmf"]]
            post_c = counts.cards
            refs = {}
            if "ref" in post_c.draws:
                refs = {name: round(float(post_c.draws["ref"][:, j].mean()), 4)
                        for j, name in enumerate(post_c.referees)}
            eta = cn.match_eta(post_c, r)
            alpha = post_c.draws.get("alpha")
            out["referee"] = json.dumps({
                "name": ref, "known": bool(pred.get("referee_known")),
                "effect": refs.get(ref) if ref else None, "effects": refs,
                "eta": _thin(eta), "alpha": _thin(alpha) if alpha is not None else None,
                "sigma_ref": float(np.mean(post_c.draws["sigma_ref"]))
                if "sigma_ref" in post_c.draws else 0.0})
    return out


def ratings(view: RunView) -> pd.DataFrame:
    rows = []
    for league, m in view.models.items():
        post = m.bayes
        if post is None:
            continue
        this_season = set(view.fixtures.loc[view.fixtures["league"] == league, "home_id"])
        for i, team in enumerate(post.teams):
            if team not in this_season:
                continue
            att, dfn = np.exp(post.att[:, i]), np.exp(post.def_[:, i])
            rows.append({"as_of_utc": view.now, "league": league, "team_id": team,
                         "team_name": view.names.get(team, team),
                         "attack": float(att.mean()), "attack_lo": float(np.percentile(att, 10)),
                         "attack_hi": float(np.percentile(att, 90)),
                         "defence": float(dfn.mean()), "defence_lo": float(np.percentile(dfn, 10)),
                         "defence_hi": float(np.percentile(dfn, 90))})
    return pd.DataFrame(rows)


def projection(view: RunView) -> pd.DataFrame:
    out = []
    known = known_as_of(view.matches, view.now)
    for league, m in view.models.items():
        if m.bayes is None:
            continue
        fx = view.fixtures[view.fixtures["league"] == league]
        season_id = int(fx["season"].max())
        played = known[(known["league"] == league) & (known["season"] == season_id)]
        extra = fx[fx["home_goals"].notna() & ~fx["match_id"].isin(played["match_id"])
                   & (fx["kickoff_utc"] < view.now)]
        played = pd.concat([played[["home_id", "away_id", "home_goals", "away_goals"]],
                            extra[["home_id", "away_id", "home_goals", "away_goals"]]])
        done = set(known["match_id"]) | set(extra["match_id"])
        remaining = fx[~fx["match_id"].isin(done)]
        sim = season.simulate(m.bayes, played, remaining)
        sim.insert(0, "league", league)
        sim["team_name"] = sim["team_id"].map(view.names).fillna(sim["team_id"])
        sim["as_of_utc"] = view.now
        out.append(sim)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _market(frame: pd.DataFrame, prefix: str) -> np.ndarray:
    return metrics.demargin_power(frame[[f"{prefix}_home", f"{prefix}_draw",
                                         f"{prefix}_away"]].to_numpy(dtype=float))


def performance(view: RunView) -> pd.DataFrame:
    """Every scored ledger row, plus base rates at lock and market prices."""
    if view.ledger.empty or view.results.empty:
        return pd.DataFrame()
    res = view.results.drop_duplicates("match_id", keep="last").set_index("match_id")
    latest = view.ledger.sort_values("lock_utc").drop_duplicates(["match_id", "model_name"],
                                                                  keep="last")
    rows = latest[latest["match_id"].isin(res.index)].copy()
    if rows.empty:
        return pd.DataFrame()
    rows["home_goals"] = rows["match_id"].map(res["home_goals"])
    rows["away_goals"] = rows["match_id"].map(res["away_goals"])
    for col in ("home_reds", "away_reds"):
        rows[col] = rows["match_id"].map(res[col]) if col in res else np.nan
    keep = ["match_id", "league", "season", "home_id", "away_id", "kickoff_utc", "lock_utc",
            "model_name", "p_home", "p_draw", "p_away", "p_over_2_5", "tiers", "flags",
            "news_adjustments", "unanswered_questions", "home_goals", "away_goals",
            "home_reds", "away_reds"]
    rows = rows.reindex(columns=keep)
    first = _primary(rows)
    extra = []
    known_all = view.matches
    m = view.matches.set_index("match_id")
    for r in first.itertuples():
        lock = cast(pd.Timestamp, r.lock_utc)
        known = known_as_of(known_all[known_all["league"] == r.league], lock)
        recent = known[known["kickoff_utc"] >= lock - pd.Timedelta(days=BASE_WINDOW_DAYS)]
        y = metrics.outcome_1x2(recent["home_goals"].to_numpy(), recent["away_goals"].to_numpy())
        base = np.bincount(y, minlength=3) / max(len(y), 1)
        over = float(((recent["home_goals"] + recent["away_goals"]) > 2.5).mean())
        common = {c: getattr(r, c) for c in keep if c not in
                  ("model_name", "p_home", "p_draw", "p_away", "p_over_2_5", "tiers", "flags",
                   "news_adjustments", "unanswered_questions")}
        extra.append({**common, "model_name": "base_rates", "p_home": base[0],
                      "p_draw": base[1], "p_away": base[2], "p_over_2_5": over})
        if r.match_id in m.index:
            odds = m.loc[[r.match_id]]
            for name, prefix in (("market_friday", "odds_avg_pre"),
                                 ("market_close", "odds_pin_close")):
                p = _market(odds, prefix)[0]
                if name == "market_close" and not np.isfinite(p).all():
                    p = _market(odds, "odds_bfe_close")[0]
                if np.isfinite(p).all():
                    extra.append({**common, "model_name": name, "p_home": p[0],
                                  "p_draw": p[1], "p_away": p[2]})
    out = pd.concat([rows, pd.DataFrame(extra)], ignore_index=True)
    out["outcome"] = metrics.outcome_1x2(out["home_goals"].to_numpy(dtype=int),
                                         out["away_goals"].to_numpy(dtype=int))
    out["over_2_5_happened"] = (out["home_goals"] + out["away_goals"]) > 2.5
    rounds = view.fixtures.set_index("match_id")["round"]
    out["round"] = out["match_id"].map(rounds)
    return out


def _write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def export(view: RunView, out: Path = OUT) -> pd.DataFrame:
    """Write every dashboard file. Returns the fixtures table (also used by the
    static page)."""
    out.mkdir(parents=True, exist_ok=True)
    fixtures = upcoming(view)
    _write(fixtures, out / "fixtures.parquet")

    all_rows = pd.concat([view.ledger, view.provisional], ignore_index=True)
    path = out / "details.parquet"
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    fresh = [d for d in (detail(view, r, all_rows) for _, r in fixtures.iterrows()
                         if not (len(old) and r["locked"]
                                 and r["match_id"] in set(old.loc[old["locked"], "match_id"])))
             if d is not None]
    details = pd.concat([old, pd.DataFrame(fresh)], ignore_index=True) if fresh else old
    if len(details):
        details = details.drop_duplicates("match_id", keep="last")
        details = details[pd.to_datetime(details["kickoff_utc"], utc=True)
                          > view.now - pd.Timedelta(days=KEEP_DETAILS_DAYS)]
        _write(details.reset_index(drop=True), path)

    rt = ratings(view)
    if len(rt):
        _write(rt, out / "ratings.parquet")
        hist_path = out / "ratings_history.csv"
        day = rt.assign(date=f"{view.now:%Y-%m-%d}").drop(columns=["as_of_utc", "team_name"])
        day = day.round(4)
        if hist_path.exists():
            hist = pd.read_csv(hist_path)
            hist = hist[hist["date"] != day["date"].iloc[0]]
            day = pd.concat([hist, day], ignore_index=True)
        day.to_csv(hist_path, index=False)
    proj = projection(view)
    if len(proj):
        _write(proj, out / "projection.parquet")
    perf = performance(view)
    _write(perf, out / "performance.parquet")
    (out / "questions.json").write_text(json.dumps(view.questions, indent=1, default=str),
                                        encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({
        "generated_utc": f"{view.now:%Y-%m-%dT%H:%MZ}", "model_version": view.model_version,
        "primary_model": PRIMARY_ORDER[0]}, indent=1), encoding="utf-8")
    return fixtures
