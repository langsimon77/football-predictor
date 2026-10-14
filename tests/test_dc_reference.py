"""Reference Dixon-Coles predictor (fp.models.dc_reference), Lang's request of 14 Oct 2026."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from fp.models import dc_reference as ref

T0 = pd.Timestamp("2025-01-01", tz="UTC")


def league(n_teams: int = 6, rounds: int = 4, seed: int = 0) -> pd.DataFrame:
    """A double round robin repeated `rounds` times, goals from known team strengths."""
    rng = np.random.default_rng(seed)
    teams = [f"t{i}" for i in range(n_teams)]
    attack = np.linspace(0.6, 1.4, n_teams)
    defence = np.linspace(-0.6, -1.4, n_teams)
    rows, day = [], 0
    for _ in range(rounds):
        for h in range(n_teams):
            for a in range(n_teams):
                if h == a:
                    continue
                lam = np.exp(attack[h] + defence[a] + 0.25)
                mu = np.exp(attack[a] + defence[h])
                ko = T0 + pd.Timedelta(days=day)
                rows.append({"home_id": teams[h], "away_id": teams[a],
                             "home_goals": int(rng.poisson(lam)),
                             "away_goals": int(rng.poisson(mu)), "kickoff_utc": ko,
                             "result_available_utc": ko + pd.Timedelta(hours=3)})
                day += 1
    return pd.DataFrame(rows)


def test_adapter_maps_to_the_reference_schema():
    m = league()
    as_of = m["kickoff_utc"].iloc[10] + pd.Timedelta(hours=4)
    fr = ref.to_reference_frame(m, as_of, window_days=None)
    assert list(fr.columns) == ref.REFERENCE_COLUMNS
    assert len(fr) == 11  # matches 0..10 are known; match 11 kicks off later
    assert fr["HomeTeam"].iloc[0] == "t0" and fr["FTHG"].iloc[0] == m["home_goals"].iloc[0]
    assert fr["time_diff"].min() == 0 and fr["time_diff"].max() == 10  # days before the latest
    assert fr["time_diff"].iloc[0] == 10


def test_adapter_keeps_no_future_result_and_drops_missing_goals():
    m = league()
    m.loc[3, ["home_goals", "away_goals"]] = np.nan
    as_of = m["kickoff_utc"].iloc[20]  # match 20 kicked off, but its result is not known
    fr = ref.to_reference_frame(m, as_of, window_days=None)
    assert len(fr) == 19  # 0..19 known, minus the one without goals
    with pytest.raises(ValueError):
        ref.to_reference_frame(m.drop(columns="result_available_utc"), as_of)


@pytest.mark.parametrize("n_teams", [6, 24])
def test_constraint_uses_the_actual_team_count(n_teams):
    m = league(n_teams=n_teams, rounds=2 if n_teams > 20 else 6)
    fit = ref.fit(ref.to_reference_frame(m, m["result_available_utc"].max(), None), xi=0.0)
    assert len(fit.teams) == n_teams
    assert sum(fit.attack.values()) == pytest.approx(n_teams, abs=1e-6)


def test_fit_recovers_the_order_of_team_strength():
    m = league(n_teams=6, rounds=12, seed=1)
    fit = ref.fit(ref.to_reference_frame(m, m["result_available_utc"].max(), None), xi=0.0)
    attack = [fit.attack[f"t{i}"] for i in range(6)]
    assert attack[-1] > attack[0]
    assert fit.home_adv == pytest.approx(0.25, abs=0.15)
    assert ref.RHO_BOUNDS[0] <= fit.rho <= ref.RHO_BOUNDS[1]


def test_failed_optimisation_raises_instead_of_returning_parameters():
    m = league()
    fr = ref.to_reference_frame(m, m["result_available_utc"].max(), None)
    with pytest.raises(ref.DCReferenceFitError):
        ref.fit(fr, maxiter=1)
    with pytest.raises(ref.DCReferenceFitError):
        ref.fit(fr.iloc[0:0])
    bad = fr.copy()
    bad.loc[0, "FTHG"] = np.nan
    with pytest.raises(ValueError):
        ref.fit(bad)


def known_fit(lam: float, mu: float, rho: float = 0.0) -> ref.RefFit:
    return ref.RefFit(teams=["h", "a"], attack={"h": np.log(lam), "a": np.log(mu)},
                      defence={"h": 0.0, "a": 0.0}, rho=rho, home_adv=0.0, xi=0.0,
                      n_matches=0, iterations=0)


def test_home_draw_away_come_from_the_right_parts_of_the_matrix():
    fit = known_fit(2.0, 0.5)
    out = fit.predict("h", "a")
    g = np.arange(60)
    ph, pa = poisson.pmf(g, 2.0), poisson.pmf(g, 0.5)
    joint = np.outer(ph, pa)
    assert out["p_home"] == pytest.approx(np.tril(joint, -1).sum(), abs=1e-4)
    assert out["p_draw"] == pytest.approx(np.trace(joint), abs=1e-4)
    assert out["p_away"] == pytest.approx(np.triu(joint, 1).sum(), abs=1e-4)
    assert out["p_home"] > out["p_away"]
    matrix, omitted = fit.score_matrix("h", "a")
    assert matrix[3, 0] > matrix[0, 3]  # rows are home goals
    assert omitted >= 0 and matrix.sum() == pytest.approx(1)


@pytest.mark.parametrize("rho", [-0.2, 0.0, 0.2])
def test_probabilities_are_finite_nonnegative_and_sum_to_one(rho):
    for lam, mu in ((0.2, 0.2), (1.4, 1.1), (4.5, 0.3)):
        out = known_fit(lam, mu, rho).predict("h", "a")
        p = np.array([out["p_home"], out["p_draw"], out["p_away"]])
        assert np.isfinite(p).all() and (p >= 0).all()
        assert p.sum() == pytest.approx(1)


def test_omitted_mass_is_reported_and_absurd_rates_are_refused():
    _, omitted = known_fit(3.5, 3.0).score_matrix("h", "a")
    assert 0 < omitted < ref.MAX_OMITTED
    with pytest.raises(ref.InvalidForecastError):
        known_fit(9.0, 1.0).score_matrix("h", "a")


def test_negative_correction_is_refused():
    with pytest.raises(ref.InvalidForecastError):
        known_fit(4.0, 3.0, rho=0.2).score_matrix("h", "a")  # 1 - lam * mu * rho < 0


def test_unseen_team_raises():
    with pytest.raises(ref.UnseenTeamError):
        known_fit(1.0, 1.0).predict("h", "promoted_club")


def test_blend_is_valid_and_falls_back_where_the_reference_has_no_forecast():
    existing = np.array([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]])
    reference = np.array([[0.7, 0.2, 0.1], [np.nan, np.nan, np.nan]])
    out = ref.blend(existing, reference, 0.25)
    assert out[0] == pytest.approx(0.25 * existing[0] + 0.75 * reference[0])
    assert out[1] == pytest.approx(existing[1])
    assert np.allclose(out.sum(axis=1), 1) and (out >= 0).all()
    with pytest.raises(ValueError):
        ref.blend(existing, np.array([[0.9, 0.3, 0.2], [0.2, 0.3, 0.5]]), 0.5)


def test_walk_forward_never_trains_on_a_result_after_the_lock():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import compare_dc_reference as compare

    m = league(n_teams=6, rounds=4).assign(league="EPL", season=2024,
                                           match_id=lambda f: [f"m{i}" for i in range(len(f))])
    out = compare.walk_forward(m, "EPL", (2024,), xi=0.0018)
    assert len(out) == len(m)
    assert (out["source_max_utc"].isna() | (out["source_max_utc"] <= out["lock_utc"])).all()
    # The first matches have no history, so no forecast, and say why.
    assert set(out["status"]) <= {"ok", "unseen_team", "fit_failed", "invalid_matrix"}
    assert out.loc[out["status"] == "ok", ["ref_home", "ref_draw", "ref_away"]].notna().all().all()
