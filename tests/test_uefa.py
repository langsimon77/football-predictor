"""Reader for openfootball's UEFA club competition files (fp.ingest.uefa)."""

from __future__ import annotations

import pandas as pd
import pytest

from fp.ingest import uefa

SAMPLE = """= UEFA Champions League 2023/24

▪ Group, Matchday 1
  Tue Sep 19 2023
    18:45  AC Milan (ITA)          v Newcastle United FC (ENG)  0-0
           BSC Young Boys (SUI)    v RB Leipzig (GER)         1-3 (1-1)
  Wed Sep 20
    21:00  Arsenal FC (ENG)        v PSV (NED)                4-0 (3-0)

▪ Finals, Round of 16
  Tue Mar 12
    21:00  Arsenal FC (ENG)        v FC Porto (POR)           4-2 pen. 1-0 a.e.t. (1-0, 1-0)

▪ Finals, Final
  Sat Jun 1
    21:00  Borussia Dortmund (GER) v Real Madrid CF (ESP)     0-2 (0-0)
           Club A (ESP) v Club B (FRA)
"""


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return uefa.parse(SAMPLE, 2023, "cl")


def test_reads_every_match_and_carries_the_time(frame):
    assert len(frame) == 6
    assert list(frame["home_name"][:2]) == ["AC Milan", "BSC Young Boys"]
    assert frame.loc[1, "away_country"] == "GER"
    # 18:45 Central European Summer Time is 16:45 UTC; the time carries to the next line.
    assert frame.loc[1, "kickoff_utc"] == pd.Timestamp("2023-09-19 16:45", tz="UTC")


def test_group_by_group_files_do_not_jump_a_year():
    text = ("▪ Group A\n  Tue Sep 13 2016\n    20:45  A (SUI) v B (BUL)  1-1 (0-1)\n"
            "  Wed Dec 7\n    20:45  B (BUL) v A (SUI)  0-0\n"
            "▪ Group B\n  Tue Sep 13\n    20:45  C (ESP) v D (ENG)  2-1 (1-1)\n"
            "▪ Final\n  Sat Jun 3\n    20:45  A (SUI) v C (ESP)  1-4 (1-1)\n")
    f = uefa.parse(text, 2016, "cl")
    assert [str(d) for d in f["date"]] == ["2016-09-13", "2016-12-07", "2016-09-13", "2017-06-03"]


def test_covid_season_runs_into_august():
    text = ("▪ Round of 16\n  Tue Feb 18 2020\n    21:00  A (GER) v B (FRA)  2-1 (0-0)\n"
            "  Fri Aug 7\n    21:00  B (FRA) v A (GER)  2-0 (2-0)\n"
            "▪ Quarterfinals\n  Wed Aug 12\n    21:00  B (FRA) v C (ITA)  2-1 (0-1)\n")
    f = uefa.parse(text, 2019, "cl")
    assert [str(d) for d in f["date"]] == ["2020-02-18", "2020-08-07", "2020-08-12"]
    assert f.loc[2, "neutral"]  # 2019/20 quarter-finals in Lisbon


def test_june_qualifiers_open_the_season():
    f = uefa.parse("▪ Preliminary round\n  Tue Jun 25\n    18:00  A (SMR) v B (AND)  0-1 (0-0)\n",
                   2024, "clq")
    assert str(f.loc[0, "date"]) == "2024-06-25"


def test_years_roll_over_in_january(frame):
    assert str(frame.loc[3, "date"]) == "2024-03-12"
    assert str(frame.loc[4, "date"]) == "2024-06-01"


def test_ninety_minute_score_after_extra_time(frame):
    r = frame.loc[3]
    assert (r["home_goals"], r["away_goals"]) == (1, 0)
    assert (r["ht_home_goals"], r["ht_away_goals"]) == (1, 0)
    assert r["extra_time"] and r["penalties"]


def test_half_time_and_goalless_draws(frame):
    assert (frame.loc[0, "ht_home_goals"], frame.loc[0, "ht_away_goals"]) == (0, 0)
    assert (frame.loc[1, "ht_home_goals"], frame.loc[1, "ht_away_goals"]) == (1, 1)


def test_final_is_neutral_and_fixture_without_score_is_kept(frame):
    assert frame.loc[4, "neutral"] and not frame.loc[3, "neutral"]
    assert pd.isna(frame.loc[5, "home_goals"])


@pytest.mark.parametrize("text,want", [
    ("2-3 a.e.t. (1-3, 0-1)", (1, 3, True, False)),
    ("3-2 a.e.t. (3-0, 1-0)", (3, 0, True, False)),
    ("4-3 pen. 1-1 a.e.t. (1-1, 0-1)", (1, 1, True, True)),
    ("1-1 (0-1)", (1, 1, False, False)),
])
def test_score_variants(text, want):
    s = uefa.parse_score(text)
    assert s is not None and (s.home, s.away, s.extra_time, s.penalties) == want


def test_unreadable_match_line_raises():
    with pytest.raises(ValueError):
        uefa.parse("▪ Group A\n  Tue Sep 13 2016\n    20:45  Basel v Ludogorets 1-1\n", 2016, "cl")
