"""Manager changes from Wikipedia, confirmed by Lang (spec S5.5, S6.4; PRD item 18).

Each run reads the club infobox ("manager" or "head coach") from English
Wikipedia for clubs playing in the next 72 hours, through the public API with
our named User-Agent, at most one request every 3 seconds (DATA_SOURCES: allowed;
content CC BY-SA, attributed in data/manual/managers.csv).

`data/manual/managers.csv` is a log: one row per name we have seen for a club.
- status `seed`: the name on the day we started; no flag.
- status `pending`: a new name; Lang is asked to confirm it; the club carries the
  `manager_change` flag for 30 days unless Lang answers "no".
- status `confirmed` or `rejected`: Lang's answer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from fp import ROOT
from fp.ingest import http

MANAGERS = ROOT / "data" / "manual" / "managers.csv"
TITLES = ROOT / "data" / "manual" / "wikipedia_titles.csv"
COLUMNS = ["team_id", "manager", "first_seen_utc", "status", "source"]
FLAG_DAYS = 30
API = ("https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&section=0"
       "&format=json&formatversion=2&redirects=1&page=")
FIELD = re.compile(r"^\s*\|\s*(manager|head[ _]?coach|coach)\s*=\s*(.*)$",
                   re.IGNORECASE | re.MULTILINE)


def clean(value: str) -> str:
    """Plain name from an infobox value such as `[[Mikel Arteta]]<ref>...</ref>`."""
    v = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    v = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", v, flags=re.DOTALL)
    v = re.sub(r"<[^>]+>", " ", v)
    for _ in range(3):  # unwrap simple wrapper templates, drop the rest
        v = re.sub(r"\{\{\s*(?:nowrap|nobr|small)\s*\|([^{}]*)\}\}", r"\1", v,
                   flags=re.IGNORECASE)
        v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    return re.sub(r"\s+", " ", v).strip(" ,;")


def from_wikitext(text: str) -> str | None:
    m = FIELD.search(text)
    if not m:
        return None
    return clean(m.group(2)) or None


def current(team_id: str, title: str) -> str | None:
    """Today's infobox manager for one club, or None if the page cannot be read."""
    try:
        path = http.fetch(API + quote(title), "wikipedia", f"{team_id}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        return from_wikitext(data["parse"]["wikitext"])
    except Exception:
        return None


def load(path: Path = MANAGERS) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.read_csv(path)
    frame["first_seen_utc"] = pd.to_datetime(frame["first_seen_utc"], utc=True)
    return frame


def save(frame: pd.DataFrame, path: Path = MANAGERS) -> None:
    out = frame[COLUMNS].copy()
    out["first_seen_utc"] = pd.to_datetime(out["first_seen_utc"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%MZ")
    out.to_csv(path, index=False)


def latest(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """The newest row per club that Lang has not rejected."""
    live = frame[frame["status"] != "rejected"].sort_values("first_seen_utc")
    return {str(t): g.iloc[-1] for t, g in live.groupby("team_id")}


Change = tuple[str, str, str]  # club, previous name, new name


def observe(frame: pd.DataFrame, seen: dict[str, str], now: pd.Timestamp,
            source: str = "Wikipedia (CC BY-SA)") -> tuple[pd.DataFrame, list[Change]]:
    """Add today's names. Returns the updated log and new changes (club, old, new)."""
    last = latest(frame)
    rejected = {(str(r.team_id), str(r.manager)) for r in frame.itertuples()
                if r.status == "rejected"}
    rows, changes = [], []
    for team, name in seen.items():
        prev = last.get(team)
        if prev is None:
            rows.append({"team_id": team, "manager": name, "first_seen_utc": now,
                         "status": "seed", "source": source})
        elif name != prev["manager"] and (team, name) not in rejected:
            rows.append({"team_id": team, "manager": name, "first_seen_utc": now,
                         "status": "pending", "source": source})
            changes.append((team, str(prev["manager"]), name))
    if rows:
        frame = pd.concat([frame, pd.DataFrame(rows)], ignore_index=True)
    return frame, changes


def apply_answers(frame: pd.DataFrame, answers: dict[str, str]) -> pd.DataFrame:
    """Lang's yes or no on the newest pending name for each club."""
    frame = frame.copy()
    for team, answer in answers.items():
        pending = frame.index[(frame["team_id"] == team) & (frame["status"] == "pending")]
        if len(pending):
            frame.loc[pending[-1], "status"] = "confirmed" if answer == "yes" else "rejected"
    return frame


def recent_changes(frame: pd.DataFrame, now: pd.Timestamp) -> set[str]:
    """Clubs whose manager changed in the last 30 days (pending or confirmed)."""
    since = now - pd.Timedelta(days=FLAG_DAYS)
    hit = frame[frame["status"].isin(["pending", "confirmed"])
                & (frame["first_seen_utc"] > since) & (frame["first_seen_utc"] <= now)]
    return set(hit["team_id"].astype(str))


def titles() -> dict[str, str]:
    t = pd.read_csv(TITLES)
    return dict(zip(t["team_id"], t["title"], strict=True))
