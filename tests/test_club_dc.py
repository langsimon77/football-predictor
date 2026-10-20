"""Champions League model (fp.models.club_dc) and its data (fp.ingest.europe)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fp.ingest import europe
from fp.models import club_dc

T0 = pd.Timestamp("2024-08-01", tz="UTC")


def toy(seed: int = 0) -> tuple[pd.DataFrame, dict[str, str]]:
    """Two leagues of four clubs; league S is stronger; clubs meet across leagues in Europe."""
    rng = np.random.default_rng(seed)
    strength = {"s1": 0.5, "s2": 0.4, "s3": 0.3, "s4": 0.2, "w1": -0.1, "w2": -0.2,
                "w3": -0.3, "w4": -0.4}
    country = {c: ("STR" if c.startswith("s") else "WEA") for c in strength}
    rows, day = [], 0
    clubs = list(strength)
    for _ in range(6):
        for h in clubs:
            for a in clubs:
                same = country[h] == country[a]
                if h == a or (not same and rng.random() > 0.3):
                    continue
                lam = np.exp(0.2 + 0.25 + strength[h] - strength[a] / 2)
                nu = np.exp(0.2 + strength[a] - strength[h] / 2)
                ko = T0 + pd.Timedelta(days=day)
                rows.append({"match_id": f"m{len(rows)}", "competition": "X", "season": 2024,
                             "kind": "domestic" if same else "europe", "date": ko.date(),
                             "kickoff_utc": ko, "result_available_utc": ko + pd.Timedelta(hours=3),
                             "home_id": h, "away_id": a, "home_goals": float(rng.poisson(lam)),
                             "away_goals": float(rng.poisson(nu)), "neutral": False, "round": None})
                day += 1
    return pd.DataFrame(rows), country


def test_fit_finds_the_stronger_league_and_sums_to_one():
    m, country = toy()
    f = club_dc.fit(m, m["result_available_utc"].max() + pd.Timedelta(hours=1), country)
    assert f.converged
    lvl = {c: f.league_attack[c] - f.league_defence[c] for c in f.countries}
    assert lvl["STR"] > lvl["WEA"]
    mk = f.markets("s1", "w4")
    p = np.array([mk["p_home"], mk["p_draw"], mk["p_away"]])
    assert np.isfinite(p).all() and (p >= 0).all() and p.sum() == pytest.approx(1)
    assert mk["p_home"] > mk["p_away"]


def test_neutral_ground_has_no_home_advantage():
    m, country = toy(1)
    f = club_dc.fit(m, m["result_available_utc"].max() + pd.Timedelta(hours=1), country)
    lam_home, nu_home = f.rates("s1", "s2")
    lam_n, nu_n = f.rates("s1", "s2", neutral=True)
    assert lam_n < lam_home and nu_n == pytest.approx(nu_home)


def test_fit_never_uses_a_result_not_yet_known():
    m, country = toy(2)
    cut = m["result_available_utc"].iloc[40]
    f = club_dc.fit(m, cut, country)
    assert f.n_matches == int((m["result_available_utc"] <= cut).sum())


def test_new_club_gets_its_league_level():
    m, country = toy(3)
    country["s9"] = "STR"
    f = club_dc.fit(m, m["result_available_utc"].max() + pd.Timedelta(hours=1), country, ("s9",))
    assert f.attack["s9"] == pytest.approx(f.league_attack["STR"])


def test_domestic_league_wins_over_the_european_country_tag():
    dom = pd.DataFrame({"kind": ["domestic"], "competition": ["F1"], "home_id": ["monaco"],
                        "away_id": ["lyon"]})
    assert club_dc.countries(dom, {"monaco": "MCO"})["monaco"] == "FRA"


def test_alias_table_is_one_id_per_spelling():
    a = pd.read_csv(europe.ALIASES_CSV)
    assert not a.duplicated(["country", "uefa_name"]).any()
    assert a["club_id"].str.match(r"^[a-z0-9_]+$").all()
    assert europe.uefa_id("ESP", "Club Atlético de Madrid") == "atletico_madrid"
    assert europe.uefa_id("GER", "FC Bayern München") == europe.domestic_id("GER", "Bayern Munich")
    assert europe.uefa_id("CRO", "GNK Dinamo Zagreb") == europe.uefa_id("CRO", "Dinamo Zagreb")
    assert europe.domestic_id("ROU", "U Craiova") == europe.domestic_id("ROU", "Univ. Craiova")


def test_season_of():
    assert europe.season_of(pd.Timestamp("2025-07-01")) == 2025
    assert europe.season_of(pd.Timestamp("2026-05-30")) == 2025
