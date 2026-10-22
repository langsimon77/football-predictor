"""2026/27 Europa League and Conference League fixtures and results from two sources (task 5.2).

1. Wikipedia's league-phase pages (MediaWiki API; a structured results grid: name_XXX holds a
   club, match_XXX_YYY a score or a date). Free, updated within hours of each match.
2. euro2627.py: the list typed in from public reports on 22 Oct 2026 (it also holds kick-off
   times and the qualifying rounds, which the grid does not).

A fixture or result counts as verified when both sources have it and agree (date within a
day, same score). Anything in one source only, or where they disagree, is flagged unverified;
a result with conflicting scores is left out of the training data. Kick-off times come from
the list; when it has none the earliest usual slot is used and flagged, so a forecast never
locks late.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import paths

PAGES = {"UEL": "2026\u201327 UEFA Europa League league phase", "UECL": "2026\u201327 UEFA Conference League league phase"}
UA = {"User-Agent": "football-predictor/1.0 (+https://github.com/langsimon77/football-predictor)"}
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
# Wikipedia flag codes that differ from the pipeline's country codes.
WIKI_CC = {"SLO": "SVN", "NIR": "NIR", "IRL": "IRL"}
NAME = re.compile(r"^\|name_([A-Z0-9]+)\s*=\s*\{\{fbaicon\|([A-Z]{3})\}\}\s*\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", re.M)
MATCH = re.compile(r"^\|match_([A-Z0-9]+)_([A-Z0-9]+)\s*=\s*(.*?)\s*$", re.M)
MATCHDAY = re.compile(r"<!--\s*Matchday\s+(\d+)\s*-->")
SCORE = re.compile(r"^(\d+)\s*[\u2013\-]\s*(\d+)$")
DAY = re.compile(r"\{\{small\|(\d{1,2}) ([A-Z][a-z]{2})\}\}")


def fetch_page(title: str) -> str:
    """The page's wikitext; a copy is kept in paths.SOURCES/wikipedia for reproducibility."""
    cache = paths.SOURCES / "wikipedia" / (re.sub(r"\W+", "_", title) + ".json")
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "wikitext", "format": "json", "formatversion": 2})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            body = json.loads(r.read())
        if "error" in body:
            raise RuntimeError(body["error"].get("info"))
        cache.parent.mkdir(parents=True, exist_ok=True)
        body["fetched_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        cache.write_text(json.dumps(body), encoding="utf-8")
    except Exception:  # offline: the last copy, if any
        if not cache.exists():
            raise
        body = json.loads(cache.read_text(encoding="utf-8"))
    return body["parse"]["wikitext"]


def season_date(day: int, mon: str) -> date:
    m = MONTHS[mon]
    return date(2026 if m >= 7 else 2027, m, day)


def parse_grid(text: str, comp: str) -> list[dict]:
    clubs = {code: (name.strip(), WIKI_CC.get(cc, cc)) for code, cc, name in NAME.findall(text)}
    out, md = [], None
    cut = text.find("|match_")
    pos = 0
    for m in re.finditer(MATCHDAY.pattern + "|" + MATCH.pattern, text[cut - 200 if cut > 200 else 0:], re.M):
        if m.group(1):
            md = int(m.group(1))
            continue
        h, a, val = m.group(2), m.group(3), m.group(4)
        if h not in clubs or a not in clubs:
            continue
        entry = {"comp": comp, "matchday": md, "home": clubs[h][0], "hcc": clubs[h][1], "away": clubs[a][0], "acc": clubs[a][1],
                 "date": None, "hg": None, "ag": None}
        s = SCORE.match(re.sub(r"<[^>]+>|\[\[[^\]]*\]\]", "", val).strip())
        d = DAY.search(val)
        if s:
            entry["hg"], entry["ag"] = int(s.group(1)), int(s.group(2))
        if d:
            entry["date"] = season_date(int(d.group(1)), d.group(2)).isoformat()
        if s or d:
            out.append(entry)
        pos += 1
    return out


if __name__ == "__main__":
    for comp, title in PAGES.items():
        g = parse_grid(fetch_page(title), comp)
        print(comp, len(g), "entries;", sum(e["hg"] is not None for e in g), "with scores;", sorted({e["hcc"] for e in g} | {e["acc"] for e in g}))
        print("  ", g[0], g[-1])


# ---------------------------------------------------------------- cross-check
LOCAL_EARLIEST = "16:30"  # earliest usual league-phase slot, Central European time


def earliest_utc(day: str) -> str:
    from zoneinfo import ZoneInfo
    local = datetime.fromisoformat(f"{day}T{LOCAL_EARLIEST}").replace(tzinfo=ZoneInfo("Europe/Paris"))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def collect(R, run_date: date, horizon_days: int = 10, wiki: list | None = None,
            hand_results: list | None = None, hand_fixtures: list | None = None) -> dict:
    """Results and fixtures from both sources, each flagged verified or not.

    R(name, country) is the pipeline's club resolver (names.resolve). wiki can be given (tests);
    otherwise the two pages are fetched (or their last copies used)."""
    import euro2627
    if wiki is None:
        wiki = []
        for comp, title in PAGES.items():
            try:
                wiki += parse_grid(fetch_page(title), comp)
            except Exception as err:  # the list alone still works, all unverified
                print(f"Wikipedia {comp} unavailable ({type(err).__name__}); fixtures from the list only")
    key = lambda comp, h, hc, a, ac: (comp, R(h, hc), R(a, ac))  # noqa: E731
    hr = euro2627.R if hand_results is None else hand_results
    hf = euro2627.FIX if hand_fixtures is None else hand_fixtures
    hand_res = {key(r["comp"], r["home"], r["hcc"], r["away"], r["acc"]): r for r in hr if r["comp"] in PAGES}
    hand_fix = {key(f["comp"], f["home"], f["hcc"], f["away"], f["acc"]): f for f in hf}
    results, fixtures, conflicts, md_dates, seen_res, seen_fix = [], [], [], {}, set(), set()
    for w in wiki:
        k = key(w["comp"], w["home"], w["hcc"], w["away"], w["acc"])
        if w["hg"] is not None:
            h = hand_res.get(k)
            seen_res.add(k)
            if h and (h["hg"], h["ag"]) != (w["hg"], w["ag"]):
                conflicts.append({"key": list(k), "list": [h["hg"], h["ag"]], "wikipedia": [w["hg"], w["ag"]]})
                continue
            if h:
                md_dates.setdefault((w["comp"], w["matchday"]), {}).setdefault(h["date"], 0)
                md_dates[(w["comp"], w["matchday"])][h["date"]] += 1
            results.append({**w, "date": h["date"] if h else None, "verified": bool(h), "sources": ["wikipedia"] + (["list"] if h else [])})
        elif w["date"]:
            f = hand_fix.get(k)
            seen_fix.add(k)
            ok = bool(f) and abs((date.fromisoformat(f["kickoff"][:10]) - date.fromisoformat(w["date"])).days) <= 1
            fixtures.append({"comp": w["comp"], "home": f["home"] if f else w["home"], "hcc": w["hcc"], "away": f["away"] if f else w["away"], "acc": w["acc"],
                             "kickoff": f["kickoff"] if f else earliest_utc(w["date"]), "time_confirmed": bool(f),
                             "round": f"League phase, matchday {w['matchday']}", "verified": ok, "sources": ["wikipedia"] + (["list"] if f else [])})
    for r in results:  # a Wikipedia-only result takes the date its matchday was played
        if r["date"] is None:
            days = md_dates.get((r["comp"], r["matchday"]))
            r["date"] = max(days, key=days.get) if days else None
    for k, h in hand_res.items():
        if k not in seen_res:
            results.append({"comp": h["comp"], "home": h["home"], "hcc": h["hcc"], "away": h["away"], "acc": h["acc"], "date": h["date"],
                            "hg": h["hg"], "ag": h["ag"], "verified": False, "sources": ["list"]})
    for k, f in hand_fix.items():
        if k not in seen_fix:
            fixtures.append({**f, "time_confirmed": True, "verified": False, "sources": ["list"]})
    start = datetime.combine(run_date, datetime.min.time(), timezone.utc)
    upcoming = [f for f in fixtures if start <= datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00")) < start + timedelta(days=horizon_days)]
    report = {"run_date": run_date.isoformat(), "wikipedia_entries": len(wiki),
              "results": {"verified": sum(r["verified"] for r in results), "unverified": sum(not r["verified"] for r in results), "conflicts": conflicts},
              "upcoming": {"verified": sum(f["verified"] for f in upcoming), "unverified": sum(not f["verified"] for f in upcoming),
                           "time_unconfirmed": sum(not f["time_confirmed"] for f in upcoming)}}
    return {"results": [r for r in results if r["date"]], "upcoming": sorted(upcoming, key=lambda f: f["kickoff"]), "report": report}
