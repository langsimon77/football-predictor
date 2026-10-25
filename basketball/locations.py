"""Basketball phase B2, step 1: each club's home city and its coordinates, for travel distances.

Plan: data/audit/preregistration_basketball_b2_2026_10.md, section 1. Source: English Wikipedia
(CC BY-SA 4.0) through the MediaWiki API, with the project's polite downloader. For each club,
the infobox "location" links the city; the city article's coordinates are used. If a club has no
location, or its city has no coordinates, the infobox "arena" article is used instead.

Writes data/manual/basketball_club_cities.csv (club_title, city, lat, lon, source); the build
stops if any club in data/processed/basketball/games.parquet has no coordinates.

    uv run python basketball/locations.py [--offline]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from urllib.parse import urlencode

import pandas as pd
from audit_sample import API, SOURCE, wikitext

from data import GAMES, link_target, resolve
from fp import ROOT
from fp.ingest import http

CITIES = ROOT / "data" / "manual" / "basketball_club_cities.csv"


def infobox_field(text: str, name: str) -> str | None:
    """The link target of an infobox field such as '| location = [[Madrid]], Spain'."""
    head = text[:8000]
    m = re.search(r"\|\s*" + name + r"\s*=\s*([^\n]*)", head)
    return link_target(m.group(1)) if m else None


def coordinates(titles: list[str], offline: bool) -> dict[str, tuple[float, float]]:
    """Primary coordinates of each article that has them."""
    out: dict[str, tuple[float, float]] = {}
    todo = sorted(set(titles))
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        url = API + urlencode({"action": "query", "prop": "coordinates", "colimit": "max",
                               "titles": "|".join(batch), "redirects": 1, "format": "json",
                               "formatversion": 2})
        name = "coords_max_" + hashlib.sha1("|".join(batch).encode()).hexdigest()[:12] + ".json"
        q = json.loads(http.fetch(url, SOURCE, name, refresh=not offline)
                       .read_text(encoding="utf-8"))["query"]
        back = {r["to"]: r["from"] for r in q.get("redirects", [])}
        back.update({n["to"]: n["from"] for n in q.get("normalized", [])})
        for p in q.get("pages", []):
            if p.get("coordinates"):
                c = p["coordinates"][0]
                title = p["title"]
                while title in back and title not in batch:
                    title = back[title]
                out[title] = (float(c["lat"]), float(c["lon"]))
                out[p["title"]] = out[title]
    return out


def build(offline: bool = False) -> pd.DataFrame:
    games = pd.read_parquet(GAMES)
    clubs = sorted(set(games["home_title"]) | set(games["away_title"]))
    fields = {}
    for club in clubs:
        text = wikitext(club, refresh=not offline) or ""
        fields[club] = (infobox_field(text, "location"), infobox_field(text, "arena"))
    names = [x for pair in fields.values() for x in pair if x]
    current = resolve(names, offline)
    coords = coordinates([t for t in current.values() if t], offline)
    rows, missing = [], []
    for club, (city, arena) in fields.items():
        for kind, title in (("city", city), ("arena", arena)):
            t = current.get(title) if title else None
            if t and t in coords:
                rows.append({"club_title": club, "city": t, "lat": coords[t][0],
                             "lon": coords[t][1], "source": f"wikipedia {kind}"})
                break
        else:
            missing.append(club)
    if missing:
        raise SystemExit("No coordinates for: " + "; ".join(missing))
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached copies only")
    args = parser.parse_args(argv)
    table = build(args.offline)
    CITIES.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(CITIES, index=False)
    print(table.to_string(index=False))
    print(f"written {CITIES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
