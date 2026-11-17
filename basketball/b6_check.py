"""Basketball B6: progress of the pre-registered live tests
(data/audit/preregistration_basketball_b6_width_2026_11.md, sections 4 and 6).

    uv run python basketball/b6_check.py      # writes reports/basketball_b6_progress.md

Read-only: it never changes a ledger. A test is reported only once its game count is reached.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ledger_bb  # noqa: E402
import odds  # noqa: E402
from backtest import interval  # noqa: E402
from shadow import SHADOW  # noqa: E402
from width import Width, crps, inside_90  # noqa: E402

from fp import ROOT  # noqa: E402

MAIN = ROOT / "ledger" / "basketball" / "predictions.parquet"
RESULTS = ROOT / "ledger" / "basketball" / "results.parquet"
OUT = ROOT / "reports" / "basketball_b6_progress.md"
NEED_WIDTH, NEED_ODDS = 100, 100


def _width(flags: str, market: str) -> Width:
    for f in flags.strip("[]").replace('"', "").split(", "):
        if f.startswith(f"b6_{market}:"):
            parts = f.split(":", 1)[1].split()
            if parts[0] == "W0":
                return Width("W0")
            n = int(parts[1].split("=")[1])
            df = float(parts[2].split("=")[1]) if len(parts) > 2 else 0.0
            return Width(parts[0], n, df)
    return Width("W0")


def _ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def check() -> list[str]:
    res = pd.read_parquet(RESULTS) if RESULTS.exists() else pd.DataFrame()
    sh = ledger_bb.load(SHADOW)
    main = ledger_bb.load(MAIN)
    lines = ["# Basketball B6: live test progress", ""]
    if res.empty or sh.empty:
        return lines + ["No shadow game has a result yet."]
    res = res.drop_duplicates("game_id", keep="last")
    s = sh.merge(res, on="game_id")
    for league, part in s.groupby("league"):
        n = len(part)
        lines.append(f"## {league}: {n} shadow games with a result")
        day = part["tip_utc"].astype(str).str[:10].to_numpy()
        for market, xcol, mcol, scol in (("handicap", "margin", "margin_mean", "margin_sd"),
                                         ("total", "total", "total_mean", "total_sd")):
            x = (part["home_pts"] - part["away_pts"]) if xcol == "margin" else (
                part["home_pts"] + part["away_pts"])
            x = x.astype(float).to_numpy()
            mu, sd = part[mcol].to_numpy(float), part[scol].to_numpy(float)
            w = _width(part["flags"].iloc[-1], market)
            cover = float(inside_90(x, mu, sd, w).mean())
            msg = f"- {market} ({w.label()}): 90% range caught {cover:.1%}"
            if n >= NEED_WIDTH:
                mm = main.drop_duplicates("game_id").set_index("game_id")
                base_sd = part["game_id"].map(mm[scol]).to_numpy(float)
                ok = ~np.isnan(base_sd)
                if ok.any():
                    d = (crps(x[ok], mu[ok], sd[ok], w)
                         - crps(x[ok], mu[ok], base_sd[ok], Width("W0")))
                    iv = interval(d, day[ok])
                    passed = 0.86 <= cover <= 0.94 and iv["high"] < 0.10
                    msg += (f"; CRPS minus W0 {iv['mean']:+.3f} (upper {iv['high']:+.3f}): "
                            f"{'PASS' if passed else 'FAIL'}")
            else:
                msg += f"; test waits for {NEED_WIDTH} games"
            lines.append(msg)
        lines.append("")
    snaps = odds.load()
    if len(snaps) and len(main):
        games = main.drop_duplicates("game_id")[["game_id", "league", "tip_utc", "home_name",
                                                 "away_name"]]
        m = odds.match_events(snaps, games)
        tip = m.set_index("event_id")["game_id"].map(games.set_index("game_id")["tip_utc"])
        view = odds.market_view(snaps, before=tip).merge(m, on="event_id")
        j = view.merge(main.drop_duplicates("game_id"), on="game_id").merge(res, on="game_id")
        lines.append(f"## Odds benchmark: {len(j)} locked games with a pre-tip-off price")
        for league, part in j.groupby("league"):
            y = (part["home_pts"] > part["away_pts"]).to_numpy(float)
            ok = part["p_home_mkt"].notna().to_numpy()
            if ok.sum() < NEED_ODDS:
                lines.append(f"- {league}: {ok.sum()} games, waits for {NEED_ODDS}")
                continue
            pm, pk = part["p_home"].to_numpy(float)[ok], part["p_home_mkt"].to_numpy(float)[ok]
            yy = y[ok]
            days = part["tip_utc"].astype(str).str[:10].to_numpy()[ok]
            iv = interval(_ll(pm, yy) - _ll(pk, yy), days)
            lines.append(f"- {league}: model minus market log loss {iv['mean']:+.4f} "
                         f"(range {iv['low']:+.4f} to {iv['high']:+.4f})")
    else:
        lines.append("## Odds benchmark: no prices yet (needs the ODDS_API_KEY secret).")
    return lines


if __name__ == "__main__":
    text = "\n".join(check()) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
