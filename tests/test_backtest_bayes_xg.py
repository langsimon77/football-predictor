"""The --xg flag reaches BayesParams (pre-registration step 2)."""

import pandas as pd
import pytest

from fp.evaluate import backtest_bayes


def _run(monkeypatch, tmp_path, extra):
    pd.DataFrame({"a": [1]}).to_parquet(tmp_path / "matches.parquet")
    pd.DataFrame({"a": [1]}).to_parquet(tmp_path / "second_tier.parquet")
    seen = {}

    def fake_predict(matches, second_tier, league, seasons, params, until=None):
        seen["params"] = params
        return pd.DataFrame({"x": [1]}), pd.DataFrame({"ok": [True]})

    monkeypatch.setattr(backtest_bayes, "processed_dir", lambda league: tmp_path)
    monkeypatch.setattr(backtest_bayes, "predict_league", fake_predict)
    out = tmp_path / "p.parquet"
    assert backtest_bayes.main(["EPL", "2026", "--out", str(out), *extra]) == 0
    return seen["params"]


def test_xg_flag_reaches_params(monkeypatch, tmp_path):
    params = _run(monkeypatch, tmp_path,
                  ["--sot", "--sampler", "numpyro", "--xg", "joint"])
    assert params.xg_mode == "joint"
    assert params.use_sot


def test_xg_default_is_none(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, []).xg_mode == "none"


def test_xg_rejects_unknown_value(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        _run(monkeypatch, tmp_path, ["--xg", "bogus"])
