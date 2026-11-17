"""Basketball upgrade (B6): adaptive widths, odds, availability, blend."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import integrate, stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "basketball"))

import availability  # noqa: E402
import blend  # noqa: E402
import odds  # noqa: E402
from width import Width, crps, inside_90, p_above, rolling_sd  # noqa: E402


@pytest.mark.parametrize("w", [Width("W1", 100), Width("W2", 100, 5), Width("W2", 100, 30)])
@pytest.mark.parametrize("x", [17.0, -40.0, 2.5])
def test_crps_matches_integration(w, x):
    mu, sd = 2.0, 12.0
    if w.method == "W2":
        dist = stats.t(w.df, loc=mu, scale=sd * np.sqrt((w.df - 2) / w.df))
    else:
        dist = stats.norm(mu, sd)
    num = integrate.quad(lambda y: (dist.cdf(y) - (y >= x)) ** 2, -2000, 2000,
                         points=[x], limit=800)[0]
    assert float(crps(x, mu, sd, w)) == pytest.approx(num, rel=1e-5)


def test_rolling_sd_uses_earlier_days_only():
    e = np.r_[np.full(70, 10.0), np.full(70, 20.0)]
    day = np.arange(140)
    r = rolling_sd(e, day, 50, start_sd=99.0)
    assert r[59] == 99.0 and r[60] == 10.0 and r[139] == 20.0
    # same day: a game never sees errors from its own day
    same = rolling_sd(np.full(80, 5.0), np.zeros(80), 50, start_sd=7.0)
    assert (same == 7.0).all()


def test_variance_matched_t_is_wider_in_tails():
    w2, w1 = Width("W2", 100, 5), Width("W1", 100)
    # same variance, so the t's 90% range is a little narrower but its far tail is heavier
    assert inside_90(np.array([19.5]), 0.0, 12.0, w1)[0]
    assert not inside_90(np.array([19.5]), 0.0, 12.0, w2)[0]
    assert p_above(0.0, 12.0, w2, line=30.0) > p_above(0.0, 12.0, w1, line=30.0)


EVENTS = [{"id": "e1", "commence_time": "2026-11-20T19:00:00Z",
           "home_team": "Real Madrid", "away_team": "Olympiacos Piraeus",
           "bookmakers": [{"key": "pinnacle", "markets": [
               {"key": "h2h", "outcomes": [{"name": "Real Madrid", "price": 1.50},
                                           {"name": "Olympiacos Piraeus", "price": 2.70}]},
               {"key": "spreads", "outcomes": [{"name": "Real Madrid", "price": 1.9, "point": -5.5},
                                               {"name": "Olympiacos Piraeus", "price": 1.9,
                                                "point": 5.5}]},
               {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 160.5},
                                              {"name": "Under", "price": 1.9, "point": 160.5}]}]},
               {"key": "other", "markets": [
                   {"key": "h2h", "outcomes": [{"name": "Real Madrid", "price": 1.0},
                                               {"name": "Olympiacos Piraeus", "price": 2.5}]}]}]}]


def test_odds_flatten_view_and_match():
    now = pd.Timestamp("2026-11-19T08:00Z")
    snaps = odds.flatten(EVENTS, "EuroLeague", now)
    assert (snaps["price"] > 1.0).all()  # the 1.0 price is dropped
    view = odds.market_view(snaps).iloc[0]
    assert view["p_home_mkt"] == pytest.approx((1 / 1.5) / (1 / 1.5 + 1 / 2.7))
    assert view["spread_home"] == -5.5 and view["total_line"] == 160.5
    games = pd.DataFrame({"league": ["EuroLeague", "EuroLeague"], "game_id": ["g1", "g2"],
                          "tip_utc": pd.to_datetime(["2026-11-20T19:00Z", "2026-11-20T19:00Z"]),
                          "home_name": ["Real Madrid", "Partizan"],
                          "away_name": ["Olympiacos", "Monaco"]})
    m = odds.match_events(snaps, games)
    assert m["game_id"].tolist() == ["g1"]


def test_odds_due_and_no_key(monkeypatch, tmp_path):
    now = pd.Timestamp("2026-11-19T08:00Z")
    fx = pd.DataFrame({"league": ["NBL"], "tip_utc": [now + pd.Timedelta(hours=20)]})
    assert odds.due("NBL", fx, odds.load(tmp_path / "x.parquet"), now)
    assert not odds.due("EuroLeague", fx, odds.load(tmp_path / "x.parquet"), now)
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    assert odds.run(fx, now, path=tmp_path / "x.parquet") == 0


def test_availability_adjust(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("league,date,club,player,role,status,source\n"
                 "NBL,2026-11-20,Perth Wildcats,A,star,out,Lang\n"
                 "NBL,2026-11-20,Perth Wildcats,B,starter,doubtful,Lang\n"
                 "NBL,2026-11-20,Sydney Kings,C,rotation,out,Lang\n")
    av = availability.load(p)
    dm, dt, n = availability.adjust("NBL", "2026-11-20", "Perth Wildcats", "Sydney Kings", av)
    assert dm == pytest.approx(0.5 - 3.75) and dt == pytest.approx(-0.5 * 4.25) and n == 3
    p.write_text("league,date,club,player,role,status,source\nNBL,2026-11-20,X,A,legend,out,L\n")
    with pytest.raises(ValueError):
        availability.load(p)


def test_blend_pool_and_fit():
    assert blend.pool(0.6, 0.6, 0.3) == pytest.approx(0.6)
    rng = np.random.default_rng(1)
    truth = rng.uniform(0.2, 0.8, 600)
    y = (rng.uniform(size=600) < truth).astype(float)
    market = np.clip(truth + rng.normal(0, 0.02, 600), 0.01, 0.99)
    model = np.clip(truth + rng.normal(0, 0.15, 600), 0.01, 0.99)
    w = blend.fit_weight(model, market, y)
    assert 0.0 <= w <= 0.5  # the sharper source gets most of the weight
