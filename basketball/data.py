"""Basketball phase B1, step 1: one table of regular-season games for the EuroLeague and the NBL.

Source: English Wikipedia season articles (CC BY-SA 4.0), read with the project's polite
downloader (fp.ingest.http: named User-Agent, one request every 3 seconds, every response
cached). Plan: data/audit/preregistration_basketball_b1_2026_10.md, section 1.

Club IDs: each club's current Wikipedia article title. A game box links the club (or the
club's season article, "2026-27 Melbourne United season"); the link is followed through
Wikipedia's redirects to the current title, so sponsor names and renamed articles land on one
club. Names without a link go through data/manual/basketball_club_aliases.csv; a name that
maps nowhere stops the build.

Cross-check (EuroLeague): each game box against the season's results grid. A game the two
disagree on is left out (the Europe pipeline's rule). The NBL has no second open source.

Writes data/processed/basketball/games.parquet (outside Git) and
data/basketball/b1_data_summary.json (counts, left-out games, time zone check).

    uv run python basketball/data.py [--offline]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from urllib.parse import urlencode

import numpy as np
import pandas as pd
from audit_sample import (  # noqa: E402  (same folder; run as a script or via sys.path)
    API,
    CURRENT,
    EN_DASH,
    SOURCE,
    params,
    parse_date,
    plain,
    score,
    season_key,
    season_label,
    templates,
    wikitext,
)

from fp import ROOT
from fp.ingest import http

GAMES = ROOT / "data" / "processed" / "basketball" / "games.parquet"
SUMMARY = ROOT / "data" / "basketball" / "b1_data_summary.json"
ALIASES = ROOT / "data" / "manual" / "basketball_club_aliases.csv"

# The seasons the plan uses (section 4): warm-up, tuning and test, plus the current season.
SEASONS = {
    "EuroLeague": list(range(2016, CURRENT + 1)),
    "NBL": [2016, 2017, 2022, 2023, 2024, 2025, CURRENT],
}
ARTICLES = {"EuroLeague": ("{s} EuroLeague regular season", "{s} EuroLeague Regular Season"),
            "NBL": ("{s} NBL season",)}
GRID_ARTICLE = "{s} EuroLeague"
# EuroLeague articles state "Times are CET or CEST" [V]; Paris follows those rules.
EUROLEAGUE_ZONE = "Europe/Paris"
# NBL articles state no time zone. If the times are the home venue's local time (checked in
# nbl_time_check), these are the zones [E: the clubs' home cities].
NBL_ZONES = {
    "Adelaide 36ers": "Australia/Adelaide", "Brisbane Bullets": "Australia/Brisbane",
    "Cairns Taipans": "Australia/Brisbane", "Illawarra Hawks": "Australia/Sydney",
    "Melbourne United": "Australia/Melbourne", "New Zealand Breakers": "Pacific/Auckland",
    "Perth Wildcats": "Australia/Perth", "South East Melbourne Phoenix": "Australia/Melbourne",
    "Sydney Kings": "Australia/Sydney", "Tasmania JackJumpers": "Australia/Hobart",
}
SEASON_PREFIX = re.compile(r"^\d{4}[" + EN_DASH + r"-]\d{2,4}\s+")


def link_target(value: str) -> str | None:
    """The first wiki link's target, with a season article reduced to its club:
    '[[2026-27 Melbourne United season|Melbourne United]]' -> 'Melbourne United'."""
    m = re.search(r"\[\[([^|\]#]+)", value)
    if not m:
        return None
    target = m.group(1).strip().replace("_", " ")
    if target.endswith(" season") and SEASON_PREFIX.match(target):
        target = SEASON_PREFIX.sub("", target)[: -len(" season")]
    return target[:1].upper() + target[1:]


def club_id(title: str) -> str:
    """A readable ID from a Wikipedia title: 'Hapoel Tel Aviv B.C.' -> 'hapoel_tel_aviv_b_c'."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_title.lower()).strip("_")


def resolve(titles: list[str], offline: bool) -> dict[str, str | None]:
    """Each title's current article title after Wikipedia's redirects (None if no article)."""
    out: dict[str, str | None] = {}
    todo = sorted(set(titles))
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        url = API + urlencode({"action": "query", "titles": "|".join(batch), "redirects": 1,
                               "format": "json", "formatversion": 2})
        name = "redirects_" + hashlib.sha1("|".join(batch).encode()).hexdigest()[:12] + ".json"
        data = json.loads(http.fetch(url, SOURCE, name, refresh=not offline)
                          .read_text(encoding="utf-8"))["query"]
        step = {n["from"]: n["to"] for n in data.get("normalized", [])}
        step.update({r["from"]: r["to"] for r in data.get("redirects", [])})
        missing = {p["title"] for p in data.get("pages", []) if p.get("missing")}
        for t in batch:
            cur, seen = t, set()
            while cur in step and cur not in seen:
                seen.add(cur)
                cur = step[cur]
            out[t] = None if cur in missing else cur
    return out


def aliases() -> dict[tuple[str, str], str]:
    if not ALIASES.exists():
        return {}
    a = pd.read_csv(ALIASES)
    return {(r.league, r.name): r.wiki_title for r in a.itertuples()}


ROUND = re.compile(r"Round \d+")
HEADING = re.compile(r"^(={2,4})\s*(.+?)\s*\1\s*$", re.M)


def parse_boxes(text: str, league: str, season: int) -> list[dict]:
    """Every game box, with the section heading it sits under. Regular-season games sit under
    "Round N" headings; preseason, cup and finals sections have other names [V: B1 data step,
    all 18 season articles]."""
    rows = []
    heads = [(m.start(), m.group(2).strip()) for m in HEADING.finditer(text)]
    starts = [m.start() for m in re.finditer(r"\{\{\s*basketballbox\b", text, re.I)]
    for start, body in zip(starts, templates(text, "basketballbox"), strict=True):
        section = next((h for pos, h in reversed(heads) if pos < start), "")
        p = params(body)
        # Editors sometimes write team1/team2 or score1/score2 for teamA/teamB, scoreA/scoreB.
        for new, old in (("teamA", "team1"), ("teamB", "team2"),
                         ("scoreA", "score1"), ("scoreB", "score2")):
            if not p.get(new) and p.get(old):
                p[new] = p[old]
        quarters = [score(p.get(f"Q{q}", "")) for q in (1, 2, 3, 4)]
        q_home = q_away = None
        if all(p.get(f"Q{q}") for q in (1, 2, 3, 4)):
            pairs = [re.findall(r"\d{1,3}", plain(p[f"Q{q}"])) for q in (1, 2, 3, 4)]
            if all(len(x) == 2 for x in pairs):
                q_home = sum(int(x[0]) for x in pairs)
                q_away = sum(int(x[1]) for x in pairs)
        time = re.search(r"\d{1,2}:\d{2}", p.get("time", ""))
        rows.append({
            "league": league, "season": season, "date": parse_date(p.get("date", "")),
            "time_local": time.group() if time else None,
            "home_link": link_target(p.get("teamA", "")),
            "away_link": link_target(p.get("teamB", "")),
            "home_name": plain(p.get("teamA", "")), "away_name": plain(p.get("teamB", "")),
            "home_pts": score(p.get("scoreA", "")), "away_pts": score(p.get("scoreB", "")),
            "home_reg": q_home, "away_reg": q_away,
            "overtime": any(k.upper().startswith("OT") or k.lower() == "overtime"
                            for k, v in p.items() if v.strip()),
            "has_quarters": all(q is not None for q in quarters),
            "section": section, "regular_season": bool(ROUND.fullmatch(section)),
        })
    return rows


def parse_grid(text: str) -> tuple[dict[str, str], dict[tuple[str, str], tuple[int, int]]]:
    """Team code -> link target, and (home code, away code) -> scores, from a results grid."""
    names = {c: link_target(v) or plain(v)
             for c, v in re.findall(r"name_([A-Za-z0-9]+)\s*=\s*(.+)", text)}
    cells = {}
    cell = r"match_([A-Za-z0-9]+)_([A-Za-z0-9]+)\s*=\s*([^\n|]*(?:\|[^\n|]*\]\])?)"
    for h, a, v in re.findall(cell, text):
        nums = re.findall(r"\d{2,3}", re.sub(r"\[\[[^|\]]*\|", "", v))
        if len(nums) >= 2:
            cells[(h, a)] = (int(nums[0]), int(nums[1]))
    return {c: n for c, n in names.items() if n}, cells


def build(offline: bool = False) -> tuple[pd.DataFrame, dict]:
    raw, grids = [], {}
    for league, years in SEASONS.items():
        for year in years:
            text = None
            for pattern in ARTICLES[league]:
                text = wikitext(pattern.format(s=season_label(year)),
                                refresh=(year == CURRENT) and not offline)
                if text is not None:
                    break
            if text is None:
                raise SystemExit(f"{league} {season_key(year)}: season article missing")
            raw += parse_boxes(text, league, year)
            if league == "EuroLeague":
                grid_text = wikitext(GRID_ARTICLE.format(s=season_label(year)),
                                     refresh=(year == CURRENT) and not offline) or ""
                grids[year] = parse_grid(grid_text)
    games = pd.DataFrame(raw)
    # Regular seasons only (plan, section 1): drop preseason, cup and finals sections.
    not_regular = {f"{lg} {season_key(int(s))}": sorted(set(g["section"]))
                   for (lg, s), g in games[~games["regular_season"]].groupby(["league", "season"])}
    games = games[games["regular_season"]].reset_index(drop=True)

    # Club IDs: link target -> current article title. An unlinked name goes through the alias
    # table, or else is tried as a title, but is accepted only if it lands on a club already
    # linked in the same league (a bare city name would otherwise land on the city).
    alias = aliases()
    for side in ("home", "away"):
        games[f"{side}_key"] = [lk if isinstance(lk, str) else alias.get((lg, nm)) or nm
                                for lk, lg, nm in zip(games[f"{side}_link"], games["league"],
                                                      games[f"{side}_name"], strict=True)]
    grid_keys = [n for names, _ in grids.values() for n in names.values()]
    keys = list(pd.concat([games["home_key"], games["away_key"]]).dropna()) + grid_keys
    titles = resolve(keys, offline)
    for side in ("home", "away"):
        games[f"{side}_title"] = games[f"{side}_key"].map(titles)
    linked = {lg: set(g.loc[g["home_link"].notna(), "home_title"])
              | set(g.loc[g["away_link"].notna(), "away_title"])
              for lg, g in games.groupby("league")}
    unknown = set()
    for side in ("home", "away"):
        unlinked_unknown = np.array([
            not isinstance(lk, str) and (lg, nm) not in alias and t not in linked[lg]
            for lk, lg, nm, t in zip(games[f"{side}_link"], games["league"],
                                     games[f"{side}_name"], games[f"{side}_title"], strict=True)])
        bad = games[f"{side}_title"].isna().to_numpy() | unlinked_unknown
        unknown |= {f"{lg}: {nm}" for lg, nm in zip(games.loc[bad, "league"],
                                                   games.loc[bad, f"{side}_name"], strict=True)}
    if unknown:
        raise SystemExit("Unmapped club names (add them to data/manual/"
                         "basketball_club_aliases.csv): " + "; ".join(sorted(unknown)))
    games["home_id"] = games["home_title"].map(club_id)
    games["away_id"] = games["away_title"].map(club_id)

    # Played games: both scores present. A forfeit (a team under 40 points) is not a result.
    scored = games["home_pts"].notna() & games["away_pts"].notna() & (
        games["home_pts"].fillna(0) + games["away_pts"].fillna(0) > 0)
    games["played"] = scored
    games["forfeit"] = scored & ((games["home_pts"] < 40) | (games["away_pts"] < 40))

    # EuroLeague cross-check against the results grid.
    games["check"] = np.where(games["league"] == "NBL", "no second source", "not in grid")
    for year, (names, cells) in grids.items():
        code_to_title = {c: titles.get(n) for c, n in names.items()}
        by_pair = {(code_to_title.get(h), code_to_title.get(a)): s for (h, a), s in cells.items()}
        sel = (games["league"] == "EuroLeague") & (games["season"] == year) & games["played"]
        for i in games.index[sel]:
            s = by_pair.get((games.at[i, "home_title"], games.at[i, "away_title"]))
            if s is None:
                continue
            same = s == (games.at[i, "home_pts"], games.at[i, "away_pts"])
            games.at[i, "check"] = "agrees" if same else f"grid says {s[0]}-{s[1]}"
    games["left_out"] = games["played"] & (
        games["forfeit"] | games["check"].str.startswith("grid says") | games["date"].isna())

    # Tip-off in UTC: EuroLeague from CET/CEST; NBL from the home club's zone [E] (checked below).
    local = pd.to_datetime(games["date"].fillna("") + " " + games["time_local"].fillna("00:00"),
                           errors="coerce")
    tips = []
    for i in games.index:
        zone = (EUROLEAGUE_ZONE if games.at[i, "league"] == "EuroLeague"
                else NBL_ZONES.get(games.at[i, "home_title"]))
        ok = zone and pd.notna(games.at[i, "time_local"]) and pd.notna(local[i])
        tips.append(pd.Timestamp(local[i]).tz_localize(zone).tz_convert("UTC") if ok else pd.NaT)
    games["tip_utc"] = pd.to_datetime(pd.Series(tips, index=games.index, dtype=object), utc=True)
    games["date"] = pd.to_datetime(games["date"]).dt.date
    games["game_id"] = [f"{lg}_{season_key(s).replace('/', '')}_{h}_{a}" for lg, s, h, a in
                        zip(games["league"], games["season"], games["home_id"], games["away_id"],
                            strict=True)]
    dupes = games["game_id"].duplicated(keep=False)
    if dupes.any():  # a pair meets twice at the same ground in one season: number them
        games.loc[dupes, "game_id"] += "_" + (games[dupes].groupby("game_id").cumcount() + 1
                                              ).astype(str)
    summary = summarise(games)
    summary["sections_left_out"] = not_regular
    return games, summary


def nbl_time_check(games: pd.DataFrame) -> dict:
    """Are NBL times the home venue's local time? If so, Perth (UTC+8) and Auckland (UTC+12
    or +13) home games show the same evening times as the east coast; if the times were all
    Sydney time, Perth games would show about two or three hours later."""
    nbl = games[(games["league"] == "NBL") & games["time_local"].notna()].copy()
    minutes = nbl["time_local"].str.split(":").map(lambda x: int(x[0]) * 60 + int(x[1]))
    med = minutes.groupby(nbl["home_title"]).median().sort_values()
    return {club: f"{int(m) // 60:02d}:{int(m) % 60:02d}" for club, m in med.items()}


def summarise(games: pd.DataFrame) -> dict:
    out: dict = {"generated_utc": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "source": "English Wikipedia (CC BY-SA 4.0)", "seasons": {}}
    for (lg, s), g in games.groupby(["league", "season"]):
        out["seasons"][f"{lg} {season_key(int(s))}"] = {
            "games": int(len(g)), "played": int(g["played"].sum()),
            "left_out": int(g["left_out"].sum()), "forfeits": int(g["forfeit"].sum()),
            "overtime": int((g["played"] & g["overtime"]).sum()),
            "with_quarters": int((g["played"] & g["home_reg"].notna()).sum()),
            "clubs": int(pd.concat([g["home_id"], g["away_id"]]).nunique()),
            "checks": {k: int(v) for k, v in g.loc[g["played"], "check"].value_counts().items()},
        }
    out["left_out_games"] = [
        {"game_id": r.game_id, "date": str(r.date), "home": r.home_title, "away": r.away_title,
         "box": f"{int(r.home_pts)}-{int(r.away_pts)}",
         "reason": "forfeit" if r.forfeit else "no date" if pd.isna(r.date) else r.check}
        for r in games[games["left_out"]].itertuples()]
    out["nbl_median_tip_by_home_club"] = nbl_time_check(games)
    out["clubs"] = {lg: sorted(set(g["home_title"]) | set(g["away_title"]))
                    for lg, g in games.groupby("league")}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached copies only")
    args = parser.parse_args(argv)
    games, summary = build(args.offline)
    GAMES.parent.mkdir(parents=True, exist_ok=True)
    games.to_parquet(GAMES, index=False)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in summary["seasons"].items():
        print(k, v)
    print("left out:", summary["left_out_games"])
    print("NBL median tip time by home club:", summary["nbl_median_tip_by_home_club"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
