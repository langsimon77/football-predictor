"""The new-methods test (fp.research and scripts/backtest_methods.py)."""
from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from fp import ROOT
from fp.features.ml_features import FEATURES
from fp.research import form, methods, neural, sequences

T0 = pd.Timestamp("2018-08-01", tz="UTC")


def day(n: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(days=n)


def test_histories_read_only_results_known_at_the_lock():
    clubs = pd.DataFrame({"team": ["a"] * 3, "result_available_utc": [day(1), day(8), day(15)],
                          **{c: [1.0, 2.0, 3.0] for c in sequences.SEQ_COLS}})
    target = pd.DataFrame({"home_id": ["a"], "away_id": ["b"], "lock_utc": [day(10)]})
    values, mask = sequences.histories(target, clubs, length=4)
    assert mask[0, 0].tolist() == [0, 0, 1, 1]         # two known matches, most recent last
    assert values[0, 0, -1, 0] == 2.0                   # the day-15 result is not read
    assert mask[0, 1].sum() == 0                        # club b has no history


def test_club_matches_rest_days_and_sides():
    rows = []
    for i, (h, a) in enumerate([("a", "b"), ("b", "a"), ("a", "b")]):
        rows.append({"match_id": f"m{i}", "league": "EPL", "season": 2018, "home_id": h,
                     "away_id": a, "kickoff_utc": day(3 * i), "result_available_utc":
                     day(3 * i) + pd.Timedelta(hours=3), "home_goals": 2, "away_goals": 1,
                     "home_shots": 10, "away_shots": 8, "home_sot": 4, "away_sot": 3,
                     "home_corners": 5, "away_corners": 4})
    clubs = sequences.club_matches(pd.DataFrame(rows))
    a = clubs[clubs["team"] == "a"].reset_index(drop=True)
    assert a["rest_days"].tolist() == [14.0, 3.0, 3.0]  # first match capped at 14
    assert a["is_home"].tolist() == [1.0, 0.0, 1.0]
    assert a.loc[1, "goals_for"] == 1 and a.loc[1, "goals_against"] == 2
    assert a.loc[0, "opp_elo"] == 1500.0                # everyone starts at 1500


def synthetic_rows(n: int, seed: int = 0) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    outcome = np.where(x > 0.4, 0, np.where(x < -0.4, 2, 1))
    rows = pd.DataFrame({"f1": x, "f2": rng.normal(size=n), "outcome": outcome,
                         "kickoff_utc": [day(i) for i in range(n)]})
    seq = rng.normal(size=(n, 2, 5, len(sequences.SEQ_COLS))).astype(np.float32)
    mask = np.ones((n, 2, 5), dtype=np.float32)
    return rows, seq, mask


@pytest.mark.parametrize("kind", ["lstm", "transformer"])
def test_networks_learn_a_simple_pattern(kind, monkeypatch):
    monkeypatch.setattr(neural, "SEEDS", (1,))  # one seed keeps the test quick
    rows, seq, mask = synthetic_rows(2200)
    net = neural.SeqNet(kind, {"size": 16, "length": 5}, ["f1", "f2"]).fit(
        rows[:2000], seq[:2000], mask[:2000])
    p = net.predict(rows[2000:], seq[2000:], mask[2000:])
    assert np.allclose(p.sum(1), 1, atol=1e-5)
    loss = -np.log(p[np.arange(200), rows["outcome"].to_numpy()[2000:]]).mean()
    assert loss < 0.7  # one third each would score 1.10


def test_arima_forecast_ignores_results_after_the_lock():
    pytest.importorskip("statsmodels")
    rng = np.random.default_rng(1)
    values = np.cumsum(rng.normal(size=40)) * 0.1 + 1.5
    known = np.array([np.datetime64("2018-01-01") + np.timedelta64(i, "D") for i in range(40)])
    lock = known[32]
    first = form._arima(known, values, known[30], np.array([lock]))
    changed = values.copy()
    changed[33:] += 50.0
    assert np.isfinite(first[0])
    assert form._arima(known, changed, known[30], np.array([lock]))[0] == first[0]
    short = form._arima(known[:10], values[:10], known[9], np.array([known[9]]))
    assert np.isnan(short[0])  # fewer than 20 matches: no forecast


def test_a_broken_arima_fit_is_not_usable():
    """Amendment 1, item 7: the West Ham case, a tiny AIC from a broken fit."""
    from types import SimpleNamespace
    train = np.full(38, 1.24) + np.random.default_rng(5).normal(0, 1, 38)
    good = SimpleNamespace(aic=110.7, mle_retvals={"converged": True}, arroots=np.array([]),
                           maroots=np.array([]), params=np.array([1.24, 0.97]))
    broken = SimpleNamespace(aic=10.0, mle_retvals={"converged": True},
                             arroots=np.array([1.0, 1.0]), maroots=np.array([1.0]),
                             params=np.array([-390.9, 2.0, -1.0, -1.0, 1.29e6]))
    assert form.usable(good, train)
    assert not form.usable(broken, train)
    assert not form.usable(SimpleNamespace(**{**good.__dict__, "mle_retvals":
                                              {"converged": False}}), train)


def test_walk_forward_refits_monthly_on_known_results():
    rng = np.random.default_rng(2)
    n = 400
    rows = pd.DataFrame({c: rng.normal(size=n) for c in [*FEATURES, *form.columns("arima")]})
    rows["kickoff_utc"] = [day(2 * i) for i in range(n)]
    rows["lock_utc"] = rows["kickoff_utc"] - pd.Timedelta(days=1)
    rows["result_available_utc"] = rows["kickoff_utc"] + pd.Timedelta(hours=3)
    rows["season"] = np.where(rows["kickoff_utc"] < day(600), 2018, 2019)
    rows["outcome"] = rng.integers(0, 3, n)
    rows["match_id"] = [f"m{i}" for i in range(n)]
    rows["league"] = "EPL"
    data = methods.Prepared(rows, np.zeros((n, 2, 10, 11), np.float32),
                            np.zeros((n, 2, 10), np.float32))
    preds = methods.walk_forward("arima_multinomial", {"C": 0.1}, data, (2019,))
    assert len(preds) == (rows["season"] == 2019).sum()
    assert (pd.to_datetime(preds["refit_utc"]) <= pd.to_datetime(preds["lock_utc"])).all()
    assert preds["n_train"].is_monotonic_increasing
    assert np.allclose(preds[["p_home", "p_draw", "p_away"]].sum(axis=1), 1)


def scorer():
    spec = importlib.util.spec_from_file_location("backtest_methods",
                                                  ROOT / "scripts" / "backtest_methods.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interval_is_wider_at_99_than_95():
    bm = scorer()
    diff = np.random.default_rng(3).normal(-0.01, 0.2, 2000)
    lo95, hi95 = bm.interval(diff, 0.95)
    lo99, hi99 = bm.interval(diff, 0.99)
    assert lo99 < lo95 < hi95 < hi99
    assert bm.interval(diff, 0.99) == (lo99, hi99)  # same seed, same answer


def test_checks_pass_a_clearly_better_method_and_fail_noise():
    bm = scorer()
    rng = np.random.default_rng(4)
    n = 4000
    frame = pd.DataFrame({"league": np.where(np.arange(n) % 2, "EPL", "LaLiga"),
                          "season": np.repeat([2021, 2022, 2023, 2024, 2025], n // 5)})
    truth = rng.dirichlet([4, 2.5, 3], n)
    frame["outcome"] = [rng.choice(3, p=p) for p in truth]
    noisy = 0.5 * truth + 0.5 * rng.dirichlet([4, 2.5, 3], n)
    names = ["published", *bm.CURRENT, *bm.NEW_FILES]
    for name in names:
        p = truth if name == "lightgbm" else noisy  # N1 knows the true chances
        for i, k in enumerate(bm.OUTCOMES):
            frame[f"{name}_{k}"] = p[:, i]
    chosen = bm.build_forecasts(frame)
    res = bm.checks(frame)
    verdict = {v["method"]: v for v in res["verdicts"]}
    assert verdict["N1"]["A1_pass"]
    assert not verdict["N2"]["A1_pass"]  # identical to the published forecast
    assert chosen["n6"]["EPL"]["chosen"] == "N1"
