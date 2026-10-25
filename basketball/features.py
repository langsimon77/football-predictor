"""Basketball phase B2: features for the challengers, each built from earlier days only.

Plan: data/audit/preregistration_basketball_b2_2026_10.md, section 1.

    F1 elo_diff              B1 Elo: home rating + home edge - away rating
    F2 pts_margin, pts_total B1 points model: expected margin and total
    F3 rest_home, rest_away  days since the team's previous game in our data (at most 30)
    F4 travel_km             great-circle distance between the two clubs' home cities
    F5 form_home, form_away  the team's margin minus Elo's expected margin, last 5 games
    F6 played_home, played_away  the team's games so far this season

Plus, for the small neural network (C5), each team's last 10 results from its own side:
margin and game total, most recent first, zero where the team has fewer games, and the count.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from models import EloSettings, PointsSettings, _day_groups, elo_run, points_run

from fp import ROOT

CITIES = ROOT / "data" / "manual" / "basketball_club_cities.csv"
REST_CAP = 30
FORM_GAMES = 5
SEQ_GAMES = 10
BASE = ["elo_diff", "pts_margin", "pts_total", "rest_home", "rest_away", "travel_km",
        "form_home", "form_away", "played_home", "played_away"]
SEQ = ([f"h_margin_{i}" for i in range(SEQ_GAMES)] + [f"h_total_{i}" for i in range(SEQ_GAMES)]
       + [f"a_margin_{i}" for i in range(SEQ_GAMES)] + [f"a_total_{i}" for i in range(SEQ_GAMES)]
       + ["h_count", "a_count"])


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in km (Earth radius 6,371 km)."""
    p1, l1, p2, l2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def build_features(games: pd.DataFrame, b1: dict, cities: pd.DataFrame | None = None
                   ) -> pd.DataFrame:
    """`games`: one league's played games sorted by date (as in backtest.league_games);
    `b1`: that league's B1 settings (data/basketball/b1_settings.json)."""
    e, pt = b1["elo"], b1["points"]
    elo = elo_run(games, EloSettings(e["k"], e["home"], e["carry"], e["mov"]))
    pts = points_run(games, PointsSettings(pt["half_life"], pt["penalty"]))
    out = pd.DataFrame(index=games.index)
    out["elo_diff"] = elo["elo_diff"]
    out["pts_margin"] = pts["m_home"] - pts["m_away"]
    out["pts_total"] = pts["m_home"] + pts["m_away"]

    cities = pd.read_csv(CITIES) if cities is None else cities
    loc = cities.set_index("club_title")[["lat", "lon"]]
    h = loc.reindex(games["home_title"]).to_numpy()
    a = loc.reindex(games["away_title"]).to_numpy()
    out["travel_km"] = haversine_km(a[:, 0], a[:, 1], h[:, 0], h[:, 1])

    expected = e["margin_scale_b"] * elo["elo_diff"].to_numpy()
    margin = (games["home_pts"] - games["away_pts"]).to_numpy()
    total = (games["home_pts"] + games["away_pts"]).to_numpy()
    ordinal = np.array([d.toordinal() for d in games["date"]])
    seasons = games["season"].to_numpy()
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()

    last_day: dict[str, int] = {}
    played: dict[tuple[str, int], int] = defaultdict(int)
    history: dict[str, list[tuple[float, float, float]]] = defaultdict(list)  # margin, total, resid
    cols = {c: np.zeros(len(games)) for c in
            ["rest_home", "rest_away", "form_home", "form_away", "played_home", "played_away",
             *SEQ]}
    for idx in _day_groups(games):
        day = ordinal[idx[0]]
        for i in idx:
            for side, team in (("home", home[i]), ("away", away[i])):
                cols[f"rest_{side}"][i] = min(day - last_day.get(team, day - REST_CAP), REST_CAP)
                past = history[team]
                cols[f"form_{side}"][i] = (np.mean([r for _, _, r in past[-FORM_GAMES:]])
                                           if past else 0.0)
                cols[f"played_{side}"][i] = played[(team, seasons[i])]
                tag = "h" if side == "home" else "a"
                recent = past[-SEQ_GAMES:][::-1]
                for k, (m, t, _) in enumerate(recent):
                    cols[f"{tag}_margin_{k}"][i] = m
                    cols[f"{tag}_total_{k}"][i] = t
                cols[f"{tag}_count"][i] = len(recent)
        for i in idx:  # the day's results join the history after the whole day is built
            history[home[i]].append((margin[i], total[i], margin[i] - expected[i]))
            history[away[i]].append((-margin[i], total[i], -(margin[i] - expected[i])))
            for team in (home[i], away[i]):
                last_day[team] = day
                played[(team, seasons[i])] += 1
    for c, v in cols.items():
        out[c] = v
    return out
