"""Basketball upgrade step 2 (Lang: "Approved all", 17 Nov 2026): bookmaker prices from
The Odds API (https://the-odds-api.com, v4), as a benchmark first.

Each live run that has a game of a covered league tipping off within LOOKAHEAD hours, and no
snapshot of that league in the last MIN_GAP hours, fetches one snapshot (one region, three
markets: 3 credits per call [V: the API counts markets x regions per call]). Snapshots are
appended to ledger/basketball/odds_snapshots.parquet. The last snapshot before tip-off stands
in for the closing price.

The key comes from the ODDS_API_KEY environment variable (a GitHub Actions secret). With no
key the step does nothing and says so. The key is sent as the `apiKey` URL parameter, the only
way this API accepts it, and is never written to a file or a log.

Coverage: EuroLeague and NBL only [A: sport keys basketball_euroleague and basketball_nbl;
checked against /v4/sports on the first run with a key]. ACB, LBA and ABA are not offered.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from fp import ROOT

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORTS = {"EuroLeague": "basketball_euroleague", "NBL": "basketball_nbl"}
REGIONS = {"EuroLeague": "eu", "NBL": "au"}
MARKETS = "h2h,spreads,totals"
LOOKAHEAD = pd.Timedelta(hours=36)
MIN_GAP = pd.Timedelta(hours=10)
SNAPSHOTS = ROOT / "ledger" / "basketball" / "odds_snapshots.parquet"
SNAP_COLUMNS = ["fetched_utc", "league", "event_id", "commence_utc", "home_team", "away_team",
                "bookmaker", "market", "outcome", "price", "point"]
SHARP = "pinnacle"  # preferred when present: the sharpest widely quoted book [E]


# ---------------------------------------------------------------- fetch


def due(league: str, fixtures: pd.DataFrame, snaps: pd.DataFrame, now: pd.Timestamp) -> bool:
    soon = fixtures[(fixtures["league"] == league) & fixtures["tip_utc"].notna()
                    & (fixtures["tip_utc"] > now) & (fixtures["tip_utc"] <= now + LOOKAHEAD)]
    if soon.empty:
        return False
    mine = snaps[snaps["league"] == league] if len(snaps) else snaps
    return mine.empty or (now - pd.to_datetime(mine["fetched_utc"]).max()) >= MIN_GAP


def fetch(league: str, key: str, session=requests) -> list[dict]:
    params = {"apiKey": key, "regions": REGIONS[league], "markets": MARKETS,
              "oddsFormat": "decimal", "dateFormat": "iso"}
    r = session.get(BASE.format(sport=SPORTS[league]), params=params, timeout=60,
                    headers={"User-Agent": "football-predictor (non-commercial research)"})
    if r.status_code != 200:
        # never log the URL: it holds the key
        raise RuntimeError(f"The Odds API {league}: HTTP {r.status_code}")
    left = r.headers.get("x-requests-remaining")
    if left is not None:
        log.info("The Odds API credits left this month: %s", left)
    return r.json()


def flatten(events: list[dict], league: str, now: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                for oc in mk.get("outcomes", []):
                    price = oc.get("price")
                    if price is None or price <= 1.0:  # DECISIONS 24 Sep 2026: <= 1.0 is missing
                        continue
                    rows.append({"fetched_utc": now, "league": league, "event_id": ev["id"],
                                 "commence_utc": pd.Timestamp(ev["commence_time"]),
                                 "home_team": ev["home_team"], "away_team": ev["away_team"],
                                 "bookmaker": bk["key"], "market": mk["key"],
                                 "outcome": oc["name"], "price": float(price),
                                 "point": float(oc["point"]) if oc.get("point") is not None
                                 else np.nan})
    return pd.DataFrame(rows, columns=SNAP_COLUMNS)


def load(path: Path = SNAPSHOTS) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=SNAP_COLUMNS)


def append(new: pd.DataFrame, path: Path = SNAPSHOTS) -> pd.DataFrame:
    old = load(path)
    out = new if old.empty else pd.concat([old, new], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def run(fixtures: pd.DataFrame, now: pd.Timestamp, path: Path = SNAPSHOTS,
        session=requests, dry_run: bool = False) -> int:
    """Fetch what is due. Returns rows added. Never raises on an API problem: the forecasts
    must lock even if the odds feed is down."""
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        log.warning("odds: ODDS_API_KEY not set, no prices fetched")
        return 0
    snaps = load(path)
    added = 0
    for league in SPORTS:
        if not due(league, fixtures, snaps, now):
            continue
        try:
            rows = flatten(fetch(league, key, session), league, now)
        except Exception as exc:  # noqa: BLE001
            log.warning("odds: %s skipped (%s)", league, exc)
            continue
        if not dry_run and len(rows):
            snaps = append(rows, path)
        added += len(rows)
    return added


# ---------------------------------------------------------------- match and summarise


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b(bc|b\.c\.|kk|sk|s\.k\.|fc|basket|basketball|baloncesto|bàsquet|basquet|"
               r"club|the)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def name_score(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_events(snaps: pd.DataFrame, games: pd.DataFrame, min_score: float = 0.6,
                 max_hours: float = 6.0) -> pd.DataFrame:
    """event_id -> game_id, by league, tip-off within `max_hours` and both names alike.
    `games` needs league, game_id, tip_utc, home_name, away_name."""
    ev = snaps.drop_duplicates("event_id")[["event_id", "league", "commence_utc",
                                            "home_team", "away_team"]]
    out = []
    for e in ev.itertuples():
        cand = games[(games["league"] == e.league) & games["tip_utc"].notna()]
        cand = cand[(pd.to_datetime(cand["tip_utc"]) - pd.Timestamp(e.commence_utc)).abs()
                    <= pd.Timedelta(hours=max_hours)]
        best, score = None, 0.0
        for g in cand.itertuples():
            s = min(name_score(e.home_team, g.home_name), name_score(e.away_team, g.away_name))
            if s > score:
                best, score = g.game_id, s
        if best is not None and score >= min_score:
            out.append({"event_id": e.event_id, "game_id": best, "match_score": score})
    return pd.DataFrame(out, columns=["event_id", "game_id", "match_score"])


def market_view(snaps: pd.DataFrame, before: pd.Series | None = None) -> pd.DataFrame:
    """Per event: the market's home win chance (margin removed by normalising), spread line
    (home handicap) and total line, from the last snapshot (before tip-off if `before`, a
    Series event_id -> time, is given). Pinnacle when quoted, otherwise the median book."""
    s = snaps.copy()
    s["fetched_utc"] = pd.to_datetime(s["fetched_utc"], utc=True)
    if before is not None:
        s = s[s["fetched_utc"] < s["event_id"].map(before)]
    if s.empty:
        return pd.DataFrame(columns=["event_id", "fetched_utc", "p_home_mkt", "spread_home",
                                     "total_line", "books"])
    last = s.groupby("event_id")["fetched_utc"].transform("max")
    s = s[s["fetched_utc"] == last]
    rows = []
    for eid, e in s.groupby("event_id"):
        home = e["home_team"].iloc[0]
        books = e["bookmaker"].unique()
        use = e[e["bookmaker"] == SHARP] if SHARP in books else e
        p, sp, tl = [], [], []
        for _, b in use.groupby("bookmaker"):
            h2h = b[b["market"] == "h2h"]
            if len(h2h) == 2:
                inv = 1 / h2h["price"].to_numpy()
                p.append(inv[(h2h["outcome"] == home).to_numpy()].sum() / inv.sum())
            spr = b[(b["market"] == "spreads") & (b["outcome"] == home)]
            if len(spr):
                sp.append(float(spr["point"].iloc[0]))
            tot = b[(b["market"] == "totals")]
            if len(tot):
                tl.append(float(tot["point"].iloc[0]))
        rows.append({"event_id": eid, "fetched_utc": e["fetched_utc"].iloc[0],
                     "p_home_mkt": float(np.median(p)) if p else np.nan,
                     "spread_home": float(np.median(sp)) if sp else np.nan,
                     "total_line": float(np.median(tl)) if tl else np.nan,
                     "books": int(len(books))})
    return pd.DataFrame(rows)
