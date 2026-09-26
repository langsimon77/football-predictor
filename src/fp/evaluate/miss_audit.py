"""Post-match miss audit (spec S5.6 step 4, with PRD item 12's fix).

Each week, the five results per league that the published home, draw, away
forecast found most surprising (-ln of the chance it gave the result) get their
objective causes tagged from data, never from judgement:

- red card: a player was sent off;
- team news unanswered: the Question Queue asked and got no answer;
- team news applied: your answers moved the forecast;
- upset: the result was given under 15%.

Penalties and changed line-ups have no free data source, so they cannot be
tagged. Model error is judged over many matches (calibration, drift), never from
one. A fix is proposed only for a cause we control (unanswered news) that shows
up among the misses three weeks running, more often than among all matches.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fp.evaluate import metrics

TOP = 5
UPSET = 0.15
CONTROLLABLE = "team news unanswered"
WEEKS_RUNNING = 3


def _json_list(value: object) -> list:
    return json.loads(value) if isinstance(value, str) and value else []


def causes(row: pd.Series) -> list[str]:
    tags = []
    if (row.get("home_reds") or 0) + (row.get("away_reds") or 0) > 0:
        tags.append("red card")
    if _json_list(row.get("unanswered_questions")):
        tags.append(CONTROLLABLE)
    adj = _json_list(row.get("news_adjustments"))
    if any(abs(a["scale_home_goals"] - 1) > 0.004 or abs(a["scale_away_goals"] - 1) > 0.004
           for a in adj):
        tags.append("team news applied")
    if row["chance_given"] < UPSET:
        tags.append("upset")
    return tags


def audit(week: pd.DataFrame, week_label: str) -> pd.DataFrame:
    """Top misses per league for one week of scored primary forecasts."""
    if week.empty:
        return pd.DataFrame()
    week = week.copy()
    p = week[["p_home", "p_draw", "p_away"]].to_numpy(float)
    y = week["outcome"].to_numpy(int)
    week["chance_given"] = p[np.arange(len(y)), y]
    week["surprise"] = metrics.log_loss(p, y)
    week["tags"] = week.apply(lambda r: ", ".join(causes(r)) or "none tagged", axis=1)
    week["unanswered"] = week.apply(lambda r: bool(_json_list(r.get("unanswered_questions"))),
                                    axis=1)
    top = (week.sort_values("surprise", ascending=False).groupby("league").head(TOP)
           .assign(week=week_label, all_unanswered_share=week["unanswered"].mean()))
    return top[["week", "league", "match_id", "home_id", "away_id", "home_goals", "away_goals",
                "chance_given", "surprise", "tags", "all_unanswered_share"]]


def proposal(history: pd.DataFrame) -> str | None:
    """A drafted fix when unanswered news keeps showing up among the misses."""
    if history.empty:
        return None
    weeks = sorted(history["week"].unique())[-WEEKS_RUNNING:]
    if len(weeks) < WEEKS_RUNNING:
        return None
    for w in weeks:
        g = history[history["week"] == w]
        share = g["tags"].str.contains(CONTROLLABLE).mean()
        if not share > float(g["all_unanswered_share"].iloc[0]):
            return None
    return (f"For {WEEKS_RUNNING} weeks running, matches with unanswered team-news questions "
            "were over-represented among the biggest misses. Proposed: ask earlier (two runs "
            "before the lock) or cut the daily question count so each gets answered. Awaiting "
            "Lang.")
