"""Freshness check (spec S3): is each source keeping up with the calendar?

football-data.co.uk has the statistics we need, but it updates a few times a
week. openfootball updates daily. If a match finished more than 72 hours ago and
football-data.co.uk still lacks it, the league is stale: take its score from
openfootball, flag the run, and leave corners and cards to wait.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

STALE_AFTER = pd.Timedelta(hours=72)
TIME_WARNING_WINDOW = pd.Timedelta(hours=72)


@dataclass
class LeagueFreshness:
    league: str
    latest_result_utc: pd.Timestamp | None
    missing_results: list[str] = field(default_factory=list)
    stale: bool = False
    unconfirmed_soon: list[str] = field(default_factory=list)


@dataclass
class FreshnessReport:
    checked_at: pd.Timestamp
    leagues: list[LeagueFreshness]

    @property
    def stale(self) -> bool:
        return any(lf.stale for lf in self.leagues)

    def summary(self) -> str:
        lines = [f"freshness check at {self.checked_at:%Y-%m-%d %H:%M} UTC"]
        for lf in self.leagues:
            status = "STALE" if lf.stale else "ok"
            latest = f"{lf.latest_result_utc:%Y-%m-%d}" if lf.latest_result_utc else "none"
            lines.append(
                f"  {lf.league}: {status}; latest football-data result {latest}; "
                f"{len(lf.missing_results)} finished matches missing; "
                f"{len(lf.unconfirmed_soon)} matches within 72 h without a kickoff time"
            )
        return "\n".join(lines)


def check(
    matches: pd.DataFrame, fixtures: pd.DataFrame, now: pd.Timestamp | None = None
) -> FreshnessReport:
    now = now if now is not None else pd.Timestamp(datetime.now(UTC))
    season = int(fixtures["season"].max())
    have = set(matches.loc[matches["season"] == season, "match_id"])
    leagues = []
    for league, cal in fixtures.groupby("league"):
        played = cal[cal["status"] == "played"]
        missing = played[~played["match_id"].isin(have)]
        # A match without a kickoff time counts from the start of its date.
        kick = missing["kickoff_utc"].fillna(pd.to_datetime(missing["date"]).dt.tz_localize("UTC"))
        stale = bool((now - kick > STALE_AFTER).any())

        upcoming = cal[cal["status"] == "scheduled"]
        day = pd.to_datetime(upcoming["date"]).dt.tz_localize("UTC")
        soon = upcoming[~upcoming["time_confirmed"] & (day - now < TIME_WARNING_WINDOW)]

        in_fd = matches[(matches["league"] == league) & (matches["season"] == season)]
        latest = in_fd["kickoff_utc"].max() if len(in_fd) else None
        leagues.append(LeagueFreshness(
            league=str(league),
            latest_result_utc=latest,
            missing_results=list(missing["match_id"]),
            stale=stale,
            unconfirmed_soon=list(soon["match_id"]),
        ))
    return FreshnessReport(checked_at=now, leagues=leagues)
