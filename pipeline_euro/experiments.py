"""Tasks 5.3 to 5.7: the experiments pre-registered in data/audit/preregistration_euro_2026_10.md.

Reads the walk-forward backtests (bt.py) and the match table; writes data/euro/experiments_2026_10.json
and reports/euro_experiments_2026_10.md. Every number is out of sample: models refitted monthly,
calibrators and stackers fitted on the tuning window (before 1 Jul 2025) only.
"""
from __future__ import annotations

import json
import math
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

import paths
import dc
import elo
import link
from evalkit import B, I, J, MAXG, boot, grids, ll3, llb, markets, rng

warnings.filterwarnings("ignore")
SPLIT, W, RHO0 = "2025-07-01", 0.2, -0.05
HALVES, ALPHAS = [180.0, 270.0, 365.0, 540.0, 730.0], [0.0001, 0.0003, 0.001]
REF = (365.0, 0.0003)

df = pd.read_pickle(str(paths.WORK / "df.pkl"))
y_all = np.where(df.hg > df.ag, 0, np.where(df.hg == df.ag, 1, 2))
ep = json.load(open(str(paths.HERE / "elo_params.json")))


def load(half, alpha):
    b = pd.read_pickle(str(paths.WORK / f"bt_dc_{half}_{alpha}_3.0.pkl")).set_index("idx").sort_index()
    return b


ref = load(*REF)
idx = ref.index.values
y = y_all[idx]
dates = df.date.values[idx]
months = pd.Series(dates).str[:7].values
tune, hold = dates < SPLIT, dates >= SPLIT
hg, ag = df.hg.values[idx].astype(int), df.ag.values[idx].astype(int)
tot = hg + ag
comp = df.comp.values[idx]
# Elo, as the pipeline runs it.
pre, _, _, _ = elo.run_elo(df, K0=ep["K0"], HE=ep["HE"], newK=ep["newK"], HD=ep["HD"], gap_reg=0.0)
trm = ((df.main == 1) & (df.date < "2023-07-01")).values
lp = link.ol_fit(pre[trm], y_all[trm])
Pel = link.ol_pred(lp, pre[idx])


def blend(Pdc, Pe=Pel):
    return W * Pe + (1 - W) * Pdc


def fitted_rho(lh, la):
    """rho for each month by maximum likelihood on the scorelines of the forecasts made before
    that month (out of sample; -0.05 until 150 such matches exist)."""
    out = np.full(len(lh), RHO0)
    for m in sorted(set(months)):
        past = months < m
        if past.sum() < 150:
            continue
        h, a, l1, l2 = np.minimum(hg[past], MAXG), np.minimum(ag[past], MAXG), lh[past], la[past]
        f = lambda r: -np.log(grids(l1, l2, r)[np.arange(len(h)), h, a]).sum()  # noqa: E731
        out[months == m] = minimize_scalar(f, bounds=(-0.3, 0.3), method="bounded").x
    return out


def rho_grids(lh, la, rho):
    if np.isscalar(rho):
        return grids(lh, la, rho)
    M = np.empty((len(lh), MAXG + 1, MAXG + 1))
    for r in np.unique(rho):
        s = rho == r
        M[s] = grids(lh[s], la[s], r)
    return M


refM = markets(grids(ref.lh.values, ref.la.values, RHO0))
refP = blend(refM["p"])
ref_ll = ll3(refP, y)
summary = {"reference": {"all": round(float(ref_ll.mean()), 4), "tune": round(float(ref_ll[tune].mean()), 4),
                         "hold": round(float(ref_ll[hold].mean()), 4), "n": int(len(y)), "n_tune": int(tune.sum()), "n_hold": int(hold.sum())}}
print("reference", summary["reference"])

# 1. Goals model settings and fitted rho (5.3).
grid = []
for half in HALVES:
    for alpha in ALPHAS:
        try:
            b = load(half, alpha)
        except FileNotFoundError:
            continue
        assert (b.index.values == idx).all()
        for mode in ("fixed", "fitted"):
            rho = RHO0 if mode == "fixed" else fitted_rho(b.lh.values, b.la.values)
            P = blend(markets(rho_grids(b.lh.values, b.la.values, rho))["p"])
            l = ll3(P, y)
            grid.append({"half": half, "alpha": alpha, "rho": mode, "tune": round(float(l[tune].mean()), 4), "hold": round(float(l[hold].mean()), 4),
                         "all": round(float(l.mean()), 4), "_ll": l, "_rho": rho})
best = min(grid, key=lambda g: g["tune"])
e1 = {"grid": [{k: v for k, v in g.items() if not k.startswith("_")} for g in grid], "chosen": {k: v for k, v in best.items() if not k.startswith("_")},
      "hold_diff": boot(best["_ll"][hold] - ref_ll[hold]),
      "rho_fitted_range": [round(float(np.min(best["_rho"])), 3), round(float(np.max(best["_rho"])), 3)] if best["rho"] == "fitted" else None}
print("5.3", e1["chosen"], e1["hold_diff"])

# 2. Totals calibration (5.4).
k25 = tot >= 3
o25 = refM["o25"]
shift = {}
for c in sorted(set(comp)):
    s = tune & (comp == c)
    shift[c] = math.log(tot[s].sum() / (ref.lh.values[s] + ref.la.values[s]).sum()) if s.sum() >= 30 else 0.0
d = np.array([shift.get(c, 0.0) for c in comp])
Msh = markets(grids(ref.lh.values * np.exp(d), ref.la.values * np.exp(d), RHO0))
iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98).fit(o25[tune], k25[tune].astype(float))
o25_iso = iso.predict(o25)
base_ll = llb(o25, k25)
e2 = {"mean_pred_tune": round(float(o25[tune].mean()), 3), "actual_tune": round(float(k25[tune].mean()), 3),
      "mean_pred_hold": round(float(o25[hold].mean()), 3), "actual_hold": round(float(k25[hold].mean()), 3),
      "reference_hold": round(float(base_ll[hold].mean()), 4),
      "shift": {c: round(v, 4) for c, v in shift.items()},
      "shift_hold": round(float(llb(Msh["o25"], k25)[hold].mean()), 4), "shift_hold_diff": boot(llb(Msh["o25"], k25)[hold] - base_ll[hold]),
      "shift_1x2_hold_diff": boot(ll3(blend(Msh["p"]), y)[hold] - ref_ll[hold]),
      "isotonic_hold": round(float(llb(o25_iso, k25)[hold].mean()), 4), "isotonic_hold_diff": boot(llb(o25_iso, k25)[hold] - base_ll[hold]),
      "other_lines_hold": {k: {"pred": round(float(refM[k][hold].mean()), 3), "actual": round(float(v[hold].mean()), 3)}
                           for k, v in (("o15", tot >= 2), ("o35", tot >= 4), ("btts", (hg > 0) & (ag > 0)))}}
print("5.4", e2["shift_hold_diff"], e2["isotonic_hold_diff"])

# 3. Home, draw, away calibration (5.5).
L = np.log(np.clip(refP, 1e-9, 1))
def temp(T, P):  # noqa: E302
    Q = np.exp(np.log(np.clip(P, 1e-9, 1)) / T)
    return Q / Q.sum(1, keepdims=True)
T = minimize_scalar(lambda t: ll3(temp(t, refP[tune]), y[tune]).mean(), bounds=(0.5, 2.0), method="bounded").x
dir_lr = LogisticRegression(C=100.0, max_iter=2000).fit(L[tune], y[tune])
P_dir = dir_lr.predict_proba(L)
e3 = {"temperature": round(float(T), 3), "temperature_hold_diff": boot(ll3(temp(T, refP), y)[hold] - ref_ll[hold]),
      "dirichlet_hold_diff": boot(ll3(P_dir, y)[hold] - ref_ll[hold])}
print("5.5", e3)

# 4. Stacked blend with data depth (5.6).
pos = defaultdict(list)
for t, h, a in zip(df.t.values, df.H.values, df.A.values):
    pos[h].append(t); pos[a].append(t)
pos = {k: np.array(v) for k, v in pos.items()}
def recent(team, t):  # noqa: E302
    v = pos.get(team, np.array([], dtype="datetime64[ns]"))
    return int(((v < t) & (v >= t - np.timedelta64(365, "D"))).sum())
tt, H_, A_ = df.t.values[idx], df.H.values[idx], df.A.values[idx]
nH = np.array([recent(H_[i], tt[i]) for i in range(len(idx))]); nA = np.array([recent(A_[i], tt[i]) for i in range(len(idx))])
X = np.column_stack([np.log(np.clip(refM["p"], 1e-9, 1)), np.log(np.clip(Pel, 1e-9, 1)), np.log1p(nH), np.log1p(nA)])
st = LogisticRegression(C=1.0, max_iter=3000).fit(X[tune], y[tune])
P_st = st.predict_proba(X)
# Walk-forward version over all 1,199: refitted monthly on earlier months (reference until 300).
P_wf = refP.copy()
for m in sorted(set(months)):
    past, now = months < m, months == m
    if past.sum() >= 300:
        P_wf[now] = LogisticRegression(C=1.0, max_iter=3000).fit(X[past], y[past]).predict_proba(X[now])
e4 = {"hold_diff": boot(ll3(P_st, y)[hold] - ref_ll[hold]), "walk_forward_all": round(float(ll3(P_wf, y).mean()), 4),
      "walk_forward_all_diff": boot(ll3(P_wf, y) - ref_ll), "beats_0_9393": bool(ll3(P_wf, y).mean() < 0.9393)}
print("5.6", e4)

# 5. New teams: Elo start from the goals model's league strength (5.7).
thin = np.minimum(nH, nA) < 15
fits = {}
for d0 in pd.date_range("2022-01-01", "2026-10-01", freq="6MS").strftime("%Y-%m-%d"):
    m = dc.fit_dc(df, d0, half=REF[0], alpha=REF[1], cscale=3.0)
    fits[d0] = {c: float(m["attc"][i] - m["dec"][i]) for c, i in m["ci"].items()}
def country_strength(cc, when):  # noqa: E302
    keys = [k for k in fits if k <= when]
    return fits[keys[-1]].get(cc) if keys else None
try:
    pre_v, *_ = elo.run_elo(df, K0=ep["K0"], HE=ep["HE"], newK=ep["newK"], HD=ep["HD"], gap_reg=0.0,
                            init_fn=lambda team, cc, R, N, date: None)
    has_hook = True
except TypeError:
    has_hook = False
e5 = {"has_hook": has_hook}
if has_hook:
    cache = {}
    def league_prior(team, cc, R, N, date):
        """Elo of an established club in a league of this strength (a straight line fitted on
        established clubs: Elo against their league's goals-model strength), minus 75."""
        s = country_strength(cc, date)
        keys = [k for k in fits if k <= date]
        if s is None or not keys:
            return None
        ck = (keys[-1], len(R) // 250)
        if ck not in cache:
            est = [(R[t], country_strength(t.split(":")[0], date)) for t in R if N[t] >= 10]
            est = [(r, s2) for r, s2 in est if s2 is not None]
            cache[ck] = np.polyfit([e[1] for e in est], [e[0] for e in est], 1) if len(est) >= 30 else None
        return None if cache[ck] is None else float(np.polyval(cache[ck], s)) - 75.0
    pre_new, *_ = elo.run_elo(df, K0=ep["K0"], HE=ep["HE"], newK=ep["newK"], HD=ep["HD"], gap_reg=0.0, init_fn=league_prior)
    lp_new = link.ol_fit(pre_new[trm], y_all[trm])
    P_new = blend(refM["p"], link.ol_pred(lp_new, pre_new[idx]))
    l_new = ll3(P_new, y)
    e5.update({"thin_n_hold": int((thin & hold).sum()), "thin_hold_ref": round(float(ref_ll[thin & hold].mean()), 4), "thin_hold_new": round(float(l_new[thin & hold].mean()), 4),
               "thin_hold_diff": boot(l_new[thin & hold] - ref_ll[thin & hold]), "all_hold_diff": boot(l_new[hold] - ref_ll[hold])})
print("5.7", e5)

# Holm across the five pre-registered comparisons (one primary test each).
tests = {"5.3 settings and fitted rho": e1["hold_diff"], "5.4 totals calibration (best of two, over 2.5)": min(e2["shift_hold_diff"], e2["isotonic_hold_diff"], key=lambda d: d["mean"]),
         "5.5 home, draw, away calibration (best of two)": min(e3["temperature_hold_diff"], e3["dirichlet_hold_diff"], key=lambda d: d["mean"]),
         "5.6 stacked blend": e4["hold_diff"], "5.7 new-team Elo start (thin-data matches)": e5.get("thin_hold_diff")}
def pval(d):  # noqa: E302
    """One-sided bootstrap p-value that the mean difference is below zero, from the normal approximation."""
    if not d:
        return 1.0
    se = (d["hi"] - d["lo"]) / (2 * 1.96)
    return float(0.5 * math.erfc(-(d["mean"] / se) / math.sqrt(2))) if se > 0 else 1.0
ps = sorted((pval(d), k) for k, d in tests.items())
holm = {}
for r, (p, k) in enumerate(ps):
    holm[k] = {"p": round(p, 4), "holm_threshold": round(0.05 / (len(ps) - r), 4), "pass": p < 0.05 / (len(ps) - r) and all(holm[k2]["pass"] for _, k2 in ps[:r])}
c = e1["chosen"]
e1["detail"] = (f"best on the tuning matches: half-life {c['half']:.0f} days, penalty {c['alpha']}, rho {c['rho']}"
                + (f" (fitted rho {e1['rho_fitted_range'][0]} to {e1['rho_fitted_range'][1]})" if e1.get("rho_fitted_range") else ""))
e2["detail"] = (f"over 2.5: predicted {e2['mean_pred_hold']:.1%}, happened {e2['actual_hold']:.1%} on the test matches; "
                f"goals shift by competition {e2['shift_hold_diff']['mean']:+.4f}, isotonic {e2['isotonic_hold_diff']['mean']:+.4f}")
e3["detail"] = f"temperature {e3['temperature']}: {e3['temperature_hold_diff']['mean']:+.4f}; Dirichlet {e3['dirichlet_hold_diff']['mean']:+.4f}"
e4["detail"] = f"walked forward over all {summary['reference']['n']}: {e4['walk_forward_all']:.4f} against 0.9393"
if e5.get("has_hook"):
    e5["detail"] = f"{e5['thin_n_hold']} test matches with a thin-data team: {e5['thin_hold_ref']:.4f} to {e5['thin_hold_new']:.4f}"
out = {"summary": summary, "5.3": e1, "5.4": e2, "5.5": e3, "5.6": e4, "5.7": e5, "holm": holm, "tests": tests}
(paths.OUT / "experiments_2026_10.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
print(json.dumps(holm, indent=1))
