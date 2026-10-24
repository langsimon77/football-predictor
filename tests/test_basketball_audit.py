"""basketball/audit_sample.py: reading games from Wikipedia wikitext (phase B0)."""
from __future__ import annotations

import importlib
import sys
from collections import Counter

from fp import ROOT

sys.path.insert(0, str(ROOT / "basketball"))
audit = importlib.import_module("audit_sample")

DASH = chr(0x2013)  # Wikipedia's score separator; the repository bans the character itself

NBL_BOX = f"""{{{{basketballbox collapsible|bg=#eee
 | date = 19 September 2026
 | time = 19:30
 | teamA = [[2026{DASH}27 Melbourne United season|Melbourne United]]
 | scoreA = 95
 | scoreB = '''97'''
 | teamB = '''[[2026{DASH}27 Adelaide 36ers season|Adelaide 36ers]]'''
 | Q1 = 23{DASH}'''25'''
}}}}"""

EL_BOX = """{{basketballbox collapsible|id="Hapoel v Barcelona"
 | date = 30 September 2025 | time = 18:00
 | teamA = '''[[Hapoel Tel Aviv B.C.|Hapoel IBI Tel Aviv]] {{#invoke:bka|icon|ISR}}'''
 | scoreA = '''103'''
 | teamB = {{#invoke:bka|icon|ESP}} [[FC Barcelona Bàsquet|Barcelona]] | scoreB = 87
}}"""

FUTURE_BOX = """{{basketballbox collapsible
 | date = 7 November 2026 | time = 17:30
 | teamA = [[Sydney Kings]] | scoreA = | teamB = [[Perth Wildcats]] | scoreB =
}}"""


def test_boxes_read_date_time_teams_and_scores():
    nbl, el = audit.boxes(NBL_BOX + "\n" + EL_BOX)
    assert nbl == {"date": "2026-09-19", "time": "19:30", "home": "Melbourne United",
                   "away": "Adelaide 36ers", "home_pts": 95, "away_pts": 97}
    assert (el["home"], el["away"], el["home_pts"], el["away_pts"]) == (
        "Hapoel IBI Tel Aviv", "Barcelona", 103, 87)
    assert el["date"] == "2025-09-30" and el["time"] == "18:00"


def test_box_summary_counts_played_and_timed_future_games():
    games = audit.boxes(NBL_BOX + FUTURE_BOX)
    s = audit.box_summary(games, today="2026-10-24")
    assert (s["games"], s["played"], s["future"], s["future_with_time"]) == (2, 1, 1, 1)
    assert s["last_future_with_time"] == "2026-11-07"


def test_params_split_outside_links_and_templates():
    p = audit.params(" a = [[x|y]] | b = {{t|1|2}} | c = 3")
    assert p == {"a": "[[x|y]]", "b": "{{t|1|2}}", "c": "3"}


def nba_log(*rows):
    out = "{{NBA game log start|Team}}"
    for date, opp, gid, pf, pa in rows:
        game = f"{{{{NBA game|id={gid}|pf={pf}|pa={pa}}}}}" if pf is not None else \
            f"{{{{NBA game|id={gid}}}}}"
        out += f"\n|-{{{{Game-won}}}}\n| 1\n| {date}\n| {opp}\n| {game}\n| x"
    return out


def test_nba_rows_read_kind_side_and_scores():
    rows = audit.nba_rows(nba_log(("October 8", "@ [[A|Memphis]]", "0012500038", 121, 103),
                                  ("October 22", "[[B|Cleveland]]", "0022500005", 110, 99),
                                  ("October 24", "@ [[C|Miami]]", "0022500020", None, None)))
    assert [r["kind"] for r in rows] == ["preseason", "regular", "regular"]
    assert [r["away"] for r in rows] == [True, False, True]
    assert rows[1]["pf"] == 110 and rows[2]["pf"] is None
    assert rows[1]["date"] == "October 22"


def test_nba_check_needs_both_logs_with_mirrored_scores():
    home = audit.nba_rows(nba_log(("October 22", "[[B|Celtics]]", "0022500005", 110, 99),
                                  ("October 23", "[[B|Celtics]]", "0022500006", 100, 90)))
    away = audit.nba_rows(nba_log(("October 22", "@ [[A|Knicks]]", "0022500005", 99, 110),
                                  ("October 23", "@ [[A|Knicks]]", "0022500006", 91, 100),
                                  ("October 25", "@ [[C|Heat]]", "0022500007", 80, 70)))
    check = audit.nba_check({"Knicks": home, "Celtics": away})
    assert check["regular_played"] == 3
    assert check["played_in_both_logs"] == 2
    assert check["both_logs_agree"] == 1          # 0022500006 disagrees: 100-90 against 91-100
    assert check["played_in_one_log_only"] == 1   # 0022500007: the Heat log is missing


def test_grid_scores_read_linked_and_bold_results():
    text = (f"| match_JOV_BAR=[[Catalan basketball derby|84{DASH}72]]\n"
            f"| match_JOV_GIR=71{DASH}74\n| match_BAR_JOV='''90'''{DASH}80\n| match_X_Y=")
    assert audit.grid_scores(text) == Counter({(84, 72): 1, (71, 74): 1, (90, 80): 1})
