"""Basketball phase B5: the ACB, LBA and ABA parsers, duplicate handling and the daily step's
date-only leagues, on small samples written like the real pages."""
from __future__ import annotations

import importlib
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

from fp import ROOT

sys.path.insert(0, str(ROOT / "basketball"))
more = importlib.import_module("more_leagues")
live = importlib.import_module("live")
ledger_bb = importlib.import_module("ledger_bb")

ACB = """== Jornada 8 ==
{{Partido de baloncesto
 |id     = BUR-BRE
 |date   = {{fecha|14|11|2026}}
 |time   = 18:00
 |teamA  = [[Club Baloncesto San Pablo Burgos|Recoletas Salud Burgos]]
 |scoreA = '''88'''
 |scoreB = 80
 |teamB  = [[Club Baloncesto Breogán|Río Breogán]]
 |Q1 = '''20'''-18
 |Q2 = 22-20
 |Q3 = 24-22
 |Q4 = 22-20
}}
{{Partido de baloncesto
 |date   = {{fecha|21|5|2027}}
 |time   =
 |teamA  = [[Valencia Basket]]
 |scoreA =
 |scoreB =
 |teamB  = [[Real Madrid Baloncesto|Real Madrid]]
}}
"""


def test_acb_boxes():
    a, b = more.parse_acb(ACB, 2026)
    assert a["date"] == date(2026, 11, 14) and a["time_local"] == "18:00"
    assert a["home_key"] == "Club Baloncesto San Pablo Burgos"
    assert a["home_title"] == "Recoletas Salud Burgos"
    assert (a["home_pts"], a["away_pts"]) == (88.0, 80.0)
    assert (a["home_reg"], a["away_reg"]) == (88, 80)
    assert a["section"] == "Round 8"
    assert b["time_local"] is None and b["home_pts"] is None


LBA = """=== Calendario ===
'''1ª giornata'''
|-
| rowspan bgcolor=#f0ffff | 1 ott. || NutriBullet Treviso Basket - UNAHOTELS Reggio Emilia || 58-78
|rowspan=3 bgcolor=#def|1º nov.
|Banco di Sardegna Sassari - APU Old Wild West Udine||[https://legabasket.it/g/1 96-79]
|<del>Pallacanestro Trieste - Trapani Shark</del>||<del>[https://legabasket.it/g/2 87-91]</del>
|bgcolor=#def|26 gen.
|UNA Hotels Reggio Emilia - Openjobmetis Varese || -
== Classifica in divenire ==
"""


def test_lba_calendar():
    rows = more.parse_lba(LBA, 2026)
    assert [r["date"] for r in rows] == [date(2026, 10, 1), date(2026, 11, 1),
                                         date(2026, 11, 1), date(2027, 1, 26)]
    assert rows[0]["home_title"] == "NutriBullet Treviso Basket" and rows[0]["home_pts"] == 58
    assert rows[1]["away_pts"] == 79  # the score inside the link, not the link's numbers
    assert rows[2]["struck"] and not rows[1]["struck"]
    assert rows[3]["home_pts"] is None and rows[3]["section"] == "Round 1"


def test_round_days():
    assert more.round_days("30.9" + chr(0x2014) + "3.10.2022.", 2022) == (
        date(2022, 9, 30), date(2022, 10, 3))
    assert more.round_days("7" + chr(0x2014) + "10.10.2022.", 2022) == (
        date(2022, 10, 7), date(2022, 10, 10))
    assert more.round_days("20" + chr(0x2014) + "22. сеп. 2024.", 2024) == (
        date(2024, 9, 20), date(2024, 9, 22))
    assert more.round_days("30. окт " + chr(0x2014) + " 3. нов. 2025.", 2025) == (
        date(2025, 10, 30), date(2025, 11, 3))
    assert more.round_days("29. јан. " + chr(0x2014) + " 2. феб. 2026.", 2025) == (
        date(2026, 1, 29), date(2026, 2, 2))


EM = chr(0x2014)
ABA = f"""== Први део такмичења ==
=== Група А ===
==== Резултати по колима ====
{{| border=0
|-
| colspan=5 |<div class="center"><span>'''2. коло''', 2{EM}4. окт. 2026.</span></div>
|- align=center
| Борац {EM} '''Широки''' || '''81:87'''
|- align=center
| [[Датотека:golden star.svg|20п]] '''Ц. звезда''' {EM} Крка (25. сеп.) || '''97:78'''
|- align=center
| Игокеа {EM} Будућност || '''{EM}:{EM}'''
|}}
"""


def test_aba_rounds():
    rows = more.parse_aba(ABA, 2026)
    assert len(rows) == 3
    a, b, c = rows
    assert a["date"] == date(2026, 10, 2) and a["phase"] == "a"
    assert a["section"] == "Group A, Round 2 (2 to 4 Oct)"
    assert (a["home_title"], a["away_title"], a["home_pts"]) == ("Борац", "Широки", 81.0)
    assert b["home_title"] == "Ц. звезда" and b["away_title"] == "Крка"  # no star, no date
    assert b["date"] == date(2026, 9, 25)  # played away from its round
    assert c["home_pts"] is None
    assert more.latin("Ц. звезда") == "C. zvezda"


def test_pair_listed_twice_keeps_the_first_id():
    g = pd.DataFrame({"league": "ACB", "season": 2026, "phase": "rs",
                      "date": [date(2027, 3, 1), date(2026, 11, 14), date(2026, 12, 1)],
                      "time_local": "18:00", "game_id": ["ACB_x_b_a", "ACB_x_b_a", "ACB_x_c_a"]})
    out = more.mark_listed_twice(g).set_index("date")
    assert out.loc[date(2026, 11, 14), "game_id"] == "ACB_x_b_a"
    assert out.loc[date(2027, 3, 1), "game_id"] == "ACB_x_b_a_2"
    assert out.loc[date(2027, 3, 1), "suspect"] and not out.loc[date(2026, 11, 14), "suspect"]


SETTINGS = {"LBA": {"elo": {"k": 15, "home": 100, "carry": 1.0, "mov": True,
                            "margin_scale_b": 0.05, "margin_sd": 13.5},
                    "points": {"half_life": 240, "penalty": 10, "sd_home": 10.7,
                               "sd_away": 11.0, "rho": 0.2}}}


def lba_games(now: pd.Timestamp) -> pd.DataFrame:
    rng = np.random.default_rng(4)
    rows = []
    clubs = ["a", "b", "c", "d"]
    for k in range(40):
        day = (now - pd.Timedelta(days=60 - k)).date()
        h, a = rng.choice(clubs, 2, replace=False)
        rows.append({"date": day, "home_id": h, "away_id": a, "played": True,
                     "home_pts": float(80 + rng.integers(0, 20)),
                     "away_pts": float(75 + rng.integers(0, 20)),
                     "tip_utc": pd.Timestamp(day, tz="Europe/Rome").tz_convert("UTC")})
    soon = (now + pd.Timedelta(hours=40)).tz_convert("Europe/Rome").normalize()
    rows.append({"date": soon.date(), "home_id": "a", "away_id": "d", "played": False,
                 "home_pts": np.nan, "away_pts": np.nan, "tip_utc": soon.tz_convert("UTC")})
    g = pd.DataFrame(rows).assign(league="LBA", season=2026, left_out=False, overtime=False,
                                  section="Round 9", date_only=True, suspect=False)
    g["home_title"], g["away_title"] = g["home_id"].str.upper(), g["away_id"].str.upper()
    g["game_id"] = [f"LBA_{i}" for i in range(len(g))]
    return g


def test_date_only_league_locks_but_shows_no_time_and_no_winner(tmp_path):
    now = pd.Timestamp("2026-11-14 08:00", tz="UTC")
    ctx = live.Context(games=lba_games(now), settings=SETTINGS,
                       ledger_path=tmp_path / "p.parquet", results_path=tmp_path / "r.parquet",
                       upcoming_path=tmp_path / "u.parquet", report_path=None)
    new = live.run_once(now, ctx)
    assert len(new) == 1
    row = new.iloc[0]
    flags = json.loads(row["flags"])
    assert "date_only" in flags and "winner_not_shown" in flags
    assert np.isfinite(row["margin_mean"]) and np.isfinite(row["total_mean"])
    ledger_bb.verify_chain(ledger_bb.load(ctx.ledger_path))
    up = pd.read_parquet(ctx.upcoming_path)
    assert up["tip_utc"].isna().all() and up["date_only"].all()  # the stand-in time is hidden
    assert set(up["markets"]) == {"handicap,total"}
