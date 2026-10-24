"""Basketball phase B0 (data audit): sample the open sources and count what they hold.

Only openly licensed sources are read here: English Wikipedia (CC BY-SA 4.0) through
the MediaWiki API, with the project's named User-Agent, at most one request every
3 seconds, every response cached under data/raw/wikipedia_basketball/ (fp.ingest.http).
Official league sites and APIs are not downloaded: see
reports/basketball_data_audit_2026_10.md for why.

What it checks, per league and season:
- NBL and EuroLeague: the season article's game boxes (date, tip-off time, scores).
- NBA: the 30 team-season articles' game logs (date, home or away, scores).
- Cross-checks: each NBA game must appear in both teams' logs with the same score;
  the EuroLeague game boxes must match the season's results grid.

Writes data/basketball/audit_sample.json and prints a summary.

    uv run python basketball/audit_sample.py [--offline]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from fp import ROOT
from fp.ingest import http

SOURCE = "wikipedia_basketball"
API = "https://en.wikipedia.org/w/api.php?"
OUT = ROOT / "data" / "basketball" / "audit_sample.json"
CURRENT = 2026  # 2026/27
EN_DASH, EM_DASH = chr(0x2013), chr(0x2014)  # built, not typed: the repository bans both
NBA_TEAMS = (
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
    "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons",
    "Golden State Warriors", "Houston Rockets", "Indiana Pacers", "Los Angeles Clippers",
    "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat", "Milwaukee Bucks",
    "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks", "Oklahoma City Thunder",
    "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
    "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards",
)
# NBA game IDs start with the game type [E: the league's ID pattern, checked below by
# counting 1,230 regular-season games]: 001 preseason, 002 regular season, 004 playoffs,
# 005 play-in. Seasons up to about 2016/17 use team-code IDs ("BOSPHI") instead.
NBA_KIND = {"001": "preseason", "002": "regular", "004": "playoffs", "005": "play-in"}


def season_label(year: int) -> str:
    """2025 -> Wikipedia's '2025-26' title form, with its en dash (EN_DASH)."""
    return f"{year}{EN_DASH}{(year + 1) % 100:02d}"


def season_key(year: int) -> str:
    """2025 -> '2025/26', the project's own form, used in the output file."""
    return f"{year}/{(year + 1) % 100:02d}"


def no_dashes(text: str | None) -> str | None:
    """Wikipedia text with its en and em dashes turned into hyphens (scripts/check_dashes.py)."""
    return None if text is None else text.replace(EN_DASH, "-").replace(EM_DASH, "-")


def wikitext(title: str, refresh: bool) -> str | None:
    """The article's wikitext, or None when there is no such article."""
    url = API + urlencode({"action": "parse", "page": title, "prop": "wikitext",
                           "redirects": 1, "format": "json", "formatversion": 2})
    name = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") + ".json"
    data = json.loads(http.fetch(url, SOURCE, name, refresh=refresh).read_text(encoding="utf-8"))
    return data.get("parse", {}).get("wikitext")


def templates(text: str, name: str) -> list[str]:
    """The inside of every {{name ...}} template, nested templates included."""
    out, i = [], 0
    pattern = re.compile(r"\{\{\s*" + re.escape(name) + r"\b", re.I)
    while (m := pattern.search(text, i)) is not None:
        depth, j = 0, m.start()
        while j < len(text):
            if text.startswith("{{", j):
                depth, j = depth + 1, j + 2
            elif text.startswith("}}", j):
                depth, j = depth - 1, j + 2
                if depth == 0:
                    break
            else:
                j += 1
        out.append(text[m.end():j - 2])
        i = j
    return out


def params(body: str) -> dict[str, str]:
    """Named parameters of a template body, split on | outside links and templates."""
    parts: list[str] = []
    cur: list[str] = []
    depth, i = 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            cur.append(two)
            i += 2
        elif two in ("}}", "]]"):
            depth -= 1
            cur.append(two)
            i += 2
        elif body[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(body[i])
            i += 1
    parts.append("".join(cur))
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def plain(value: str) -> str:
    """Wiki markup to plain text: [[a|b]] -> b, no templates, no bold or italics."""
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value.replace("'''", "").replace("''", "")).strip()


def score(value: str) -> int | None:
    m = re.search(r"\d{1,3}", plain(value))
    return int(m.group()) if m else None


def parse_date(value: str) -> str | None:
    text = plain(value)
    for fmt in ("%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def boxes(text: str) -> list[dict]:
    """Games from {{basketballbox}} templates (NBL and EuroLeague season articles)."""
    games = []
    for body in templates(text, "basketballbox"):
        p = params(body)
        time = re.search(r"\d{1,2}:\d{2}", p.get("time", ""))
        games.append({"date": parse_date(p.get("date", "")),
                      "time": time.group() if time else None,
                      "home": plain(p.get("teamA", "")), "away": plain(p.get("teamB", "")),
                      "home_pts": score(p.get("scoreA", "")),
                      "away_pts": score(p.get("scoreB", ""))})
    return games


def time_note(text: str) -> str | None:
    """The article's note on which time zone its times use, if it has one."""
    m = re.search(r"[^.\n]*\b(?:All times|times are|Times are)\b[^.\n]*", text)
    return no_dashes(plain(m.group().split("{{")[0])[:200]) if m else None


def box_summary(games: list[dict], today: str) -> dict:
    played = [g for g in games if g["home_pts"] is not None and g["away_pts"] is not None
              and g["home_pts"] + g["away_pts"] > 0]
    future = [g for g in games if g not in played and g["date"] and g["date"] >= today]
    timed = [g for g in future if g["time"]]
    return {"games": len(games), "dated": sum(1 for g in games if g["date"]),
            "with_time": sum(1 for g in games if g["time"]), "played": len(played),
            "future": len(future), "future_with_time": len(timed),
            "last_future_with_time": max((g["date"] for g in timed), default=None)}


def grid_scores(text: str) -> Counter:
    """(home points, away points) from a {{#invoke:Sports results}} grid."""
    found = re.findall(r"match_[A-Za-z0-9]+_[A-Za-z0-9]+\s*=\s*(?:\[\[[^|\]]*\|)?'*(\d{2,3})'*"
                       r"\s*[" + EN_DASH + r"-]\s*'*(\d{2,3})", text)
    return Counter((int(a), int(b)) for a, b in found)


def nba_rows(text: str) -> list[dict]:
    """Game log rows: date, home or away, NBA game ID, and the team's points for and
    against (None for a game not played yet)."""
    rows = []
    for row in re.split(r"\n\|-", text):
        t = re.search(r"\{\{\s*NBA game\s*\|([^{}]*)\}\}", row)
        if not t:
            continue
        p = params(t.group(1))
        if "id" not in p:
            continue
        cells = [c.strip() for c in row.split("\n|")[1:]]
        pf, pa = p.get("pf", ""), p.get("pa", "")
        played = pf.isdigit() and pa.isdigit()
        rows.append({"id": p["id"], "kind": NBA_KIND.get(p["id"][:3], "other"),
                     "date": plain(cells[1]) if len(cells) > 1 else None,
                     "away": (cells[2] if len(cells) > 2 else "").startswith("@"),
                     "pf": int(pf) if played else None, "pa": int(pa) if played else None})
    return rows


def nba_check(logs: dict[str, list[dict]]) -> dict:
    """Each regular-season game should be in two team logs, one home and one away, with
    mirrored scores once played."""
    seen: dict[str, list[dict]] = {}
    for rows in logs.values():
        for r in rows:
            if r["kind"] == "regular":
                seen.setdefault(r["id"], []).append(r)
    played = [e for e in seen.values() if any(r["pf"] is not None for r in e)]
    both = [e for e in played if len(e) == 2]
    agree = sum(1 for a, b in both
                if a["pf"] == b["pa"] and a["pa"] == b["pf"] and a["away"] != b["away"])
    return {"regular_games_listed": len(seen), "regular_played": len(played),
            "played_in_both_logs": len(both), "both_logs_agree": agree,
            "played_in_one_log_only": sum(1 for e in played if len(e) == 1)}


def run(offline: bool = False) -> dict:
    today = datetime.now(UTC).date().isoformat()
    result: dict = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "source": "English Wikipedia via the MediaWiki API (CC BY-SA 4.0)",
                    "leagues": {}, "cross_checks": {}}

    def read(title: str, year: int) -> str | None:
        return wikitext(title, refresh=(year == CURRENT) and not offline)

    for league, titles in (("NBL", ("{s} NBL season",)),
                           ("EuroLeague", ("{s} EuroLeague regular season",
                                           "{s} EuroLeague Regular Season"))):
        per = {}
        for year in range(2016, CURRENT + 1):
            text = title = None
            for pattern in titles:
                title = pattern.format(s=season_label(year))
                if (text := read(title, year)) is not None:
                    break
            key = season_key(year)
            if text is None:
                per[key] = {"article": None}
                continue
            per[key] = {"article": no_dashes(title), **box_summary(boxes(text), today),
                        "time_note": time_note(text)}
            print(league, key, per[key], flush=True)
        result["leagues"][league] = per

    # EuroLeague 2025/26: the game boxes against the results grid on the season page.
    last = season_label(CURRENT - 1)
    box_text = read(f"{last} EuroLeague regular season", CURRENT - 1) or ""
    grid_text = read(f"{last} EuroLeague", CURRENT - 1) or ""
    played = Counter((g["home_pts"], g["away_pts"]) for g in boxes(box_text)
                     if g["home_pts"] and g["away_pts"])
    grid = grid_scores(grid_text)
    result["cross_checks"]["EuroLeague " + season_key(CURRENT - 1)] = {
        "boxes_played": sum(played.values()), "grid_results": sum(grid.values()),
        "same_home_away_scores": sum((played & grid).values())}

    nba = {}
    for year in (2016, CURRENT - 1, CURRENT):
        logs: dict[str, list[dict]] = {}
        missing = []
        for team in NBA_TEAMS:
            text = read(f"{season_label(year)} {team} season", year)
            if text is None:
                missing.append(team)
            logs[team] = nba_rows(text) if text is not None else []
        kinds = Counter(r["kind"] for rows in logs.values() for r in rows)
        nba[season_key(year)] = {"team_articles_missing": missing,
                                 "team_logs_with_games": sum(1 for r in logs.values() if r),
                                 "rows_by_kind": dict(kinds), **nba_check(logs)}
        print("NBA", season_key(year), nba[season_key(year)], flush=True)
    result["leagues"]["NBA"] = nba
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached copies only")
    args = parser.parse_args(argv)
    result = run(args.offline)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written {Path(OUT).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
