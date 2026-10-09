"""Goals shape fix `shape_v1` (approved by Lang on 9 Oct 2026; reports/audit_2026_10.md).

The Bayesian model's expected goals stay as they are. Only the step from expected
goals to exact scores changes:

1. stretch: log(home rate / away rate) is widened by a factor (1 + s), the product
   of the two rates kept;
2. shape: each side's goals follow a COM-Poisson count with the same mean, which
   is less spread out than Poisson when the dispersion v is above 1 (v = 1 is
   Poisson);
3. the Dixon-Coles low-score correction rho.

The four numbers (vh, va, rho, s) are refitted at the first daily run of each
month, by maximum likelihood of the observed scorelines, on the model's own stored
forecasts (expected goals before the fix) of the previous 730 days: the walk-forward
backtest plus scored live rows. This is exactly the method tested in the check-up
(`scripts/audit_2026_10.py`, variant "S1 stretch plus G1 shape, rolling").
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp

from fp import ROOT
from fp.validate.leakage import known_as_of

log = logging.getLogger(__name__)

RULE = "shape_v1"
STORE = ROOT / "data" / "shape" / "shape_v1.json"
BACKTEST = ROOT / "data" / "backtests" / "dc_bayes_v1_walkforward_2021_2025.parquet"
WINDOW_DAYS = 730
MIN_HISTORY = 300
UNSHAPED_MODEL = "dc_bayes_v1_noshape"
MAX_GOALS = 10
K = np.arange(MAX_GOALS + 1)
LOGFACT = gammaln(K + 1)
BOUNDS = {"vh": (0.6, 2.0), "va": (0.6, 2.0), "rho": (-0.2, 0.2), "s": (-0.5, 1.0)}


@dataclass(frozen=True)
class Shape:
    vh: float = 1.0
    va: float = 1.0
    rho: float = 0.0
    s: float = 0.0


POISSON = Shape()


def cmp_pmf(mean: np.ndarray, v: float) -> np.ndarray:
    """COM-Poisson probabilities of 0 to 10 goals with the given means, shape (n, 11)."""
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
    """Scoreline tables (n, 11, 11), rows home goals, from expected goals."""
    lam = np.atleast_1d(np.asarray(lam, dtype=float))
    nu = np.atleast_1d(np.asarray(nu, dtype=float))
    r = np.log(lam / nu)
    lam2, nu2 = lam * np.exp(sh.s * r / 2), nu * np.exp(-sh.s * r / 2)
    m = cmp_pmf(lam2, sh.vh)[:, :, None] * cmp_pmf(nu2, sh.va)[:, None, :]
    m[:, 0, 0] *= 1 - lam2 * nu2 * sh.rho
    m[:, 0, 1] *= 1 + lam2 * sh.rho
    m[:, 1, 0] *= 1 + nu2 * sh.rho
    m[:, 1, 1] *= 1 - sh.rho
    m = np.clip(m, 1e-12, None)
    return m / m.sum(axis=(1, 2), keepdims=True)


def fit(lam: np.ndarray, nu: np.ndarray, hg: np.ndarray, ag: np.ndarray,
        start: Shape = POISSON) -> Shape:
    """Maximum likelihood of the observed scorelines."""
    names = list(BOUNDS)
    hi = np.minimum(np.asarray(hg, dtype=int), MAX_GOALS)
    ai = np.minimum(np.asarray(ag, dtype=int), MAX_GOALS)

    def nll(x: np.ndarray) -> float:
        m = shaped(lam, nu, Shape(*x))
        return float(-np.log(m[np.arange(len(hi)), hi, ai]).mean())

    res = minimize(nll, [getattr(start, k) for k in names], method="L-BFGS-B",
                   bounds=[BOUNDS[k] for k in names])
    return Shape(*(float(v) for v in res.x))


def history(matches: pd.DataFrame, ledger: pd.DataFrame, now: pd.Timestamp,
            backtest: Path = BACKTEST) -> pd.DataFrame:
    """Expected goals before the fix, with the result, for every match that kicked
    off in the previous 730 days and whose result was known at `now`."""
    parts = []
    if backtest.exists():
        b = pd.read_parquet(backtest, columns=["match_id", "bdc_exp_goals_home",
                                               "bdc_exp_goals_away"])
        parts.append(b.rename(columns={"bdc_exp_goals_home": "lam",
                                       "bdc_exp_goals_away": "nu"}))
    if len(ledger):
        rows = ledger.sort_values("lock_utc").drop_duplicates(["match_id", "model_name"],
                                                              keep="last")
        plain = rows[rows["model_name"] == UNSHAPED_MODEL]
        # Rows locked before the fix went live carry the plain forecast themselves.
        early = rows[(rows["model_name"] == "dc_bayes_v1")
                     & ~rows["flags"].astype(str).str.contains(RULE)
                     & ~rows["match_id"].isin(plain["match_id"])]
        live = pd.concat([plain, early])[["match_id", "exp_goals_home", "exp_goals_away"]]
        parts.append(live.rename(columns={"exp_goals_home": "lam", "exp_goals_away": "nu"}))
    if not parts:
        return pd.DataFrame(columns=["match_id", "lam", "nu", "hg", "ag", "kickoff_utc"])
    frame = pd.concat(parts, ignore_index=True).drop_duplicates("match_id", keep="last")
    known = known_as_of(matches, now)
    known = known[known["kickoff_utc"] >= now - pd.Timedelta(days=WINDOW_DAYS)]
    out = frame.merge(known[["match_id", "home_goals", "away_goals", "kickoff_utc"]],
                      on="match_id")
    out = out.rename(columns={"home_goals": "hg", "away_goals": "ag"})
    return out.dropna(subset=["lam", "nu", "hg", "ag"]).reset_index(drop=True)


def load(store: Path = STORE) -> dict | None:
    if not store.exists():
        return None
    return json.loads(store.read_text(encoding="utf-8"))


def current(matches: pd.DataFrame, ledger: pd.DataFrame, now: pd.Timestamp,
            store: Path = STORE, save: bool = True) -> Shape:
    """This month's numbers: refitted at the first run of a new month, else read."""
    data = load(store)
    month = f"{now:%Y-%m}"
    if data is not None and data["current"]["month"] == month:
        c = data["current"]
        return Shape(c["vh"], c["va"], c["rho"], c["s"])
    hist = history(matches, ledger, now)
    if len(hist) < MIN_HISTORY:
        log.warning("shape_v1: only %d matches of history; using Poisson this month", len(hist))
        sh = POISSON
    else:
        prev = data["current"] if data is not None else None
        start = Shape(prev["vh"], prev["va"], prev["rho"], prev["s"]) if prev else POISSON
        sh = fit(hist["lam"].to_numpy(), hist["nu"].to_numpy(), hist["hg"].to_numpy(),
                 hist["ag"].to_numpy(), start)
    entry = {"month": month, "fitted_utc": f"{now:%Y-%m-%dT%H:%MZ}", "n": int(len(hist)),
             **{k: round(v, 6) for k, v in asdict(sh).items()}}
    log.info("shape_v1 refit for %s: %s", month, entry)
    if save:
        past = (data or {}).get("history", [])
        out = {"rule": RULE, "approved": "Lang, 9 Oct 2026", "current": entry,
               "history": [*past, entry]}
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return Shape(entry["vh"], entry["va"], entry["rho"], entry["s"])


def _markets(mats: np.ndarray) -> dict[str, np.ndarray]:
    total = K[:, None] + K[None, :]
    home = np.tril(np.ones((len(K), len(K))), -1).astype(bool)
    return {
        "p_home": mats[:, home].sum(axis=1),
        "p_draw": np.trace(mats, axis1=1, axis2=2),
        "p_away": mats[:, home.T].sum(axis=1),
        "p_over_1_5": mats[:, total > 1.5].sum(axis=1),
        "p_over_2_5": mats[:, total > 2.5].sum(axis=1),
        "p_over_3_5": mats[:, total > 3.5].sum(axis=1),
        "p_btts": mats[:, 1:, 1:].sum(axis=(1, 2)),
        "exp_goals_home": (mats.sum(axis=2) * K).sum(axis=1),
        "exp_goals_away": (mats.sum(axis=1) * K).sum(axis=1),
    }


def apply(plain: dict, lam_draws: np.ndarray, nu_draws: np.ndarray, sh: Shape,
          top_n: int = 5) -> dict:
    """The published markets after the fix, from the plain Bayesian markets (as
    returned by bayes_dc.markets) and the posterior draws of the scoring rates
    (news scaling already applied). Point forecast: the fix applied to the plain
    forecast's expected goals, as tested. Intervals: the fix applied draw by draw."""
    mat = shaped(np.array([plain["exp_goals_home"]]), np.array([plain["exp_goals_away"]]), sh)
    point: dict = {k: float(v[0]) for k, v in _markets(mat).items()}
    mean = mat[0]
    order = np.argsort(mean, axis=None)[::-1][:top_n]
    point["top_scorelines"] = [
        {"score": f"{i}-{j}", "p": round(float(mean[i, j]), 4)}
        for i, j in zip(*np.unravel_index(order, mean.shape), strict=True)]
    point["matrix"] = mean
    per_draw = _markets(shaped(lam_draws, nu_draws, sh))
    point["intervals"] = {
        k: [round(float(np.percentile(v, 10)), 4), round(float(np.percentile(v, 90)), 4)]
        for k, v in per_draw.items() if k.startswith("p_")}
    return point
