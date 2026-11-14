"""NBA cards for the Model Lab page, refreshed twice a day by a Claude routine.

Lang (14 Nov 2026): "automate NBA. Make it refresh twice a day." The page's NBA cards come
from a pipeline built inside the page (its pipe/predict_bb.py and pipe/bbmodel.py, 8 Nov 2026)
and were refreshed by hand. This file ports its NBA part unchanged in method:

- data: the NBA schedule files of sportsdataverse/hoopR-nba-data on GitHub (updated once a
  day, about 12:35 UTC), five seasons;
- model: team ratings fitted by time-weighted ridge least squares on point margins (half-life
  75 days, ridge 1) with home edge and back-to-back effects, plus attack and defence ratings
  for points; win chance = normal CDF(margin / spread);
- output: the page's row shape (id "NBA_202627_<game id>", kickoff, p, margin, total, b2b).

Nothing here is committed: the routine writes the JSON to the page's database (document
live/nba). The NBA is not part of this repository's tested, locked forecasts (B0-D2 and B0-D4
stay as they are); the test figures shown on the page are that pipeline's own.

    python3 basketball/nba_page.py --out /tmp/nba_feed.json [--cache DIR] [--now ISO]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

SCHEDULE = ("https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/main/nba/"
            "schedules/parquet/nba_schedule_{y}.parquet")
COLUMNS = ["game_id", "date", "season", "season_type", "neutral_site", "home_display_name",
           "away_display_name", "home_score", "away_score", "status_type_completed"]
HALF_LIFE, RIDGE = 75.0, 1.0
SIG_M, SIG_T = 1.06, 1.05  # the pipeline's widening of the spreads, from its hold-out residuals
HORIZON_DAYS = 8
LOCK_HOURS = 36  # the pipeline marks a game "locked" within 36 hours of tip-off
# The pipeline's own test (pipe/predict_bb.py, 8 Nov 2026), shown on the page as before.
TEST = {"games": 1423, "acc": 0.677, "ll": 0.604, "base_ll": 0.693, "market_ll": 0.575,
        "market_acc": 0.688, "seasons": "2025/26 and 2026/27 to 3 Nov"}


def season_end_year(now: pd.Timestamp) -> int:
    return now.year + 1 if now.month >= 8 else now.year


def download(cache: Path, now: pd.Timestamp) -> list[Path]:
    cache.mkdir(parents=True, exist_ok=True)
    last = season_end_year(now)
    paths = []
    for y in range(last - 4, last + 1):
        p = cache / f"nba_schedule_{y}.parquet"
        req = urllib.request.Request(SCHEDULE.format(y=y),
                                     headers={"User-Agent": "football-predictor (Model Lab NBA)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                p.write_bytes(r.read())
        except OSError as e:  # a missing future season is fine; a missing current one is not
            if y == last:
                raise SystemExit(f"NBA schedule {y} not downloaded: {e}") from e
            continue
        paths.append(p)
    return paths


def games(paths: list[Path]) -> pd.DataFrame:
    s = pd.concat([pd.read_parquet(p, columns=COLUMNS) for p in paths], ignore_index=True)
    s = s[s["season_type"].isin([2, 3])]  # regular season and play-offs
    count = pd.concat([s["home_display_name"], s["away_display_name"]]).value_counts()
    real = set(count[count > 150].index)  # drops All-Star and exhibition teams
    s = s[s["home_display_name"].isin(real) & s["away_display_name"].isin(real)]
    done = s["status_type_completed"].astype(bool).to_numpy()
    return pd.DataFrame({
        "gid": s["game_id"].astype(str).to_numpy(), "date": s["date"].to_numpy(),
        "home": s["home_display_name"].to_numpy(), "away": s["away_display_name"].to_numpy(),
        "hs": np.where(done, s["home_score"].astype(float), np.nan),
        "as_": np.where(done, s["away_score"].astype(float), np.nan),
        "neutral": s["neutral_site"].fillna(False).astype(bool).to_numpy()})


def prep(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by tip-off and add each team's days of rest (back-to-back: under 1.6 days)."""
    d = df.copy()
    d["t"] = pd.to_datetime(d["date"], utc=True)
    d = d.sort_values("t").reset_index(drop=True)
    last: dict[str, pd.Timestamp] = {}
    rh, ra = [], []
    for r in d.itertuples():
        for team, out in ((r.home, rh), (r.away, ra)):
            p = last.get(team)
            out.append(9.0 if p is None else (r.t - p).total_seconds() / 86400)
        last[r.home] = r.t
        last[r.away] = r.t  # rest follows the schedule, played or not
    d["rest_h"] = np.clip(rh, 0, 9)
    d["rest_a"] = np.clip(ra, 0, 9)
    d["b2b_h"] = (d["rest_h"] < 1.6).astype(float)
    d["b2b_a"] = (d["rest_a"] < 1.6).astype(float)
    return d


def fit(train: pd.DataFrame, now: pd.Timestamp, half: float = HALF_LIFE,
        lam: float = RIDGE) -> dict:
    """Ratings from games played before `now`, weights halving every `half` days."""
    g = train[(train["t"] < now) & train["hs"].notna()]
    age = (now - g["t"]).dt.total_seconds().to_numpy() / 86400
    w = 0.5 ** (age / half)
    teams = sorted(set(g["home"]) | set(g["away"]))
    ix = {k: i for i, k in enumerate(teams)}
    n = len(teams)
    h = g["home"].map(ix).to_numpy()
    a = g["away"].map(ix).to_numpy()
    neutral = g["neutral"].to_numpy().astype(float)
    m = len(g)
    x = np.zeros((m, n + 3))
    x[np.arange(m), h] = 1
    x[np.arange(m), a] = -1
    x[:, n] = 1 - neutral
    x[:, n + 1] = g["b2b_h"].to_numpy()
    x[:, n + 2] = g["b2b_a"].to_numpy()
    y = (g["hs"] - g["as_"]).to_numpy()
    wx = x * w[:, None]
    ridge = np.eye(n + 3) * lam
    ridge[n:, n:] = 0
    ridge[n:, n:] += 1e-6 * np.eye(3)
    beta = np.linalg.solve(x.T @ wx + ridge, wx.T @ y)
    res = y - x @ beta
    sig = float(np.sqrt(np.sum(w * res ** 2) / np.sum(w)))
    xp = np.zeros((2 * m, 2 * n + 2))
    yp = np.r_[g["hs"].to_numpy(), g["as_"].to_numpy()]
    wp = np.r_[w, w]
    r1 = np.arange(m)
    r2 = r1 + m
    xp[r1, h] = 1
    xp[r1, n + a] = -1
    xp[r1, 2 * n] = 1 - neutral
    xp[:, 2 * n + 1] = 1
    xp[r2, a] = 1
    xp[r2, n + h] = -1
    ridge_p = np.eye(2 * n + 2) * lam
    ridge_p[2 * n:, 2 * n:] = 1e-6 * np.eye(2)
    bp = np.linalg.solve(xp.T @ (xp * wp[:, None]) + ridge_p, (xp * wp[:, None]).T @ yp)
    tot_res = (g["hs"] + g["as_"]).to_numpy() - ((xp[r1] @ bp) + (xp[r2] @ bp))
    sig_t = float(np.sqrt(np.sum(w * tot_res ** 2) / np.sum(w)))
    return {"ix": ix, "n": n, "beta": beta, "bp": bp, "sig": sig, "sig_t": sig_t, "games": m}


def ncdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def predict(mod: dict, home: str, away: str, neutral: bool = False, b2b_h: float = 0.0,
            b2b_a: float = 0.0) -> dict:
    ix, n, b, bp = mod["ix"], mod["n"], mod["beta"], mod["bp"]
    rh = b[ix[home]] if home in ix else 0.0
    ra = b[ix[away]] if away in ix else 0.0
    mu = rh - ra + b[n] * (0 if neutral else 1) + b[n + 1] * b2b_h + b[n + 2] * b2b_a
    oh = bp[ix[home]] if home in ix else 0.0
    dh = bp[n + ix[home]] if home in ix else 0.0
    oa = bp[ix[away]] if away in ix else 0.0
    da = bp[n + ix[away]] if away in ix else 0.0
    ph = bp[2 * n + 1] + oh - da + bp[2 * n] * (0 if neutral else 1)
    pa = bp[2 * n + 1] + oa - dh
    return {"p": ncdf(mu / mod["sig"]), "margin": float(mu), "sig": mod["sig"],
            "total": float(ph + pa), "sig_t": mod["sig_t"]}


def feed(d: pd.DataFrame, now: pd.Timestamp) -> dict:
    mod = fit(d, now)
    end = now + pd.Timedelta(days=HORIZON_DAYS)
    up = d[d["hs"].isna() & (d["t"] > now) & (d["t"] < end)]
    rows = []
    for r in up.itertuples():
        pr = predict(mod, r.home, r.away, r.neutral, r.b2b_h, r.b2b_a)
        k = r.t.strftime("%Y-%m-%dT%H:%MZ")
        rows.append({"id": "NBA_202627_" + r.gid, "lg": "NBA", "round": "Regular season",
                     "kickoff": k, "date": k[:10], "h": r.home, "a": r.away,
                     "locked": bool((r.t - now).total_seconds() < LOCK_HOURS * 3600),
                     "p": round(pr["p"], 4),
                     "margin": [round(pr["margin"], 1), round(pr["sig"] * SIG_M, 1)],
                     "total": [round(pr["total"], 1), round(pr["sig_t"] * SIG_T, 1)],
                     "b2b": [int(r.b2b_h), int(r.b2b_a)]})
    as_of = now.strftime("%Y-%m-%d %H:%M UTC")
    last = d.loc[d["hs"].notna(), "t"].max()
    note = ("Tuned on 2,628 games of 2023/24 and 2024/25, then tested on later games it had not "
            f"seen. Refreshed automatically twice a day; this refresh {as_of}, with results to "
            f"{last:%d %b}.")
    return {"as_of": as_of, "rows": rows, "test": {"NBA": {**TEST, "note": note}},
            "fit_games": mod["games"],
            "source": "sportsdataverse/hoopR-nba-data schedules; football-predictor "
                      "basketball/nba_page.py"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("/tmp/nba_schedules"))
    ap.add_argument("--now", help="pretend the run happens at this UTC time (tests)")
    ap.add_argument("--offline", action="store_true", help="use the files already in --cache")
    args = ap.parse_args(argv)
    now = pd.Timestamp(args.now, tz="UTC") if args.now else pd.Timestamp.now(tz="UTC")
    paths = (sorted(args.cache.glob("nba_schedule_*.parquet")) if args.offline
             else download(args.cache, now))
    out = feed(prep(games(paths)), now)
    if not out["rows"]:
        raise SystemExit("no NBA games in the next 8 days: nothing written")
    args.out.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(out['rows'])} NBA games, as of {out['as_of']}, "
          f"fitted on {out['fit_games']} games")
    return 0


if __name__ == "__main__":
    sys.exit(main())
