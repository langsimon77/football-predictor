"""Task 5.8: the Europe pipeline's goals model against the bookmakers.

No free source has odds for the Europa League or the Conference League, so the comparison is
made where odds exist: top-division domestic matches in xgabora's Matches.csv (football-data.co.uk
odds), from 1 Jul 2023, with the same goals model refitted at the start of each month (the
settings used for the European forecasts). The bookmakers' chance is the average odds with the
margin removed (each 1/odds divided by their sum). Writes data/euro/benchmark_2026_10.json.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

import paths
import dc
from evalkit import boot, grids, ll3, markets  # same score grids as the experiments

warnings.filterwarnings("ignore")
cfg = json.load(open(str(paths.HERE / "final_cfg.json")))
df = pd.read_pickle(str(paths.WORK / "df.pkl"))
ev = df[(df.comp == "DOM") & (df.src == "mcsv") & (df.date >= "2023-07-01") & df.ohome.notna() & df.odraw.notna() & df.oaway.notna()].copy()
ev = ev[(ev.ohome > 1) & (ev.odraw > 1) & (ev.oaway > 1)]
ev["month"] = ev.date.str[:7]
lh, la, keep = [], [], []
for mo, g in ev.groupby("month"):
    m = dc.fit_dc(df, g.date.min(), half=cfg["half"], alpha=cfg["alpha"], cscale=cfg["cs"])
    for r in g.itertuples():
        a, b = dc.lam(m, r.H, r.A, eur=False)
        lh.append(a); la.append(b); keep.append(r.Index)
ev = ev.loc[keep]
y = np.where(ev.hg > ev.ag, 0, np.where(ev.hg == ev.ag, 1, 2))
P = markets(grids(np.array(lh), np.array(la), cfg.get("rho", -0.05)))["p"]
inv = 1 / ev[["ohome", "odraw", "oaway"]].values
Q = inv / inv.sum(1, keepdims=True)
lm, lq = ll3(P, y), ll3(Q, y)
by = {}
for cc, s in ev.groupby("hcc").groups.items():
    i = ev.index.get_indexer(s)
    by[cc] = {"n": int(len(i)), "model": round(float(lm[i].mean()), 4), "bookmakers": round(float(lq[i].mean()), 4)}
out = {"n": int(len(y)), "from": ev.date.min(), "to": ev.date.max(), "model": round(float(lm.mean()), 4), "bookmakers": round(float(lq.mean()), 4),
       "diff": boot(lm - lq), "margin": round(float((inv.sum(1) - 1).mean()), 4), "by_country": by,
       "note": "Domestic top divisions; no free odds exist for the Europa or Conference League."}
(paths.OUT / "benchmark_2026_10.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "by_country"}))
