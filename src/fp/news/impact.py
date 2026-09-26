"""From Lang's answers to changes in the scoring rates (spec S6.3, decision D2).

We have no player data (D2), so the effect is per missing regular starter, not
per named player. Each size is an Assumption [A], chosen small on purpose; the
news-on against news-off comparison after 10 gameweeks (spec S6.5) decides
whether to keep, shrink, or drop them.

For a club with n regular starters out:
- its own scoring rate falls by STARTER_ATTACK per starter;
- its opponent's scoring rate rises by STARTER_CONCEDE per starter;
- if the main goal threat is out, its own scoring rate falls a further THREAT_ATTACK.
Each match's rate multiplier is capped at 1 +/- CAP (spec S6.3: 12%).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

RULE = "news_v1"
STARTER_ATTACK = 0.025   # [A] an average starter, replaced by an average squad player
STARTER_CONCEDE = 0.025  # [A]
THREAT_ATTACK = 0.06     # [A] extra loss when the top scorer is out
CAP = 0.12               # spec S6.3
MAX_COUNTED = 3          # "3 or more" counts as 3


@dataclass(frozen=True)
class TeamNews:
    """One club's answer. status: answered, dont_know, or unanswered."""

    status: str
    starters_out: int = 0
    threat_out: bool = False

    @property
    def usable(self) -> bool:
        return self.status == "answered"


def _loss(news: TeamNews | None) -> tuple[float, float]:
    """(fall in own scoring, rise in opponent scoring) for one club."""
    if news is None or not news.usable:
        return 0.0, 0.0
    n = min(news.starters_out, MAX_COUNTED)
    return n * STARTER_ATTACK + news.threat_out * THREAT_ATTACK, n * STARTER_CONCEDE


def _clip(x: float) -> float:
    return min(max(x, 1 - CAP), 1 + CAP)


def scales(home: TeamNews | None, away: TeamNews | None) -> tuple[float, float, bool]:
    """Multipliers for the home and away scoring rates, and whether a cap bit."""
    home_attack, home_concede = _loss(home)
    away_attack, away_concede = _loss(away)
    raw_home = 1 - home_attack + away_concede
    raw_away = 1 - away_attack + home_concede
    home_scale, away_scale = _clip(raw_home), _clip(raw_away)
    return home_scale, away_scale, (home_scale != raw_home or away_scale != raw_away)


def record(home: TeamNews | None, away: TeamNews | None, source: str) -> dict:
    """The ledger's news_adjustments entry for one match."""
    home_scale, away_scale, capped = scales(home, away)
    return {"rule": RULE, "source": source,
            "home": asdict(home) if home else None, "away": asdict(away) if away else None,
            "scale_home_goals": round(home_scale, 4), "scale_away_goals": round(away_scale, 4),
            "capped": capped}
