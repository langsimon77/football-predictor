"""Basketball phase B4: live ratings, the ledger and the daily step, on toy games."""
from __future__ import annotations

import importlib
import json
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from fp import ROOT
from fp.ledger import LedgerError

sys.path.insert(0, str(ROOT / "basketball"))
models = importlib.import_module("models")
ledger_bb = importlib.import_module("ledger_bb")
live = importlib.import_module("live")

CLUBS = ["a", "b", "c", "d"]


def season_games(seed: int = 1, days: int = 40, start: date = date(2026, 9, 1)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    strength = {"a": 6.0, "b": 2.0, "c": -2.0, "d": -6.0}
    rows = []
    for k in range(days):
        day = start + timedelta(days=k)
        h, a = rng.choice(CLUBS, 2, replace=False)
        hp = 82 + strength[h] - strength[a] / 2 + 3 + rng.normal(0, 9)
        ap = 82 + strength[a] - strength[h] / 2 + rng.normal(0, 9)
        if round(hp) == round(ap):
            hp += 1
        rows.append({"date": day, "season": 2026, "home_id": h, "away_id": a,
                     "home_pts": float(round(hp)), "away_pts": float(round(ap))})
    return pd.DataFrame(rows)


def test_elo_ratings_give_the_same_forecast_as_elo_run():
    g = season_games()
    s = models.EloSettings(20, 100, 0.75, True)
    nxt = pd.DataFrame([{"date": g["date"].iloc[-1] + timedelta(days=1), "season": 2026,
                         "home_id": "b", "away_id": "c", "home_pts": 80.0, "away_pts": 70.0}])
    walk = models.elo_run(pd.concat([g, nxt], ignore_index=True), s)["elo_diff"].iloc[-1]
    r = models.elo_ratings(g, s, season=2026)
    assert r["b"] + 100 - r["c"] == pytest.approx(walk)
    # A new season pulls every rating part way back to 1500.
    r2 = models.elo_ratings(g, s, season=2027)
    assert r2["a"] - 1500 == pytest.approx(0.75 * (r["a"] - 1500))


def test_points_fit_matches_points_run_on_the_next_day():
    g = season_games(seed=3)
    s = models.PointsSettings(60, 3)
    nxt = pd.DataFrame([{"date": g["date"].iloc[-1] + timedelta(days=2), "season": 2026,
                         "home_id": "a", "away_id": "d", "home_pts": 0.0, "away_pts": 0.0}])
    run = models.points_run(pd.concat([g, nxt], ignore_index=True), s).iloc[-1]
    fit = models.points_fit(g, s, nxt["date"].iloc[0])
    mh, ma = models.points_expect(fit, "a", "d")
    assert mh == pytest.approx(run["m_home"], rel=1e-9)
    assert ma == pytest.approx(run["m_away"], rel=1e-9)
    assert models.points_expect(fit, "new", "a")[0] > 0  # an unseen club gets 0 ratings


def row(game_id: str, tip: pd.Timestamp, lock: pd.Timestamp, p: float = 0.6) -> dict:
    return {"prediction_id": f"{game_id}:m", "game_id": game_id, "league": "NBL", "season": 2026,
            "round": "Round 1", "home_id": "a", "away_id": "b", "home_name": "A",
            "away_name": "B", "tip_utc": tip, "lock_utc": lock, "as_of_utc": lock,
            "model_name": "m", "model_version": "x", "code_dirty": False, "late_lock": False,
            "p_home": p, "margin_mean": np.nan, "margin_sd": np.nan, "total_mean": np.nan,
            "total_sd": np.nan, "flags": "[]"}


def test_ledger_locks_once_and_detects_tampering(tmp_path):
    path = tmp_path / "bb.parquet"
    now = pd.Timestamp("2026-10-30 08:00", tz="UTC")
    tip = now + pd.Timedelta(hours=30)
    ledger_bb.append(pd.DataFrame([row("g1", tip, now)]), path)
    led = ledger_bb.append(pd.DataFrame([row("g2", tip, now)]), path)
    ledger_bb.verify_chain(led)
    assert len(led) == 2
    with pytest.raises(LedgerError, match="already locked"):
        ledger_bb.append(pd.DataFrame([row("g1", tip, now)]), path)
    with pytest.raises(LedgerError, match="after tip-off"):
        ledger_bb.append(pd.DataFrame([row("g3", now, now)]), path)
    bad = led.copy()
    bad.loc[0, "p_home"] = 0.9
    with pytest.raises(LedgerError, match="chain broken"):
        ledger_bb.verify_chain(bad)


SETTINGS = {
    "EuroLeague": {"elo": {"k": 30, "home": 100, "carry": 0.5, "mov": True,
                           "margin_scale_b": 0.04, "margin_sd": 12.0},
                   "points": {"half_life": 120, "penalty": 10, "sd_home": 10.0,
                              "sd_away": 10.5, "rho": 0.3}},
    "NBL": {"elo": {"k": 20, "home": 75, "carry": 0.75, "mov": True,
                    "margin_scale_b": 0.04, "margin_sd": 13.0},
            "points": {"half_life": 60, "penalty": 3, "sd_home": 11.0, "sd_away": 11.0,
                       "rho": 0.2}}}


def games_table(now: pd.Timestamp) -> pd.DataFrame:
    played = []
    for league in ("EuroLeague", "NBL"):
        start = (now - pd.Timedelta(days=45)).date()
        g = season_games(seed=5 if league == "NBL" else 7, start=start)
        for r in g.itertuples():
            played.append({"league": league, "season": 2026, "date": r.date, "home_id": r.home_id,
                           "away_id": r.away_id, "home_pts": r.home_pts, "away_pts": r.away_pts,
                           "played": True, "tip_utc": pd.Timestamp(r.date, tz="UTC")
                           + pd.Timedelta(hours=18)})

    def fixture(league, h, a, hours):
        tip = now + pd.Timedelta(hours=hours) if hours is not None else pd.NaT
        day = (tip if hours is not None else now + pd.Timedelta(days=3)).tz_convert(
            "Africa/Juba").date()
        return {"league": league, "season": 2026, "date": day, "home_id": h, "away_id": a,
                "home_pts": np.nan, "away_pts": np.nan, "played": False, "tip_utc": tip}

    fx = [fixture("EuroLeague", "a", "d", 30), fixture("EuroLeague", "b", "c", 0.5),
          fixture("NBL", "c", "a", 20), fixture("NBL", "d", "b", 60),
          fixture("NBL", "a", "b", None)]
    g = pd.DataFrame(played + fx)
    g["home_title"], g["away_title"] = g["home_id"].str.upper(), g["away_id"].str.upper()
    g["section"], g["left_out"], g["overtime"] = "Round 9", False, False
    g["game_id"] = [f"{lg}_{h}_{a}_{i}" for i, (lg, h, a) in
                    enumerate(zip(g["league"], g["home_id"], g["away_id"], strict=True))]
    g["tip_utc"] = pd.to_datetime(g["tip_utc"], utc=True)
    return g


def context(tmp_path, now):
    return live.Context(games=games_table(now), settings=SETTINGS,
                        ledger_path=tmp_path / "p.parquet", results_path=tmp_path / "r.parquet",
                        upcoming_path=tmp_path / "u.parquet", report_path=tmp_path / "latest.md")


def test_daily_step_locks_the_window_and_shows_tested_markets_only(tmp_path):
    now = pd.Timestamp("2026-10-30 08:00", tz="UTC")
    ctx = context(tmp_path, now)
    new = live.run_once(now, ctx).set_index("game_id")
    # 30 h ahead: on time; 20 h: late; 0.5 h: too close; 60 h: not yet; no time: cannot lock.
    assert set(new["league"]) == {"EuroLeague", "NBL"} and len(new) == 2
    eu = new[new["league"] == "EuroLeague"].iloc[0]
    nbl = new[new["league"] == "NBL"].iloc[0]
    assert not eu["late_lock"] and nbl["late_lock"]
    assert eu["p_home"] > 0.5  # the strongest club at home to the weakest
    assert np.isfinite(eu["margin_mean"]) and np.isfinite(eu["total_mean"])
    assert np.isnan(nbl["margin_mean"]) and np.isnan(nbl["total_mean"])  # NBL: winner only
    assert "late_lock" in json.loads(nbl["flags"])
    assert live.run_once(now + pd.Timedelta(hours=1), ctx).empty  # nothing locks twice
    up = pd.read_parquet(ctx.upcoming_path)
    assert up["locked"].sum() == 2
    assert up["tip_utc"].isna().sum() == 1  # the game with no published time is still shown
    ledger_bb.verify_chain(ledger_bb.load(ctx.ledger_path))


def test_results_are_recorded_for_locked_games(tmp_path):
    now = pd.Timestamp("2026-10-30 08:00", tz="UTC")
    ctx = context(tmp_path, now)
    live.run_once(now, ctx)
    g = ctx.games
    gid = g.loc[(g["league"] == "EuroLeague") & ~g["played"] & (g["home_id"] == "a"), "game_id"]
    g.loc[g["game_id"].isin(gid), ["home_pts", "away_pts", "played"]] = [90.0, 80.0, True]
    live.run_once(now + pd.Timedelta(hours=40), ctx)
    res = pd.read_parquet(ctx.results_path)
    assert list(res["game_id"]) == list(gid) and int(res["home_pts"].iloc[0]) == 90


def test_basketball_files_are_apart_from_football_files():
    from fp import ledger
    assert live.LEDGER.parent.name == "basketball"
    assert not {live.LEDGER, live.RESULTS} & {ledger.PREDICTIONS, ledger.RESULTS}
    assert live.short_name("Beşiktaş J.K. (men's basketball)") == "Beşiktaş"
    assert live.short_name("Some Club B.C.") == "Some Club"
