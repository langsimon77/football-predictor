"""Team news and the Question Queue (Phase 5)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fp.models import dixon_coles as dc
from fp.news import github, impact, managers, queue
from fp.news.impact import TeamNews

NOW = pd.Timestamp("2026-10-07 04:41", tz="UTC")
NAMES = {"arsenal": "Arsenal", "leeds": "Leeds", "malaga": "Málaga", "espanyol": "Espanyol"}


def question(match_id="EPL_2627_arsenal_leeds", shift=0.03):
    home, away = ("arsenal", "leeds") if "arsenal" in match_id else ("malaga", "espanyol")
    league = "EPL" if match_id.startswith("EPL") else "LaLiga"
    return queue.TeamNewsQuestion(match_id, league, pd.Timestamp("2026-10-10 11:30", tz="UTC"),
                                  home, away, shift)


def tick(body: str, *markers: str) -> str:
    """Tick the checkboxes carrying these markers, as Lang would on GitHub."""
    return "\n".join(line.replace("- [ ]", "- [x]")
                     if any(f"fp:{m} -->" in line for m in markers) else line
                     for line in body.splitlines())


# ---------------------------------------------------------------- impact

def test_no_news_changes_nothing():
    assert impact.scales(None, None) == (1.0, 1.0, False)
    assert impact.scales(TeamNews("dont_know"), TeamNews("unanswered")) == (1.0, 1.0, False)


def test_starters_and_threat_move_both_rates():
    home, away, capped = impact.scales(TeamNews("answered", 2, True), None)
    assert home == pytest.approx(1 - 2 * impact.STARTER_ATTACK - impact.THREAT_ATTACK)
    assert away == pytest.approx(1 + 2 * impact.STARTER_CONCEDE)
    assert not capped


def test_every_answer_stays_within_the_cap():
    worst = TeamNews("answered", 3, True)
    for h in (None, worst, TeamNews("answered", 0, False)):
        for a in (None, worst):
            hs, as_, _ = impact.scales(h, a)
            assert 1 - impact.CAP - 1e-12 <= hs <= 1 + impact.CAP + 1e-12
            assert 1 - impact.CAP - 1e-12 <= as_ <= 1 + impact.CAP + 1e-12
    hs, _, capped = impact.scales(worst, None)
    assert hs == pytest.approx(1 - impact.CAP) and capped


# ---------------------------------------------------------------- queue

def test_render_and_read_back():
    title, body = queue.render([question()], [], NAMES, NOW)
    assert title == "Questions for Lang: Wed 07 Oct 2026"
    assert "Arsenal v Leeds (EPL), Sat 10 Oct, 13:30 Juba (11:30 UTC)" in body
    body = tick(body, "EPL_2627_arsenal_leeds:home:2", "EPL_2627_arsenal_leeds:home:threat",
                "EPL_2627_arsenal_leeds:away:0")
    news, managers_ = queue.answers(body)
    assert news["EPL_2627_arsenal_leeds"]["home"] == TeamNews("answered", 2, True)
    assert news["EPL_2627_arsenal_leeds"]["away"] == TeamNews("answered", 0, False)
    assert managers_ == {}


def test_untouched_question_is_unanswered_and_still_counts_as_asked():
    _, body = queue.render([question()], [], NAMES, NOW)
    news, _ = queue.answers(body)
    assert news["EPL_2627_arsenal_leeds"]["home"].status == "unanswered"


@pytest.mark.parametrize("options, expected", [
    ({"1", "2"}, TeamNews("dont_know")),              # contradictory
    ({"unknown", "1"}, TeamNews("dont_know")),
    ({"threat"}, TeamNews("answered", 1, True)),      # threat alone counts as one out
    ({"0", "threat"}, TeamNews("answered", 1, True)),
    ({"3"}, TeamNews("answered", 3, False)),
])
def test_tick_rules(options, expected):
    assert queue.team_news(options) == expected


def test_manager_question_round_trip():
    mq = queue.ManagerQuestion("arsenal", "New Coach", "Mikel Arteta", NOW)
    _, body = queue.render([], [mq], NAMES, NOW)
    news, answers = queue.answers(tick(body, "manager:arsenal:no"))
    assert news == {} and answers == {"arsenal": "no"}


def test_questions_are_for_matches_locking_at_the_next_run():
    fixtures = pd.DataFrame({
        "match_id": ["locks_now", "locks_next_run", "later", "asked", "no_time"],
        "kickoff_utc": [NOW + pd.Timedelta(hours=h) for h in (30, 60, 80, 60, 60)],
        "time_confirmed": [True, True, True, True, False],
    })
    got = queue.to_ask(fixtures, NOW, already={"asked"})
    assert list(got["match_id"]) == ["locks_next_run"]


def test_ranking_prefers_matches_where_news_moves_the_forecast_more():
    fit = dc.DCFit(teams=["a", "b", "c", "d"], mu=0.1, home_adv=0.25, rho=-0.05,
                   attack={"a": 0.0, "b": 0.0, "c": 0.6, "d": -0.6},
                   defence={"a": 0.0, "b": 0.0, "c": -0.6, "d": 0.6},
                   n_matches=100, converged=True)
    window = pd.DataFrame({"match_id": ["even", "mismatch"], "league": ["EPL", "EPL"],
                           "kickoff_utc": [NOW, NOW], "home_id": ["a", "c"],
                           "away_id": ["b", "d"]})
    ranked = queue.rank(window, {"EPL": fit})
    assert [q.match_id for q in ranked] == ["even", "mismatch"]
    assert all(0 < q.shift < 0.1 for q in ranked)


# ---------------------------------------------------------------- trust

def test_only_bot_or_owner_issues_and_edits_are_trusted():
    assert github.trusted("github-actions[bot]", ["langsimon77", "github-actions"], "langsimon77")
    assert not github.trusted("stranger", [], "langsimon77")
    assert not github.trusted("github-actions[bot]", ["langsimon77", "stranger"], "langsimon77")


# ---------------------------------------------------------------- managers

def test_infobox_cleaning():
    text = ("{{Infobox football club\n| clubname = X\n| manager = {{nowrap|[[Mikel Arteta]]}}"
            "<ref>{{cite web|url=x}}</ref>\n| league = y\n}}")
    assert managers.from_wikitext(text) == "Mikel Arteta"
    assert managers.from_wikitext("| head coach = [[Hansi Flick|Flick]] (interim)") == \
        "Flick (interim)"
    assert managers.from_wikitext("| ground = Emirates") is None


def test_manager_log_seed_change_answer_and_flag():
    log = pd.DataFrame(columns=managers.COLUMNS)
    log, changes = managers.observe(log, {"arsenal": "A"}, NOW)
    assert changes == [] and managers.recent_changes(log, NOW) == set()
    later = NOW + pd.Timedelta(days=3)
    log, changes = managers.observe(log, {"arsenal": "B"}, later)
    assert changes == [("arsenal", "A", "B")]
    assert managers.recent_changes(log, later) == {"arsenal"}
    assert managers.recent_changes(log, later + pd.Timedelta(days=31)) == set()
    rejected = managers.apply_answers(log, {"arsenal": "no"})
    assert managers.recent_changes(rejected, later) == set()
    again, changes = managers.observe(rejected, {"arsenal": "B"}, later + pd.Timedelta(days=1))
    assert changes == []  # a rejected name is not asked about again


def test_manager_log_round_trip(tmp_path):
    log, _ = managers.observe(pd.DataFrame(columns=managers.COLUMNS), {"leeds": "Farke"}, NOW)
    managers.save(log, tmp_path / "m.csv")
    back = managers.load(tmp_path / "m.csv")
    assert back.loc[0, "manager"] == "Farke" and back.loc[0, "first_seen_utc"] == NOW


# ---------------------------------------------------------------- record

def test_adjustment_record_is_json_ready():
    rec = impact.record(TeamNews("answered", 1, False), TeamNews("unanswered"), "Issue #3")
    assert json.loads(json.dumps(rec))["scale_home_goals"] == pytest.approx(
        1 - impact.STARTER_ATTACK)
    assert np.isclose(rec["scale_away_goals"], 1 + impact.STARTER_CONCEDE)
