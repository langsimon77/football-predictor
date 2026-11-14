"""Basketball phase B5, step 1: regular-season games for three more leagues, from each
league's home-language Wikipedia (CC BY-SA 4.0).

Lang asked (14 Nov 2026) for daily forecasts in ten more leagues at $0. Only these three
have a free source that lists coming games (reports/basketball_more_leagues_2026_11.md):

| League | Source | Coming games | Tip-off |
|---|---|---|---|
| ACB (Spain) | es: "Temporada regular de la ACB 2026-27" | the whole season | date and time |
| LBA (Italy) | it: "Serie A 2026-2027 (pallacanestro maschile)" | one round ahead | date only |
| ABA (Adriatic) | sr: "Јадранска лига у кошарци 2026/27." | rounds as listed | round dates only |

History for the tests: the same pages for 2022/23 to 2025/26, except the ACB, whose
Spanish pages start in 2025/26; its 2022/23 to 2024/25 games come from API-Basketball's
free plan (cached locally, never committed, never used by the daily run).

Club IDs: ACB from the club's link on es.wikipedia; LBA and ABA (plain names) and the API's
ACB names through data/manual/basketball_more_clubs.csv. A name not in that file stops the
build, and so does a season with the wrong number of clubs.

Games with a date but no time (LBA, ABA) get a stand-in tip-off at 00:00 local time on the
earliest day the game can be played, so a forecast always locks before the real tip-off.
Flag: date_only.

    uv run python basketball/more_leagues.py [--offline]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from audit_sample import CURRENT, params, plain, season_key, templates  # noqa: E402

import data as bb_data  # noqa: E402
from fp import ROOT  # noqa: E402
from fp.config import secret  # noqa: E402
from fp.ingest import http  # noqa: E402

SOURCE = "wikipedia_basketball_lang"
API_SOURCE = "apisports_basketball"
API_BASE = "https://v1.basketball.api-sports.io/"
CLUBS = ROOT / "data" / "manual" / "basketball_more_clubs.csv"
GAMES = ROOT / "data" / "processed" / "basketball" / "games_more.parquet"
SUMMARY = ROOT / "data" / "basketball" / "b5_data_summary.json"

LEAGUES = ("ACB", "LBA", "ABA")
NAMES = {"ACB": "Liga ACB (Spain)", "LBA": "Lega Basket Serie A (Italy)",
         "ABA": "ABA League (Adriatic)"}
ZONES = {"ACB": "Europe/Madrid", "LBA": "Europe/Rome", "ABA": "Europe/Belgrade"}
SEASONS = {"ACB": [2025, CURRENT], "LBA": [2022, 2023, 2024, 2025, CURRENT],
           "ABA": [2022, 2023, 2024, 2025, CURRENT]}
ACB_API = {"league": 117, "seasons": [2022, 2023, 2024]}
# Clubs per season (a check on the name mapping). ABA: one group of 14 (2022/23, 2023/24),
# one of 16 (2024/25), then two groups (2025/26 on).
CLUB_COUNT = {"ACB": {2022: 18, 2023: 18, 2024: 18, 2025: 18, 2026: 18},
              "LBA": {2022: 16, 2023: 16, 2024: 16, 2025: 16, 2026: 16}}
DASHES = chr(0x2013) + chr(0x2014) + "-"


def title(league: str, year: int) -> tuple[str, str]:
    yy = (year + 1) % 100
    return {"ACB": ("es", f"Temporada regular de la ACB {year}-{yy:02d}"),
            "LBA": ("it", f"Serie A {year}-{year + 1} (pallacanestro maschile)"),
            "ABA": ("sr", f"Јадранска лига у кошарци {year}/{yy:02d}.")}[league]


def wikitext(lang: str, page: str, refresh: bool) -> str | None:
    url = (f"https://{lang}.wikipedia.org/w/api.php?"
           + urlencode({"action": "parse", "page": page, "prop": "wikitext", "redirects": 1,
                        "format": "json", "formatversion": 2}))
    name = f"{lang}_" + re.sub(r"\W+", "_", page, flags=re.U).strip("_") + ".json"
    data = json.loads(http.fetch(url, SOURCE, name, refresh=refresh).read_text(encoding="utf-8"))
    return (data.get("parse") or {}).get("wikitext")


def season_date(year: int, month: int, day: int) -> date:
    """A day in the season that starts in `year`: August to December is `year`, the rest
    the year after."""
    return date(year if month >= 8 else year + 1, month, day)


def headings(text: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(2).strip()) for m in bb_data.HEADING.finditer(text)]


# ---------------------------------------------------------------- ACB (es.wikipedia)

FECHA = re.compile(r"\{\{\s*fecha\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\|\s*(\d{4})", re.I)


def parse_acb(text: str, season: int) -> list[dict]:
    rows = []
    heads = headings(text)
    starts = [m.start() for m in re.finditer(r"\{\{\s*Partido de baloncesto\b", text, re.I)]
    for start, body in zip(starts, templates(text, "Partido de baloncesto"), strict=True):
        p = params(body)
        d = FECHA.search(p.get("date", ""))
        time = re.search(r"\d{1,2}:\d{2}", p.get("time", ""))
        quarters = [re.findall(r"\d{1,3}", plain(p.get(f"Q{q}", ""))) for q in (1, 2, 3, 4)]
        reg = (sum(int(x[0]) for x in quarters), sum(int(x[1]) for x in quarters)) if all(
            len(x) == 2 for x in quarters) else (None, None)
        section = next((h for pos, h in reversed(heads) if pos < start), "")
        rows.append({
            "league": "ACB", "season": season,
            "date": date(int(d.group(3)), int(d.group(2)), int(d.group(1))) if d else None,
            "time_local": time.group() if time else None,
            "home_key": bb_data.link_target(p.get("teamA", "")),
            "away_key": bb_data.link_target(p.get("teamB", "")),
            "home_title": plain(p.get("teamA", "")), "away_title": plain(p.get("teamB", "")),
            "home_pts": _num(p.get("scoreA", "")), "away_pts": _num(p.get("scoreB", "")),
            "home_reg": reg[0], "away_reg": reg[1],
            "overtime": any(k.upper().startswith("OT") and v.strip() and v.strip() not in DASHES
                            for k, v in p.items()),
            "section": section.replace("Jornada", "Round"), "phase": "rs", "struck": False,
            "source": "es.wikipedia"})
    return rows


def _num(value: str) -> float | None:
    m = re.search(r"\d{1,3}", plain(value))
    return float(m.group()) if m else None


def acb_api_games(year: int, offline: bool) -> list[dict]:
    """API-Basketball's ACB regular season (numbered weeks; the play-offs are named)."""
    season = f"{year}-{year + 1}"
    url = f"{API_BASE}games?league={ACB_API['league']}&season={season}"
    name = f"games_{ACB_API['league']}_{season}.json"
    copies = http.cached_copies(API_SOURCE, name)
    if copies:
        path = copies[-1]
    elif offline:
        raise SystemExit(f"ACB {season_key(year)}: no cached API-Basketball file")
    else:
        path = http.fetch(url, API_SOURCE, name, refresh=False,
                          headers={"x-apisports-key": secret("API_FOOTBALL_KEY")})
    rows = []
    for g in json.loads(path.read_text(encoding="utf-8"))["response"]:
        if not str(g.get("week") or "").isdigit() or g["status"]["short"] not in ("FT", "AOT"):
            continue
        tip = pd.Timestamp(g["date"]).tz_convert("UTC")
        sh, sa = g["scores"]["home"], g["scores"]["away"]
        qh = [sh.get(f"quarter_{q}") for q in (1, 2, 3, 4)]
        qa = [sa.get(f"quarter_{q}") for q in (1, 2, 3, 4)]
        rows.append({
            "league": "ACB", "season": year, "date": tip.tz_convert(ZONES["ACB"]).date(),
            "time_local": tip.tz_convert(ZONES["ACB"]).strftime("%H:%M"),
            "home_key": None, "away_key": None,
            "home_title": g["teams"]["home"]["name"], "away_title": g["teams"]["away"]["name"],
            "home_pts": float(sh["total"]), "away_pts": float(sa["total"]),
            "home_reg": float(sum(qh)) if None not in qh else None,
            "away_reg": float(sum(qa)) if None not in qa else None,
            "overtime": g["status"]["short"] == "AOT", "section": f"Round {g['week']}",
            "phase": "rs", "struck": False, "source": "api-basketball"})
    return rows


# ---------------------------------------------------------------- LBA (it.wikipedia)

IT_MONTHS = {"set": 9, "ott": 10, "nov": 11, "dic": 12, "gen": 1, "feb": 2, "mar": 3,
             "apr": 4, "mag": 5, "giu": 6}
IT_DATE = re.compile(r"^\|[^|\n]*\|\s*(\d{1,2})\s*[º°]?\s+(" + "|".join(IT_MONTHS)
                     + r")[a-z]*\.?\s*(?:\|\|(.*))?$", re.I)  # 2022/23: game on the same line
IT_ROUND = re.compile(r"'''(\d+)ª giornata'''")
IT_GAME = re.compile(r"^\|\s*(<del>)?\s*([^|\[\]\n]+?)\s+-\s+([^|\[\]\n]+?)\s*(?:</del>)?\s*"
                     r"\|\|\s*(.*)$")


def parse_lba(text: str, season: int) -> list[dict]:
    start = text.find("Calendario ===")
    if start < 0:
        start = text.find("Calendario ==")
    ends = [i for i in (text.find("Classifica in divenire", start),
                        text.find("Punteggi in divenire", start),
                        text.find("Play-off", start)) if i > start]
    cal = text[start:min(ends)] if ends else text[start:]
    rows, day, rnd = [], None, None
    for line in cal.splitlines():
        if m := IT_ROUND.search(line):
            rnd, day = int(m.group(1)), None
            continue
        line = line.strip()
        if m := IT_DATE.match(line):
            day = season_date(season, IT_MONTHS[m.group(2).lower()], int(m.group(1)))
            if not m.group(3):
                continue
            line = "|" + m.group(3)
        if not (m := IT_GAME.match(line)):
            continue
        pts = re.findall(r"(\d{1,3})\s*-\s*(\d{1,3})", re.sub(r"https?://\S+", "", m.group(4)))
        rows.append({
            "league": "LBA", "season": season, "date": day, "time_local": None,
            "home_key": None, "away_key": None,
            "home_title": m.group(2).strip(), "away_title": m.group(3).strip(),
            "home_pts": float(pts[0][0]) if pts else None,
            "away_pts": float(pts[0][1]) if pts else None,
            "home_reg": None, "away_reg": None, "overtime": False,
            "section": f"Round {rnd}" if rnd else "", "phase": "rs",
            "struck": bool(m.group(1)) or "<del>" in m.group(4), "source": "it.wikipedia"})
    return rows


# ---------------------------------------------------------------- ABA (sr.wikipedia)

SR_MONTHS = {"сеп": 9, "окт": 10, "нов": 11, "дец": 12, "јан": 1, "феб": 2, "мар": 3,
             "апр": 4, "мај": 5, "јун": 6}
SR_ROUND = re.compile(r"'''(\d+)\. коло''',\s*([^<]+)<")
SR_GAME = re.compile(r"^\|\s*(.+?)\s+[" + DASHES + r"]\s+(.+?)\s*\|\|\s*(.*)$")
SR_LATIN = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш",
                    ["a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l", "lj", "m",
                     "n", "nj", "o", "p", "r", "s", "t", "ć", "u", "f", "h", "c", "č", "dž", "š"],
                    strict=True))
PHASES = {"Група А": ("a", "Group A"), "Група Б": ("b", "Group B"), "Топ 8": ("t8", "Top 8"),
          "Плеј-аут": ("po", "Play-out")}
SKIP_HEADS = {"Резултати", "Резултати по колима", "Табела"}
FILE_LINK = re.compile(r"\[\[(?:Датотека|Слика|File|Image):[^\]]*\]\]", re.I)
MOVED = re.compile(r"\(([^)]*\d[^)]*)\)\s*$")


def latin(text: str) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        t = SR_LATIN.get(low, ch)
        out.append(t.capitalize() if ch != low else t)
    return "".join(out)


def round_days(span: str, season: int) -> tuple[date | None, date | None]:
    """First and last day of a round, from spans such as '20<dash>22. сеп. 2024.' (20 to 22
    Sep), '30.9<dash>3.10.2022.' (30 Sep to 3 Oct) or '30. окт <dash> 3. нов. 2025.' (30 Oct to
    3 Nov), where <dash> is the em dash Wikipedia uses."""
    s = re.sub(r"\b(19|20)\d{2}\.?", "", span)  # years come from the season
    marks = []  # (position, month) of every month written in the span
    for m in re.finditer(r"(\d{1,2})\.(\d{1,2})(?!\d)", s):  # 30.9, 3.10
        marks.append((m.start(2), int(m.group(2))))
    for m in re.finditer("|".join(SR_MONTHS), s):
        marks.append((m.start(), SR_MONTHS[m.group()]))
    marks.sort()
    nums = [(m.start(), int(m.group())) for m in re.finditer(r"\d{1,2}", s)
            if not any(m.start() == pos for pos, _ in marks)]
    if not nums or not marks:
        return None, None

    def month_after(pos: int) -> int:
        return next((mo for p, mo in marks if p > pos), marks[-1][1])

    first, last = nums[0], nums[-1]
    return (season_date(season, month_after(first[0]), first[1]),
            season_date(season, month_after(last[0]), last[1]))


def parse_aba(text: str, season: int) -> list[dict]:
    heads = headings(text)
    rows = []
    for block in re.finditer(r"'''\d+\. коло'''.*?\|\}", text, re.S):
        head = SR_ROUND.search(block.group())
        if not head:
            continue
        pos = block.start()
        under = next((h for p, h in reversed(heads) if p < pos), "")
        if under != "Резултати по колима":
            continue  # play-off series and other tables
        phase_head = next((h for p, h in reversed(heads) if p < pos and h not in SKIP_HEADS), "")
        code, name = PHASES.get(phase_head, ("rs", ""))
        first, last = round_days(head.group(2), season)
        span = ("" if not (first and last) else f"{first.day} {first:%b}" if first == last
                else f"{first.day} to {last.day} {last:%b}" if first.month == last.month
                else f"{first.day} {first:%b} to {last.day} {last:%b}")
        label = ", ".join(x for x in (name, f"Round {head.group(1)}") if x)
        for line in block.group().splitlines():
            line = FILE_LINK.sub("", line).strip()
            m = SR_GAME.match(line)
            if not m or "коло" in line:
                continue
            day, home, away = first, m.group(1), m.group(2)
            moved = MOVED.search(away) or MOVED.search(home)
            if moved:  # a game played away from its round: '(25. сеп.)' or '(23.4)'
                day = round_days(moved.group(1), season)[0] or first
                home, away = MOVED.sub("", home), MOVED.sub("", away)
            pts = re.findall(r"(\d{1,3})\s*:\s*(\d{1,3})", m.group(3))
            rows.append({
                "league": "ABA", "season": season, "date": day, "time_local": None,
                "home_key": None, "away_key": None,
                "home_title": plain(home), "away_title": plain(away),
                "home_pts": float(pts[0][0]) if pts else None,
                "away_pts": float(pts[0][1]) if pts else None,
                "home_reg": None, "away_reg": None, "overtime": False,
                "section": f"{label} ({span})" if span and not moved else label,
                "phase": code, "struck": False, "source": "sr.wikipedia"})
    return rows


# ---------------------------------------------------------------- the table


def clubs() -> pd.DataFrame:
    return pd.read_csv(CLUBS, dtype=str, keep_default_na=False)


def build(offline: bool = False, history: bool = True) -> tuple[pd.DataFrame, dict]:
    """All three leagues. `history`: add the ACB's API-Basketball seasons (tests only)."""
    raw = []
    for league in LEAGUES:
        for year in SEASONS[league]:
            lang, page = title(league, year)
            text = wikitext(lang, page, refresh=(year == CURRENT) and not offline)
            if text is None:
                raise SystemExit(f"{league} {season_key(year)}: {lang}.wikipedia page missing")
            raw += {"ACB": parse_acb, "LBA": parse_lba, "ABA": parse_aba}[league](text, year)
        if league == "ACB" and history:
            for year in ACB_API["seasons"]:
                raw += acb_api_games(year, offline)
    games = pd.DataFrame(raw)

    # Club IDs and display names: one display name per club (data/manual/basketball_more_
    # clubs.csv), so the page shows "Kosner Baskonia" whatever the box calls it.
    table = clubs()
    by_name = {(r.league, r.name): r.club_id for r in table.itertuples()}
    shown = {(r.league, r.club_id): r.display for r in table.itertuples() if r.display}
    unknown = set()
    for side in ("home", "away"):
        ids = []
        for lg, key, name in zip(games["league"], games[f"{side}_key"],
                                 games[f"{side}_title"], strict=True):
            if isinstance(key, str) and key:  # ACB on es.wikipedia: the club's link
                ids.append(by_name.get((lg, key), bb_data.club_id(key)))
            elif (lg, name) in by_name:
                ids.append(by_name[(lg, name)])
            else:
                unknown.add(f"{lg}: {name}")
                ids.append(None)
        games[f"{side}_id"] = ids
        games[f"{side}_title"] = [shown.get((lg, i)) or (latin(n) if lg == "ABA" else n)
                                  for lg, i, n in zip(games["league"], ids,
                                                      games[f"{side}_title"], strict=True)]
    if unknown:
        raise SystemExit("Unmapped club names (add them to data/manual/basketball_more_clubs."
                         "csv): " + "; ".join(sorted(unknown)))

    scored = games["home_pts"].notna() & games["away_pts"].notna() & (
        games["home_pts"].fillna(0) + games["away_pts"].fillna(0) > 0)
    games["played"] = scored & ~games["struck"]
    games["forfeit"] = scored & ((games["home_pts"] < 40) | (games["away_pts"] < 40))
    games["check"] = "no second source"
    games["left_out"] = (scored & (games["forfeit"] | games["struck"])) | (
        games["played"] & games["date"].isna())
    games["regular_season"] = True

    # Tip-off: the listed local time (ACB), or a stand-in at 00:00 local on the first
    # possible day (LBA, ABA: date_only).
    games["date_only"] = games["time_local"].isna()
    tips = []
    for r in games.itertuples():
        if r.date is None or pd.isna(r.date):
            tips.append(pd.NaT)
            continue
        has_time = isinstance(r.time_local, str)
        if r.league == "ACB" and not has_time:
            tips.append(pd.NaT)  # ACB: a time comes later; lock only once it is known
            continue
        local = pd.Timestamp(f"{r.date} {r.time_local if has_time else '00:00'}")
        tips.append(local.tz_localize(ZONES[r.league]).tz_convert("UTC"))
    games["tip_utc"] = pd.to_datetime(pd.Series(tips, index=games.index, dtype=object), utc=True)
    games.loc[games["league"] == "ACB", "date_only"] = False
    games["date"] = pd.to_datetime(games["date"]).dt.date
    games["game_id"] = [
        f"{lg}_{season_key(s).replace('/', '')}_" + (f"{ph}_" if ph != "rs" else "") + f"{h}_{a}"
        for lg, s, ph, h, a in zip(games["league"], games["season"], games["phase"],
                                   games["home_id"], games["away_id"], strict=True)]
    games = mark_listed_twice(games)
    check_counts(games)
    return games, summarise(games)


def mark_listed_twice(games: pd.DataFrame) -> pd.DataFrame:
    """A pair listed twice at the same ground (an editing slip: the ACB's 2026/27 page lists
    Burgos v Breogán twice and Breogán v Burgos never [V: 14 Nov 2026]). The earliest keeps
    the plain ID, so fixing the slip later never renames a locked game; the later copies get
    "_2", "_3" and, in the ACB and the LBA (one game per ground per season), are not locked
    while the slip stays (suspect)."""
    games = games.sort_values(["league", "season", "date", "time_local"], na_position="last",
                              kind="stable").reset_index(drop=True)
    nth = games.groupby("game_id").cumcount()
    games["suspect"] = (nth > 0) & (games["phase"] == "rs") & games["league"].isin(["ACB", "LBA"])
    games.loc[nth > 0, "game_id"] += "_" + (nth[nth > 0] + 1).astype(str)
    return games


def check_counts(games: pd.DataFrame) -> None:
    """Each season must have the expected number of clubs: a second spelling of a club would
    add one."""
    bad = []
    for (lg, s), g in games.groupby(["league", "season"]):
        n = pd.concat([g["home_id"], g["away_id"]]).nunique()
        want = CLUB_COUNT.get(lg, {}).get(int(s))
        if want is not None and n != want:
            bad.append(f"{lg} {season_key(int(s))}: {n} clubs, expected {want}")
        if lg == "ABA":
            for ph, gp in g.groupby("phase"):
                c = pd.concat([gp["home_id"], gp["away_id"]]).value_counts()
                odd = list(c[c < c.max() // 2].index)
                if odd:
                    bad.append(f"ABA {season_key(int(s))} {ph}: odd clubs {odd}")
    if bad:
        raise SystemExit("Club count check failed: " + "; ".join(bad))


def summarise(games: pd.DataFrame) -> dict:
    out: dict = {"source": "es, it and sr Wikipedia (CC BY-SA 4.0); ACB 2022/23 to 2024/25 "
                           "from API-Basketball (tests only)", "seasons": {}}
    for (lg, s), g in games.groupby(["league", "season"]):
        out["seasons"][f"{lg} {season_key(int(s))}"] = {
            "games": int(len(g)), "played": int(g["played"].sum()),
            "left_out": int(g["left_out"].sum()), "with_time": int(g["time_local"].notna().sum()),
            "clubs": int(pd.concat([g["home_id"], g["away_id"]]).nunique()),
            "listed_twice": sorted(g.loc[g["suspect"], "game_id"]),
            "source": sorted(set(g["source"]))}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached copies only")
    args = parser.parse_args(argv)
    games, summary = build(args.offline)
    GAMES.parent.mkdir(parents=True, exist_ok=True)
    games.to_parquet(GAMES, index=False)
    SUMMARY.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in summary["seasons"].items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())

