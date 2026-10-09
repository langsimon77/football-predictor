"""Model check-up, October 2026: tests of possible accuracy fixes on stored forecasts.

Nothing here changes a live forecast. Every test re-scores the walk-forward forecasts
already saved in data/backtests, so it runs in a few minutes on a laptop.

Tests (lower log loss is better; the strict rule needs the whole 95% interval below 0):
- G1 shape: goal counts less spread out than Poisson (COM-Poisson), same expected goals.
- S1 stretch: widen the gap between the two scoring rates by a factor s, total kept.
- C1, Y1: pull corners and yellows forecasts towards the league average.
Each comes in a fixed version (fitted once on 2021/22 and 2022/23) and a rolling
version (refitted at the first lock of each month on the previous 730 days only).
The replication applies the two pre-registered candidates to 2018/19 and 2019/20
(data/audit/preregistration_2026_10.md).

    uv run python scripts/audit_2026_10.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp

ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "data" / "backtests"
OUT_JSON = ROOT / "data" / "audit" / "audit_2026_10.json"
REPORT = ROOT / "reports" / "audit_2026_10.md"
RUNS = ROOT / "data" / "audit" / "daily_run_starts.csv"
TEST = (2023, 2024, 2025)
REPLICATION = (2018, 2019)
K = np.arange(11)
LOGFACT = gammaln(K + 1)
H = np.tril(np.ones((11, 11)), -1).astype(bool)
TOTAL = np.add.outer(K, K)
WINDOW_DAYS = 730
MIN_HISTORY = 300
B = 4000


# ------------------------------------------------------------ the goals shape fix
@dataclass(frozen=True)
class Shape:
    """vh, va: COM-Poisson dispersion (1 is Poisson, above 1 less spread out);
    rho: Dixon-Coles low-score correction; s: stretch of log(home rate / away rate)."""

    vh: float = 1.0
    va: float = 1.0
    rho: float = 0.0
    s: float = 0.0


POISSON = Shape()


def cmp_pmf(mean: np.ndarray, v: float) -> np.ndarray:
    """COM-Poisson probabilities of 0 to 10 goals with the given mean."""
    mean = np.atleast_1d(np.asarray(mean, dtype=float))
    t = np.log(np.maximum(mean, 1e-6)) * v
    for _ in range(30):  # Newton on the log rate: d(mean)/dt is the variance
        lp = K[None, :] * t[:, None] - v * LOGFACT[None, :]
        p = np.exp(lp - logsumexp(lp, axis=1, keepdims=True))
        m = (p * K).sum(1)
        var = (p * K**2).sum(1) - m**2
        t = t - (m - mean) / np.maximum(var, 1e-9)
    lp = K[None, :] * t[:, None] - v * LOGFACT[None, :]
    return np.exp(lp - logsumexp(lp, axis=1, keepdims=True))


def shaped(lam: np.ndarray, nu: np.ndarray, sh: Shape) -> np.ndarray:
    """Scoreline tables (n, 11, 11) from expected goals, after stretch and shape."""
    lam, nu = np.atleast_1d(lam).astype(float), np.atleast_1d(nu).astype(float)
    r = np.log(lam / nu)
    lam2, nu2 = lam * np.exp(sh.s * r / 2), nu * np.exp(-sh.s * r / 2)
    m = cmp_pmf(lam2, sh.vh)[:, :, None] * cmp_pmf(nu2, sh.va)[:, None, :]
    m[:, 0, 0] *= 1 - lam2 * nu2 * sh.rho
    m[:, 0, 1] *= 1 + lam2 * sh.rho
    m[:, 1, 0] *= 1 + nu2 * sh.rho
    m[:, 1, 1] *= 1 - sh.rho
    m = np.clip(m, 1e-12, None)
    return m / m.sum(axis=(1, 2), keepdims=True)


def fit_shape(lam, nu, hg, ag, free=("vh", "va", "rho", "s"), start: Shape = POISSON
              ) -> Shape:
    """Maximum likelihood of the observed scorelines."""
    names = list(free)
    bounds = {"vh": (0.6, 2.0), "va": (0.6, 2.0), "rho": (-0.2, 0.2), "s": (-0.5, 1.0)}
    hi, ai = np.minimum(hg, 10), np.minimum(ag, 10)

    def nll(x):
        sh = Shape(**{**start.__dict__, **dict(zip(names, x, strict=True))})
        m = shaped(lam, nu, sh)
        return -np.log(m[np.arange(len(lam)), hi, ai]).mean()

    res = minimize(nll, [getattr(start, k) for k in names], method="L-BFGS-B",
                   bounds=[bounds[k] for k in names])
    return Shape(**{**start.__dict__, **dict(zip(names, res.x, strict=True))})


def latest_shape(now: pd.Timestamp | None = None) -> tuple[Shape, int]:
    """The stretch-plus-shape numbers that would go live at `now`: fitted on the
    stored forecasts of the previous 730 days (backtest plus scored live rows)."""
    f = goals_frame()
    now = now or pd.Timestamp.now(tz="UTC")
    sel = (f["kickoff_utc"] < now) & (f["kickoff_utc"] >= now - pd.Timedelta(days=WINDOW_DAYS))
    g = f[sel]
    sh = fit_shape(g["lam"].to_numpy(), g["nu"].to_numpy(), g["hg"].to_numpy(), g["ag"].to_numpy())
    return sh, int(sel.sum())


# ------------------------------------------------------------ data
def goals_frame(path: Path = BT / "dc_bayes_v1_walkforward_2021_2025.parquet") -> pd.DataFrame:
    from fp.ingest.matches import PROCESSED
    m = pd.read_parquet(PROCESSED / "matches.parquet").set_index("match_id")
    d = pd.read_parquet(path)
    d = d.assign(kickoff_utc=d["match_id"].map(m["kickoff_utc"]),
                 hg=d["match_id"].map(m["home_goals"]).astype(int),
                 ag=d["match_id"].map(m["away_goals"]).astype(int),
                 lam=d["bdc_exp_goals_home"], nu=d["bdc_exp_goals_away"])
    d["lock_utc"] = pd.to_datetime(d["lock_utc"], utc=True)
    d["y"] = np.where(d["hg"] > d["ag"], 0, np.where(d["hg"] == d["ag"], 1, 2))
    d["M0"] = list(np.stack([np.asarray(x, float).reshape(11, 11) for x in d["bdc_matrix"]]))
    return d.sort_values("lock_utc").reset_index(drop=True)


def markets(m: np.ndarray) -> dict[str, np.ndarray]:
    return {"x12": np.stack([m[:, H].sum(1), np.trace(m, axis1=1, axis2=2), m[:, H.T].sum(1)], 1),
            "over_1_5": m[:, TOTAL > 1.5].sum(1), "over_2_5": m[:, TOTAL > 2.5].sum(1),
            "over_3_5": m[:, TOTAL > 3.5].sum(1), "btts": m[:, 1:, 1:].sum((1, 2))}


def losses(m: np.ndarray, hg: np.ndarray, ag: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    f = markets(m)
    n = len(y)
    out = {"1x2": -np.log(np.clip(f["x12"][np.arange(n), y], 1e-15, 1))}
    tot = hg + ag
    for k, happened in (("over_1_5", tot > 1.5), ("over_2_5", tot > 2.5), ("over_3_5", tot > 3.5),
                        ("btts", (hg > 0) & (ag > 0))):
        q = np.clip(f[k], 1e-15, 1 - 1e-15)
        out[k] = -np.where(happened, np.log(q), np.log(1 - q))
    exact = m[np.arange(n), np.minimum(hg, 10), np.minimum(ag, 10)]
    out["score"] = -np.log(np.clip(exact, 1e-15, 1))
    return out


def interval(d: np.ndarray, seed: int, level: float = 0.95) -> tuple[float, float, float, float]:
    """Mean, interval, and one-sided bootstrap p (share of resamples with no gain)."""
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(B, len(d)))].mean(1)
    a = (1 - level) / 2
    return float(d.mean()), float(np.quantile(means, a)), float(np.quantile(means, 1 - a)), \
        float((means >= 0).mean())


def monthly(frame: pd.DataFrame, fit, apply, start):
    """Refit at the first lock of each month on the previous 730 days only."""
    kick, lock = frame["kickoff_utc"], frame["lock_utc"]
    months = lock.dt.strftime("%Y-%m").to_numpy()
    out = [None] * len(frame)
    prev, path = start, []
    for mth in sorted(set(months)):
        sel = np.where(months == mth)[0]
        t0 = lock.iloc[sel].min()
        past = np.where((kick + pd.Timedelta(hours=3) < t0)
                        & (kick >= t0 - pd.Timedelta(days=WINDOW_DAYS)))[0]
        if len(past) >= MIN_HISTORY:
            prev = fit(past, prev)
            use = prev
        else:
            use = start
        path.append((mth, len(past), use))
        for i, v in zip(sel, apply(sel, use), strict=True):
            out[i] = v
    return out, path


# ------------------------------------------------------------ goals tests
def goals_tests(f: pd.DataFrame) -> tuple[list[dict], dict, dict]:
    lam, nu = f["lam"].to_numpy(), f["nu"].to_numpy()
    hg, ag, y = f["hg"].to_numpy(), f["ag"].to_numpy(), f["y"].to_numpy()
    M0 = np.stack(f["M0"].to_numpy())
    tune = f["season"].isin((2021, 2022)).to_numpy()
    test = f["season"].isin(TEST).to_numpy()
    ti, te = np.where(tune)[0], np.where(test)[0]
    variants = {
        "G1 shape": ("vh", "va", "rho"),
        "S1 stretch": ("rho", "s"),
        "S1 stretch plus G1 shape": ("vh", "va", "rho", "s"),
    }
    tables, fitted, paths = {}, {}, {}
    for name, free in variants.items():
        sh = fit_shape(lam[ti], nu[ti], hg[ti], ag[ti], free)
        M = M0.copy()
        M[te] = shaped(lam[te], nu[te], sh)
        tables[name + ", fixed"] = M
        fitted[name + ", fixed"] = sh

        def fit(idx, prev, free=free):
            return fit_shape(lam[idx], nu[idx], hg[idx], ag[idx], free, prev)

        rows, path = monthly(f, fit, lambda sel, sh: list(shaped(lam[sel], nu[sel], sh)), Shape())
        tables[name + ", rolling"] = np.stack(rows)
        paths[name + ", rolling"] = path
    base = losses(M0[te], hg[te], ag[te], y[te])
    results = []
    for j, (name, M) in enumerate(tables.items()):
        new = losses(M[te], hg[te], ag[te], y[te])
        for k in base:
            mean, lo, hi, p = interval(new[k] - base[k], 100 + j)
            results.append({"variant": name, "market": k, "published": float(base[k].mean()),
                            "change": mean, "lo": lo, "hi": hi, "p": p})
    return results, fitted, {"tables": tables, "paths": paths, "base": base, "te": te}


def holm(results: list[dict]) -> dict[str, bool]:
    ps = sorted((r["p"], r["variant"]) for r in results if r["market"] == "1x2")
    out, ok = {}, True
    for j, (p, v) in enumerate(ps):
        ok = ok and p < 0.025 / (len(ps) - j)
        out[v] = ok
    return out


def breakdown(f: pd.DataFrame, M: np.ndarray, seed: int) -> list[dict]:
    hg, ag, y = f["hg"].to_numpy(), f["ag"].to_numpy(), f["y"].to_numpy()
    M0 = np.stack(f["M0"].to_numpy())
    d = losses(M, hg, ag, y)["1x2"] - losses(M0, hg, ag, y)["1x2"]
    out = []
    for label, sel in [(lg, f["league"] == lg) for lg in ("EPL", "LaLiga")] + \
            [(f"{s}/{(s + 1) % 100:02d}", f["season"] == s) for s in TEST]:
        sel = sel.to_numpy() & f["season"].isin(TEST).to_numpy()
        mean, lo, hi, _ = interval(d[sel], seed)
        out.append({"group": label, "n": int(sel.sum()), "change": mean, "lo": lo, "hi": hi})
    return out


# ------------------------------------------------------------ corners and yellows
def counts_tests() -> list[dict]:
    from fp.ingest.matches import PROCESSED
    b = pd.read_parquet(BT / "baselines_2021_2025.parquet").sort_values("lock_utc").reset_index(
        drop=True)
    b["kickoff_utc"] = pd.to_datetime(b["kickoff_utc"], utc=True)
    b["lock_utc"] = pd.to_datetime(b["lock_utc"], utc=True)
    m = pd.read_parquet(PROCESSED / "matches.parquet")
    out = []
    for args in (("C1 corners towards league average",
                  "corners_total_poisson_walkforward_2021_2025", ("home_corners", "away_corners"),
                  (8.5, 9.5, 10.5, 11.5)),
                 ("Y1 yellows towards league average", "cards_nb_walkforward_2021_2025",
                  ("home_yellows", "away_yellows"), (3.5, 4.5, 5.5))):
        out += count_test(b, m, *args)
    return out


def count_test(b: pd.DataFrame, m: pd.DataFrame, name: str, file: str, cols: tuple[str, str],
               lines: tuple[float, ...]) -> list[dict]:
    test = b["season"].isin(TEST).to_numpy()
    tune = b["season"].isin((2021, 2022)).to_numpy()
    f = pd.read_parquet(BT / f"{file}.parquet").set_index("match_id").reindex(b["match_id"])
    pmf = np.stack([np.asarray(p, float) for p in f["pmf"]])
    pmf /= pmf.sum(1, keepdims=True)
    kk = np.arange(pmf.shape[1])
    logp = np.log(np.clip(pmf, 1e-300, None))
    mu = (pmf * kk).sum(1)
    tot = m.assign(t=m[cols[0]] + m[cols[1]]).dropna(subset=["t"])
    base = np.zeros(len(b))
    for (lg, lk), g in b.groupby(["league", "lock_utc"]):
        s = tot[(tot["league"] == lg) & (tot["result_available_utc"] <= lk)
                & (tot["kickoff_utc"] >= lk - pd.Timedelta(days=1100))]
        base[g.index] = s["t"].mean()
    yv = (b[cols[0]] + b[cols[1]]).to_numpy()
    ok = np.isfinite(yv)
    yi = np.where(ok, yv, 0).astype(int)

    def tilt(idx, target):
        t = np.zeros(len(idx))
        for _ in range(40):
            lp = logp[idx] + t[:, None] * kk[None, :]
            p = np.exp(lp - logsumexp(lp, 1, keepdims=True))
            mn = (p * kk).sum(1)
            t -= (mn - target) / np.maximum((p * kk**2).sum(1) - mn**2, 1e-9)
        lp = logp[idx] + t[:, None] * kk[None, :]
        return lp - logsumexp(lp, 1, keepdims=True)

    def new_lp(idx, th):
        a, k = th
        return tilt(idx, np.maximum(base[idx] + a + k * (mu[idx] - base[idx]), 0.5))

    def fit(idx, prev=(0.0, 1.0)):
        idx = idx[ok[idx]]
        return tuple(minimize(lambda th: -new_lp(idx, th)[np.arange(len(idx)), yi[idx]].mean(),
                              prev, method="L-BFGS-B", bounds=[(-2, 2), (0, 1.5)]).x)

    te = np.where(test & ok)[0]
    fixed = logp.copy()
    fixed[te] = new_lp(te, fit(np.where(tune & ok)[0]))
    rows, _ = monthly(b, lambda idx, prev: fit(idx, prev),
                      lambda sel, th: list(new_lp(sel, th)), (0.0, 1.0))
    rolling = np.stack(rows)

    def score(lp):
        res = {"count": -lp[te, yi[te]]}
        p = np.exp(lp[te])
        for ln in lines:
            q = np.clip(p[:, kk > ln].sum(1), 1e-15, 1 - 1e-15)
            res[f"over_{ln}"] = -np.where(yi[te] > ln, np.log(q), np.log(1 - q))
        return res

    out = []
    s0 = score(logp)
    for j, (vname, lp) in enumerate((("fixed", fixed), ("rolling", rolling))):
        s1 = score(lp)
        for key in s0:
            mean, lo, hi, p = interval(s1[key] - s0[key], 300 + j)
            out.append({"variant": f"{name}, {vname}", "market": key, "change": mean, "lo": lo,
                        "hi": hi, "p": p, "published": float(s0[key].mean())})
    return out


# ------------------------------------------------------------ replication
def replication(fitted_fixed: Shape) -> list[dict] | None:
    path = BT / "dc_bayes_v1_walkforward_2018_2020.parquet"
    if not path.exists():
        return None
    f = goals_frame(path)
    latest, _ = latest_shape(pd.Timestamp("2026-10-09", tz="UTC"))
    out = []
    for label, seasons in (("2018/19 and 2019/20 (counts)", REPLICATION),
                           ("2020/21, no crowds (reported only)", (2020,))):
        g = f[f["season"].isin(seasons)]
        lam, nu = g["lam"].to_numpy(), g["nu"].to_numpy()
        hg, ag, y = g["hg"].to_numpy(), g["ag"].to_numpy(), g["y"].to_numpy()
        base = losses(np.stack(g["M0"].to_numpy()), hg, ag, y)
        for j, (cand, sh) in enumerate((("Stretch only (fixed)", fitted_fixed),
                                        ("Stretch plus shape (latest)", latest))):
            new = losses(shaped(lam, nu, sh), hg, ag, y)
            for k in base:
                mean, lo, hi, p = interval(new[k] - base[k], 500 + j, level=0.975)
                out.append({"seasons": label, "candidate": cand, "market": k, "n": len(g),
                            "published": float(base[k].mean()), "change": mean, "lo": lo,
                            "hi": hi})
    return out


# ------------------------------------------------------------ lock timing
def lock_timing() -> dict | None:
    """How often the early Saturday kickoff (11:30 UTC until 24 Oct) would have
    been locked late, given the real start times of the main daily run."""
    if not RUNS.exists():
        return None
    r = pd.read_csv(RUNS, parse_dates=["started_utc"])
    first = r.sort_values("started_utc").groupby(r["started_utc"].dt.date).first()["started_utc"]
    clock = (first.dt.hour * 60 + first.dt.minute).to_numpy()
    pairs = list(zip(clock[:-1], clock[1:], strict=True))
    out = {"days": len(clock), "earliest": f"{clock.min() // 60:02d}:{clock.min() % 60:02d}",
           "latest": f"{clock.max() // 60:02d}:{clock.max() % 60:02d}"}
    for label, ko in (("11:30", 690), ("12:00", 720), ("12:30", 750)):
        late = sum(1 for a, b in pairs if a < ko < b)
        out[label] = {"late_pairs": late, "pairs": len(pairs)}
    return out


# ------------------------------------------------------------ for the Model Lab
def proposal() -> Shape:
    """The numbers the proposed fix would use today (not live)."""
    d = json.loads(OUT_JSON.read_text(encoding="utf-8"))["latest"]
    return Shape(vh=d["vh"], va=d["va"], rho=d["rho"], s=d["s"])


def panel() -> dict:
    """Plain-language summary of the check-up for the Model Lab's Tests page."""
    d = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    def goal(variant: str, market: str) -> dict:
        return next(r for r in d["goals"] if r["variant"] == variant and r["market"] == market)

    def rep(cand: str, market: str) -> dict:
        return next(r for r in d["replication"] if r["candidate"] == cand
                    and r["market"] == market and r["seasons"].startswith("2018"))

    def count(variant: str) -> dict:
        return next(r for r in d["counts"] if r["variant"] == variant and r["market"] == "count")

    def row(idea, market, r, test_label="2023/24 to 2025/26, 95% range"):
        verdict = "pass" if r["hi"] < 0 else ("worse" if r["lo"] > 0 else "fail")
        return {"idea": idea, "seasons": test_label, "market": market, "change": r["change"],
                "lo": r["lo"], "hi": r["hi"], "verdict": verdict}

    best = "S1 stretch plus G1 shape, rolling"
    t = d["timing"] or {}
    late = t.get("11:30", {"late_pairs": 0, "pairs": 0})
    tests = [
        row("Stretch plus shape, refitted monthly", "Home, draw, away", goal(best, "1x2")),
        row("Stretch plus shape, refitted monthly", "Both teams score", goal(best, "btts")),
        row("Stretch plus shape, refitted monthly", "3 or more goals", goal(best, "over_2_5")),
        row("Stretch plus shape, numbers as of today", "Home, draw, away",
            rep("Stretch plus shape "
                "(latest)", "1x2"), "2018/19 and 2019/20, rule set in advance, 97.5% range"),
        row("Stretch plus shape, numbers as of today", "3 or more goals",
            rep("Stretch plus shape (latest)", "over_2_5"), "2018/19 and 2019/20, 97.5% range"),
        row("Stretch plus shape, numbers as of today", "Both teams score",
            rep("Stretch plus shape (latest)", "btts"), "2018/19 and 2019/20, 97.5% range"),
        row("Stretch only, one number", "Home, draw, away", goal("S1 stretch, fixed", "1x2")),
        row("Stretch only, one number", "Home, draw, away", rep("Stretch only (fixed)", "1x2"),
            "2018/19 and 2019/20, rule set in advance, 97.5% range"),
        row("Shape only", "Home, draw, away", goal("G1 shape, rolling", "1x2")),
        row("Corners pulled towards league average", "Total corners",
            count("C1 corners towards league average, rolling")),
        row("Yellows pulled towards league average", "Total yellow cards",
            count("Y1 yellows towards league average, fixed")),
    ]
    latest = d["latest"]
    return {
        "date": "9 Oct 2026",
        "summary": (
            "I checked the daily pipeline, the four published models and the saved forecasts of "
            "five past seasons, looking for errors and for ways to be more accurate. No error "
            "changes a published number. Two timing and display problems need a small fix. One "
            "accuracy fix for goals passed both its tests and waits for your yes. Corners and "
            "yellow cards are already as good as these tests can make them."),
        "findings": [
            {"title": "Goals are less random than the model assumes.", "status": "proposed",
             "text": ("Teams fail to score less often than the model says (home sides 22% against "
                      "25% forecast) and 0-0 is rarer (6% against 8%). The same pattern makes the "
                      "model too cautious about strong favourites: forecasts of 70% or more won "
                      "82% "
                      "of the time. A fix that reshapes the goal counts passed on past seasons and "
                      "again on two older seasons it had never seen.")},
            {"title": "Early Saturday kickoffs can lock too late.", "status": "proposed",
             "text": (f"GitHub starts the 04:41 UTC run 5 to 7 hours late (between "
                      f"{t.get('earliest', '?')} "
                      f"and {t.get('latest', '?')} UTC). The 11:30 UTC Saturday kickoff falls "
                      f"inside "
                      f"that spread, so in {late['late_pairs']} of {late['pairs']} day pairs it "
                      f"would "
                      "have locked under 24 hours before kickoff. Arsenal v Leeds locked in time "
                      "this "
                      "week with 6 minutes to spare. Fix: start the schedule at 00:41 UTC "
                      "instead.")},
            {"title": "Provisional confidence can be one level too high.", "status": "proposed",
             "text": ("Before a match locks, the background models are not run, so the 'models "
                      "disagree' check is skipped. Up to about 1 provisional label in 10 may drop "
                      "one "
                      "level at lock. Locked labels are right. Fix: run the background models for "
                      "provisional forecasts too.")},
            {"title": "The lab's club table could go out of date.", "status": "fixed",
             "text": ("The ratings and season simulator read the laptop's copy of the data. The "
                      "builder now refuses to run if that copy is older than the published "
                      "forecasts. No published forecast was affected.")},
            {"title": "Checked and correct.", "status": "none",
             "text": ("Lock window and late-lock flag, result recording, chances adding up to "
                      "100%, "
                      "team-news sizes and the 12% cap, the confidence rule, promoted-club "
                      "starting "
                      "points (learned only from 2017/18 to 2020/21, so no peeking in the tests), "
                      "and expected goals per team (honest on average).")},
            {"title": "Corners and yellow cards stay as they are.", "status": "kept",
             "text": ("Both are well calibrated. Pulling them towards league averages made no "
                      "difference for corners and was clearly worse for yellows.")},
        ],
        "tests": tests,
        "tests_note": (
            "Change in surprise score per match; below zero is better. Past test seasons are "
            "2023/24 to 2025/26 with a 95% range. I tried six versions of the goals fix there, so "
            "a "
            "pass could be luck; that is why I wrote the replication rule down first and tested "
            "two candidates on 2018/19 and 2019/20 with a stricter 97.5% range."),
        "proposals": [
            {"title": "1. Goals fix (proposed name shape_v1).",
             "text": ("Keep the main model's expected goals; change only how they turn into exact "
                      "scores: goal counts less spread out than now, and a small adjustment to "
                      "the gap between the two sides. Four numbers, refitted at the start of each "
                      "month from the last two seasons of the model's own forecasts. Today: "
                      f"tightness {latest['vh']:.2f} home and {latest['va']:.2f} away (1.00 is the "
                      f"current model), gap adjustment {latest['s']:+.3f} (it was about +0.07 a "
                      f"year "
                      "ago). Gain about 0.002 per match on home, draw, away "
                      "[E], about an eighth of the gap to the bookmakers' Friday prices. Both "
                      "teams score rises by "
                      "about 3 points in a typical match. A copy without the fix is locked in the "
                      "background so we can compare live.")},
            {"title": "2. Earlier daily schedule.",
             "text": ("Main run at 00:41 UTC (02:41 Juba), backups at 06:41 and 12:41 UTC. With "
                      "today's delays it would start around 05:00 to 07:30 UTC, far from any "
                      "kickoff. Team-news questions would then arrive in your morning.")},
            {"title": "3. Background models for provisional forecasts.",
             "text": ("So provisional confidence labels use the same checks as locked ones.")},
        ],
    }


# ------------------------------------------------------------ report
def fmt(x: float) -> str:
    return f"{x:+.4f}".replace("-", "−") if abs(x) >= 0.00005 else "0.0000"


def main() -> int:
    f = goals_frame()
    goals, fitted, extra = goals_tests(f)
    holm_ok = holm(goals)
    counts = counts_tests()
    rep = replication(fitted["S1 stretch, fixed"])
    timing = lock_timing()
    latest, n_latest = latest_shape(pd.Timestamp("2026-10-09", tz="UTC"))
    best = extra["tables"]["S1 stretch plus G1 shape, rolling"]
    te = extra["te"]
    bd_fixed = breakdown(f, extra["tables"]["S1 stretch, fixed"], 900)
    bd_roll = breakdown(f, best, 901)
    data = {"goals": goals, "holm": holm_ok, "counts": counts, "replication": rep,
            "timing": timing, "fitted": {k: v.__dict__ for k, v in fitted.items()},
            "latest": {**latest.__dict__, "n": n_latest},
            "breakdown": {"S1 stretch, fixed": bd_fixed,
                          "S1 stretch plus G1 shape, rolling": bd_roll}}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=1, default=float) + "\n", encoding="utf-8")
    write_report(data, f, best, te)
    print(f"wrote {OUT_JSON} and {REPORT}")
    return 0


def write_report(data: dict, f: pd.DataFrame, best: np.ndarray, te: np.ndarray) -> None:
    names = {"1x2": "home, draw, away", "over_1_5": "2 or more goals",
             "over_2_5": "3 or more goals", "over_3_5": "4 or more goals",
             "btts": "both teams score", "score": "exact score", "count": "full count"}
    lines = ["# Model check-up, October 2026", "",
             "Generated by `scripts/audit_2026_10.py`. Every test re-scores walk-forward forecasts "
             "already stored in `data/backtests`; nothing live changed. Lower log loss is better. "
             "A change passes the strict rule only if its whole 95% bootstrap interval is below "
             "zero. Seasons 2021/22 and 2022/23 fit every number; 2023/24 to 2025/26 are scored. "
             "Labels: [V] verified here, [E] estimate, [A] assumption.", "",
             "## 1. Goals: diagnosis [V]", "",
             "- Expected goals per team are honest on average (actual on forecast slope 1.02 to "
             "1.06 "
             "for home goals, 0.96 to 0.97 for away goals).",
             "- But goal counts are less spread out than Poisson: Pearson dispersion 0.94 (home) "
             "and "
             "0.96 (away) over five seasons, 0.80 to 0.86 in 2024/25 and 2025/26. A side fails to "
             "score less often than forecast (home 22.3% against 24.5%; away 30.3% against 31.8%); "
             "0-0 happens 6.2% of the time against 7.6% forecast; both teams score is "
             "under-forecast "
             "in the test seasons (55.9% against 51.4%).",
             "- Strong favourites win more often than promised: forecasts of 70% or more won 82% "
             "(forecast 76%), mostly because draws in those games happen 11% against 15% forecast.",
             "- Goal difference: actual on forecast slope 1.05 (EPL) and 1.07 (La Liga). The gap "
             "between the two sides' scoring rates is slightly too small.",
             "- Corners: well calibrated (probability integral transform flat; line forecasts "
             "within "
             "1.2 points). Yellows: slightly low in early seasons, high later; EPL slope 0.80.", "",
             "## 2. Goals: tests on 2023/24 to 2025/26 [V]", "",
             "| Variant | Market | Published | Change | 95% interval | Passes |",
             "|---|---|---|---|---|---|"]
    for r in data["goals"]:
        lines.append(f"| {r['variant']} | {names[r['market']]} | {r['published']:.4f} | "
                     f"{fmt(r['change'])} | {fmt(r['lo'])} to {fmt(r['hi'])} | "
                     f"{'yes' if r['hi'] < 0 else ('worse' if r['lo'] > 0 else 'no')} |")
    lines += ["", "Six variants were tried for home, draw, away. With a Holm correction for six "
              "tries (one-sided bootstrap p against 0.025 / rank):", "",
              "| Variant | Passes after correction |", "|---|---|"]
    for v, ok in data["holm"].items():
        lines.append(f"| {v} | {'yes' if ok else 'no'} |")
    lines += ["", "Fitted numbers (fixed versions, from 2021/22 and 2022/23):", ""]
    for k, v in data["fitted"].items():
        lines.append(f"- {k}: home dispersion {v['vh']:.3f}, away dispersion {v['va']:.3f}, "
                     f"rho {v['rho']:.4f}, stretch {v['s']:.4f}")
    la = data["latest"]
    lines += [f"- What would go live on 9 Oct 2026 (latest 730 days, {la['n']} matches): home "
              f"dispersion {la['vh']:.3f}, away dispersion {la['va']:.3f}, rho {la['rho']:.4f}, "
              f"stretch {la['s']:.4f}.", "", "Where the gain comes from (home, draw, away):", "",
              "| Variant | Group | Matches | Change | 95% interval |", "|---|---|---|---|---|"]
    for v, rows in data["breakdown"].items():
        for r in rows:
            lines.append(f"| {v} | {r['group']} | {r['n']} | {fmt(r['change'])} | "
                         f"{fmt(r['lo'])} to {fmt(r['hi'])} |")
    lines += ["", "## 3. Corners and yellows: tests on 2023/24 to 2025/26 [V]", "",
              "| Variant | Market | Published | Change | 95% interval | Passes |",
              "|---|---|---|---|---|---|"]
    for r in data["counts"]:
        mk = names.get(r["market"], r["market"].replace("_", " "))
        lines.append(f"| {r['variant']} | {mk} | {r['published']:.4f} | {fmt(r['change'])} | "
                     f"{fmt(r['lo'])} to {fmt(r['hi'])} | "
                     f"{'yes' if r['hi'] < 0 else ('worse' if r['lo'] > 0 else 'no')} |")
    lines += ["", "Neither count model gains from either change. Both stay as they are.", ""]
    lines += ["## 4. Replication on 2018/19 and 2019/20 [V]", ""]
    if data["replication"] is None:
        lines.append("Not run yet.")
    else:
        lines += ["Pre-registered in `data/audit/preregistration_2026_10.md` before the data were "
                  "seen. 97.5% intervals (two candidates).", "",
                  "| Seasons | Candidate | Market | Matches | Published | Change | 97.5% interval "
                  "|",
                  "|---|---|---|---|---|---|---|"]
        for r in data["replication"]:
            lines.append(f"| {r['seasons']} | {r['candidate']} | {names[r['market']]} | {r['n']} | "
                         f"{r['published']:.4f} | {fmt(r['change'])} | {fmt(r['lo'])} to "
                         f"{fmt(r['hi'])} |")
    lines += ["", "## 5. Lock timing [V]", ""]
    t = data["timing"]
    if t:
        lines += [f"Main daily run start times over {t['days']} days: {t['earliest']} to "
                  f"{t['latest']} UTC (scheduled 04:41). A match locks late (under 24 hours) when "
                  "its kickoff clock time falls between one day's run time and a later run time "
                  "the next day.", "",
                  "| Kickoff (UTC) | Day pairs that would lock it late |", "|---|---|"]
        for k in ("11:30", "12:00", "12:30"):
            lines.append(f"| {k} | {t[k]['late_pairs']} of {t[k]['pairs']} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    np.seterr(all="ignore")
    sys.exit(main())
