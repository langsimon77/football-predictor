"""The top drivers of a forecast, in plain English (spec S9, page 2).

Each candidate statement gets a strength between 0 and 1 (how far from ordinary
it is); the strongest five are shown, with team news always first. Ratings come
from the Bayesian posterior means: attack (goals scored) and defence (goals
conceded, lower is better).
"""

from __future__ import annotations

import numpy as np

from fp.models.bayes_dc import Posterior


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _rank(values: np.ndarray, i: int, best_high: bool, among: np.ndarray) -> int:
    """Rank of club i (1 = best) among the clubs in `among`."""
    pool = values[among]
    better = (pool > values[i]) if best_high else (pool < values[i])
    return int(better.sum()) + 1


def drivers(post: Posterior, home: str, away: str, names: dict[str, str], league: str,
            elo_gap: float | None = None, news: dict | None = None,
            promoted: set[str] | None = None, manager_change: set[str] | None = None,
            current: set[str] | None = None, top: int = 5) -> list[str]:
    """`current`: this season's clubs in the league. The model also rates clubs
    relegated in recent seasons; ranks count only this season's clubs."""
    att, dfn = post.att.mean(axis=0), post.def_.mean(axis=0)
    among = np.array([i for i, t in enumerate(post.teams) if current is None or t in current])
    n = len(among)
    league_name = "La Liga" if league == "LaLiga" else league
    found: list[tuple[float, str]] = []
    for team in (home, away):
        i = post.index(team)
        name = names.get(team, team)
        r = _rank(att, i, best_high=True, among=among)
        found.append((abs(n + 1 - 2 * r) / (n - 1),
                      f"{name}'s attack ranks {ordinal(r)} of {n} in {league_name}, "
                      f"scoring {np.exp(att[i]):.2f} times the league average."))
        r = _rank(dfn, i, best_high=False, among=among)
        found.append((abs(n + 1 - 2 * r) / (n - 1),
                      f"{name}'s defence ranks {ordinal(r)} of {n}, conceding "
                      f"{np.exp(dfn[i]):.2f} times the league average."))
    if elo_gap is not None and np.isfinite(elo_gap):
        better = names.get(home if elo_gap > 0 else away, "")
        found.append((min(abs(elo_gap) / 300, 1.0),
                      f"Elo rates {better} {abs(elo_gap):.0f} points higher, home advantage "
                      "included." if abs(elo_gap) >= 25 else
                      "Elo rates the two clubs almost level, home advantage included."))
    home_goals = float(np.exp(post.mu + post.home).mean() - np.exp(post.mu).mean())
    found.append((0.3, f"Playing at home adds about {home_goals:.2f} goals a match in "
                       f"{league_name}."))
    for team in promoted or set():
        if team in (home, away):
            found.append((0.5, f"{names.get(team, team)} were promoted: their rating still "
                               "leans on second-tier form."))
    for team in manager_change or set():
        if team in (home, away):
            found.append((0.6, f"{names.get(team, team)} changed manager in the last 30 days."))
    if news:
        for side, team in (("home", home), ("away", away)):
            answer = news.get(side) or {}
            if answer.get("status") == "answered" and (answer.get("starters_out") or 0) > 0:
                n_out = answer["starters_out"]
                extra = ", including the main goal threat" if answer.get("threat_out") else ""
                found.append((1.05, f"Team news: {names.get(team, team)} without {n_out}"
                                   f"{'+' if n_out >= 3 else ''} regular starter"
                                   f"{'s' if n_out != 1 else ''}{extra}."))
    found.sort(key=lambda x: -x[0])
    return [text for _, text in found[:top]]
