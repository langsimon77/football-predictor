"""Basketball B6 shadow forecast (data/audit/preregistration_basketball_b6_width_2026_11.md).

For EuroLeague and NBL games locked by the main run, a second row is locked under model
`bb_b6_shadow` in ledger/basketball/shadow_b6.parquet:
- winner chance, margin and total means as the main B1 models (all three markets, NBL included);
- widths from the method chosen in B6 tuning (data/basketball/b6_settings.json);
- margin, total and winner chance shifted by typed player availability (availability.py).
The main ledger and the Model Lab are unchanged until a B6 test passes.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import availability
import ledger_bb
import numpy as np
import pandas as pd
from backtest_width import B6_SETTINGS, current_sd, errors_and_means
from models import PointsSettings, points_expect, points_fit

from fp import ROOT

log = logging.getLogger(__name__)

SHADOW = ROOT / "ledger" / "basketball" / "shadow_b6.parquet"
MODEL = "bb_b6_shadow"
LEAGUES = ("EuroLeague", "NBL")
ALT_WINDOW = 200  # pre-registration amendment 2


def shadow_rows(main_rows: pd.DataFrame, played: dict[str, pd.DataFrame], settings: dict,
                av: pd.DataFrame | None = None) -> pd.DataFrame:
    """`main_rows`: rows just locked by live.forecast (ledger columns plus `date`).
    `played`: league -> played games, sorted (live.played_games)."""
    if main_rows.empty or not B6_SETTINGS.exists():
        return pd.DataFrame()
    av = availability.load() if av is None else av
    out = []
    for league, part in main_rows[main_rows["league"].isin(LEAGUES)].groupby("league"):
        st, g = settings[league], played[league]
        em = errors_and_means(g, st)
        day = g["date"].astype(str).to_numpy()
        widths = {}
        alt = {}
        for market, (x, mu, err, w0) in em.items():
            widths[market] = current_sd(league, market, x, mu, w0, day)
            known = err[~np.isnan(err)]  # amendment 2: W1 N=200, earlier games only
            alt[market] = (float(np.sqrt((known[-ALT_WINDOW:] ** 2).mean()))
                           if len(known) >= 60 else w0)
        e, pt = st["elo"], st["points"]
        fits = {}
        for r in part.itertuples():
            diff_m = float(np.log10(1 / r.p_home - 1) * -400) if 0 < r.p_home < 1 else 0.0
            margin = e["margin_scale_b"] * diff_m
            if r.date not in fits:
                fits[r.date] = points_fit(g, PointsSettings(pt["half_life"], pt["penalty"]), r.date)
            mh, ma = points_expect(fits[r.date], r.home_id, r.away_id)
            dm, dt, n = availability.adjust(league, str(r.date), r.home_name, r.away_name, av)
            diff_adj = diff_m + dm / e["margin_scale_b"]
            wm, sdm = widths["handicap"]
            wt, sdt = widths["total"]
            flags = json.loads(r.flags) + [f"b6_handicap:{wm.label()}", f"b6_total:{wt.label()}",
                                           f"availability_entries:{n}",
                                           f"b6_alt_margin_sd:{alt['handicap']:.3f}",
                                           f"b6_alt_total_sd:{alt['total']:.3f}"]
            row = {c: getattr(r, c) for c in ledger_bb.COLUMNS if hasattr(r, c)}
            row.update({"prediction_id": f"{r.game_id}:{MODEL}", "model_name": MODEL,
                        "p_home": float(1 / (1 + 10 ** (-diff_adj / 400))),
                        "margin_mean": float(margin + dm), "margin_sd": sdm,
                        "total_mean": float(mh + ma + dt), "total_sd": sdt,
                        "flags": json.dumps(flags)})
            out.append(row)
    return pd.DataFrame(out)


def lock(main_rows: pd.DataFrame, played: dict[str, pd.DataFrame], settings: dict,
         path: Path = SHADOW, dry_run: bool = False) -> int:
    """Never stops the main run: any problem is logged and skipped."""
    try:
        rows = shadow_rows(main_rows, played, settings)
        if len(rows) and not dry_run:
            ledger_bb.append(rows.drop(columns=[c for c in rows if c not in ledger_bb.COLUMNS]),
                             path)
        return len(rows)
    except Exception as exc:  # noqa: BLE001
        log.warning("shadow B6 skipped: %s", exc)
        return 0
