"""Hierarchical negative binomial models for corners and yellow cards (spec S5.3, S5.4).

Corners, one row per team per match:
    corners ~ NegBin(mean, alpha)
    log mean = intercept + home * is_home + for[team] + against[opponent]
               + b_gap * elo_gap_for_team + b_shots * rolling_shots_for_team

Yellow cards, one row per match (home plus away yellows):
    yellows ~ NegBin(mean, alpha)
    log mean = intercept + referee[ref] + discipline[home] + discipline[away]
               + b_close * closeness + b_fouls * rolling_fouls + b_derby * derby
               + b_imp * important
The referee term is used for the EPL only (decision D3). When the referee is not
known at lock time, predictions average over the referee distribution.

Team and referee effects are pooled: each is drawn from a league-wide normal whose
spread is learned, so a club or referee with little data sits near the average.
Covariates are standardised on the training rows. Likelihood terms carry the same
time-decay weights as the goals model (spec S5.3). poisson=True swaps in a Poisson
likelihood, used to test whether the extra dispersion is needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt
from numpy.typing import ArrayLike
from scipy.stats import nbinom, poisson

from fp.models.bayes_dc import DIAG_ESS, DIAG_RHAT

MAX_COUNT = {"corners": 30, "corners_total": 30, "cards": 16}
LINES = {"corners": (8.5, 9.5, 10.5, 11.5), "corners_total": (8.5, 9.5, 10.5, 11.5),
         "cards": (3.5, 4.5, 5.5)}
# Match-level targets: one row per match, a pooled effect per club (home and away
# club both contribute), plus these covariates. Continuous ones are standardised.
MATCH_COVARIATES = {
    "cards": {"continuous": ["close", "fouls"], "binary": ["derby", "important"]},
    "corners_total": {"continuous": ["lopsided", "shots"], "binary": []},
}


@dataclass
class CountParams:
    target: str = "corners"          # "corners" or "cards"
    xi: float = 0.002
    window_days: int = 1100
    poisson: bool = False
    use_referee: bool = False        # cards, EPL only
    draws: int = 1000
    tune: int = 1000
    chains: int = 4
    target_accept: float = 0.9
    sampler: str = "numpyro"
    # Club corner and card effects vary little between clubs, where the centred form
    # stalls; in tests every centred fit needed the retry. So start non-centred.
    centred: bool = False
    seed: int = 2026


@dataclass
class CountPosterior:
    target: str
    teams: list[str]
    referees: list[str]
    draws: dict[str, np.ndarray]      # name -> (S,) or (S, n)
    scales: dict[str, tuple[float, float]]   # covariate -> (mean, sd) used to standardise
    poisson: bool
    diagnostics: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        d = self.diagnostics
        return (d.get("rhat_max", 9) < DIAG_RHAT and d.get("ess_bulk_min", 0) > DIAG_ESS
                and d.get("divergences", 1) == 0)


def _z(values: ArrayLike, scale: tuple[float, float]) -> np.ndarray:
    mean, sd = scale
    return (np.asarray(values, dtype=float) - mean) / sd


def _scale(values: pd.Series) -> tuple[float, float]:
    v = values.astype(float)
    return float(v.mean()), float(v.std() or 1.0)


# Covariate construction. Missing rolling values (a club's first top-flight game)
# fall back to the training mean, which is 0 after standardising.

def corner_rows(matches: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    f = features.set_index("match_id")
    rows = []
    for side, other, sign in (("home", "away", 1.0), ("away", "home", -1.0)):
        part = pd.DataFrame({
            "match_id": matches["match_id"].to_numpy(),
            "team": matches[f"{side}_id"].to_numpy(),
            "opponent": matches[f"{other}_id"].to_numpy(),
            "is_home": 1.0 if side == "home" else 0.0,
            "gap": sign * matches["match_id"].map(f["elo_gap"]).to_numpy() / 100,
            "shots": matches["match_id"].map(f[f"{side}_shots_for"]).to_numpy(),
            "kickoff_utc": matches["kickoff_utc"].to_numpy(),
        })
        if f"{side}_corners" in matches:
            part["y"] = matches[f"{side}_corners"].to_numpy(dtype=float)
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def card_rows(matches: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    f = features.set_index("match_id")
    out = pd.DataFrame({
        "match_id": matches["match_id"].to_numpy(),
        "home": matches["home_id"].to_numpy(), "away": matches["away_id"].to_numpy(),
        "referee": matches.get("referee", pd.Series(None, index=matches.index)).to_numpy(),
        "close": -np.abs(matches["match_id"].map(f["elo_gap"]).to_numpy()) / 100,
        "fouls": (matches["match_id"].map(f["home_fouls"])
                  + matches["match_id"].map(f["away_fouls"])).to_numpy(),
        "derby": matches["match_id"].map(f["derby"]).to_numpy(dtype=float),
        "important": matches["match_id"].map(f["important"]).to_numpy(dtype=float),
        "kickoff_utc": matches["kickoff_utc"].to_numpy(),
    })
    if "home_yellows" in matches:
        out["y"] = (matches["home_yellows"] + matches["away_yellows"]).to_numpy(dtype=float)
    return out


def total_corner_rows(matches: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """One row per match for the total-corners model.

    Home and away corners are negatively correlated (about -0.3: the side chasing
    the game wins corners while the leader sits back), so modelling the total
    directly avoids pretending they are independent.
    """
    f = features.set_index("match_id")
    col = matches["match_id"]
    h_for, a_for = col.map(f["home_corners_for"]), col.map(f["away_corners_for"])
    h_against, a_against = col.map(f["home_corners_against"]), col.map(f["away_corners_against"])
    home_side = (h_for + a_against) / 2
    away_side = (a_for + h_against) / 2
    out = pd.DataFrame({
        "match_id": col.to_numpy(),
        "home": matches["home_id"].to_numpy(), "away": matches["away_id"].to_numpy(),
        "lopsided": np.abs(col.map(f["elo_gap"]).to_numpy()) / 100,
        "shots": (col.map(f["home_shots_for"]) + col.map(f["away_shots_for"])).to_numpy(),
        # Home side's expected share of the corners, from rolling averages at lock.
        "share": (home_side / (home_side + away_side)).fillna(0.55).to_numpy(),
        "kickoff_utc": matches["kickoff_utc"].to_numpy(),
    })
    if "home_corners" in matches:
        out["y"] = (matches["home_corners"] + matches["away_corners"]).to_numpy(dtype=float)
    return out


def _pooled(name: str, n: int, sigma, centred: bool):
    """A vector of pooled effects summing to zero; centred or non-centred form."""
    if centred:
        raw = pm.Normal(f"{name}_raw", 0.0, sigma, shape=n)
    else:
        raw = sigma * pm.Normal(f"{name}_z", 0.0, 1.0, shape=n)
    return pm.Deterministic(name, raw - pt.mean(raw))


def _likelihood(mu, y, w, poisson_only: bool):
    if poisson_only:
        dist = pm.Poisson.dist(mu=mu)
    else:
        alpha = pm.Gamma("alpha", alpha=2.0, beta=0.1)  # NB shape; large = near Poisson
        dist = pm.NegativeBinomial.dist(mu=mu, alpha=alpha)
    pm.Potential("likelihood", pt.sum(w * pm.logp(dist, y)))


def fit(train: pd.DataFrame, as_of: pd.Timestamp, teams: list[str], p: CountParams,
        referees: list[str] | None = None) -> CountPosterior:
    """train: rows from corner_rows or card_rows with y, already filtered to as_of."""
    age = (as_of - pd.to_datetime(train["kickoff_utc"], utc=True)).dt.total_seconds() / 86400
    train = train[(age <= p.window_days).to_numpy()].dropna(subset=["y"])
    age = age[age <= p.window_days].loc[train.index]
    w = np.exp(-p.xi * age.to_numpy())
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    y = train["y"].to_numpy(dtype=float)

    with pm.Model() as model:
        intercept = pm.Normal("intercept", np.log(max(y.mean(), 0.5)), 0.5)
        if p.target == "corners":
            scales = {"gap": _scale(train["gap"]), "shots": _scale(train["shots"])}
            gap = np.nan_to_num(_z(train["gap"], scales["gap"]))
            shots = np.nan_to_num(_z(train["shots"], scales["shots"]))
            home = pm.Normal("home", 0.1, 0.2)
            s_for = pm.HalfNormal("sigma_for", 0.3)
            s_against = pm.HalfNormal("sigma_against", 0.3)
            eff_for = _pooled("for", n, s_for, p.centred)
            eff_against = _pooled("against", n, s_against, p.centred)
            b_gap = pm.Normal("b_gap", 0, 0.3)
            b_shots = pm.Normal("b_shots", 0, 0.3)
            ti = train["team"].map(idx).to_numpy()
            oi = train["opponent"].map(idx).to_numpy()
            eta = (intercept + home * train["is_home"].to_numpy() + eff_for[ti]
                   + eff_against[oi] + b_gap * gap + b_shots * shots)
            names = ["intercept", "home", "for", "against", "b_gap", "b_shots",
                     "sigma_for", "sigma_against"]
            refs: list[str] = []
        else:
            spec = MATCH_COVARIATES[p.target]
            scales = {k: _scale(train[k]) for k in spec["continuous"]}
            x = np.column_stack(
                [np.nan_to_num(_z(train[k], scales[k])) for k in spec["continuous"]]
                + [train[k].to_numpy(dtype=float) for k in spec["binary"]])
            s_disc = pm.HalfNormal("sigma_disc", 0.3)
            disc = _pooled("disc", n, s_disc, p.centred)  # club effect ("discipline" for cards)
            b = pm.Normal("b", 0, 0.3, shape=x.shape[1])
            hi = train["home"].map(idx).to_numpy()
            ai = train["away"].map(idx).to_numpy()
            eta = intercept + disc[hi] + disc[ai] + pt.dot(x, b)
            names = ["intercept", "disc", "b", "sigma_disc"]
            refs = []
            if p.use_referee:
                refs = sorted(r for r in (referees or train["referee"].dropna().unique())
                              if isinstance(r, str))
                ridx = {r: i for i, r in enumerate(refs)}
                known = train["referee"].map(ridx)
                has = known.notna().to_numpy()
                s_ref = pm.HalfNormal("sigma_ref", 0.3)
                ref = _pooled("ref", len(refs), s_ref, p.centred)
                eta = eta + pt.where(has, ref[known.fillna(0).astype(int).to_numpy()], 0.0)
                names += ["ref", "sigma_ref"]
        _likelihood(pt.exp(eta), y, w, p.poisson)
        if not p.poisson:
            names.append("alpha")

    start = time.time()
    with model:
        idata = pm.sample(draws=p.draws, tune=p.tune, chains=p.chains,
                          target_accept=p.target_accept, nuts_sampler=p.sampler,
                          random_seed=p.seed, progressbar=False, var_names=names)
    seconds = time.time() - start
    summ = az.summary(idata, var_names=names, kind="diagnostics")
    diverging = idata["sample_stats"].to_dataset().get("diverging")
    post = idata["posterior"].to_dataset().stack(sample=("chain", "draw"))
    draws = {k: np.moveaxis(post[k].to_numpy(), -1, 0) for k in names}
    return CountPosterior(
        target=p.target, teams=teams, referees=refs, draws=draws, scales=scales,
        poisson=p.poisson, seconds=seconds,
        diagnostics={"rhat_max": float(summ["r_hat"].max()),
                     "ess_bulk_min": float(summ["ess_bulk"].min()),
                     "divergences": int(diverging.sum()) if diverging is not None else 0,
                     "n_rows": len(train)},
    )


def fit_checked(train: pd.DataFrame, as_of: pd.Timestamp, teams: list[str], p: CountParams,
                referees: list[str] | None = None) -> CountPosterior:
    post = fit(train, as_of, teams, p, referees)
    if post.ok:
        return post
    retry = CountParams(**{**p.__dict__, "centred": not p.centred, "draws": 2 * p.draws,
                           "seed": p.seed + 1})
    second = fit(train, as_of, teams, retry, referees)
    second.diagnostics["retried"] = True
    second.seconds += post.seconds
    return second


def _pmf(mu: np.ndarray, alpha: np.ndarray | None, k: np.ndarray) -> np.ndarray:
    """(S, K) probabilities of each count k under each draw's mean (and shape)."""
    if alpha is None:
        return poisson.pmf(k[None, :], mu[:, None])
    n = alpha[:, None]
    return nbinom.pmf(k[None, :], n, n / (n + mu[:, None]))


def predict(post: CountPosterior, row: dict, rng: np.random.Generator | None = None) -> dict:
    """Posterior predictive for one match. row holds the same fields as the training
    rows (for corners: both sides' gap and shots; for cards: home, away, referee...).
    Returns the expected total, the full pmf of the total, and over-line probabilities."""
    d = post.draws
    s = len(d["intercept"])
    alpha = None if post.poisson else d["alpha"]
    k = np.arange(MAX_COUNT[post.target] + 1)
    idx = {t: i for i, t in enumerate(post.teams)}
    if post.target == "corners":
        mus = []
        for side in ("home", "away"):
            r = row[side]
            gap = np.nan_to_num(_z([r["gap"]], post.scales["gap"]))[0]
            shots = np.nan_to_num(_z([r["shots"]], post.scales["shots"]))[0]
            eta = (d["intercept"] + d["home"] * r["is_home"] + d["for"][:, idx[r["team"]]]
                   + d["against"][:, idx[r["opponent"]]] + d["b_gap"] * gap
                   + d["b_shots"] * shots)
            mus.append(np.exp(eta))
        home_pmf, away_pmf = _pmf(mus[0], alpha, k), _pmf(mus[1], alpha, k)
        # Total = home + away, independent given the parameters: convolve per draw.
        total = np.zeros((s, len(k)))
        for j in range(len(k)):
            total[:, j] = (home_pmf[:, : j + 1] * away_pmf[:, j::-1]).sum(axis=1)
        extra = {"exp_home": float(mus[0].mean()), "exp_away": float(mus[1].mean())}
    else:
        spec = MATCH_COVARIATES[post.target]
        x = np.array([np.nan_to_num(_z([row[k]], post.scales[k]))[0] for k in spec["continuous"]]
                     + [float(row[k]) for k in spec["binary"]])
        eta = (d["intercept"] + d["disc"][:, idx[row["home"]]] + d["disc"][:, idx[row["away"]]]
               + d["b"] @ x)
        ref_known = False
        if "ref" in d:
            name = row.get("referee")
            if isinstance(name, str) and name in post.referees:
                eta = eta + d["ref"][:, post.referees.index(name)]
                ref_known = True
            else:  # unknown or new referee: average over the referee distribution
                rng = rng or np.random.default_rng(0)
                eta = eta + rng.normal(0.0, d["sigma_ref"])
        total = _pmf(np.exp(eta), alpha, k)
        extra = {"referee_known": ref_known} if post.target == "cards" else {}
    pmf = total.mean(axis=0)
    pmf = pmf / pmf.sum()
    exp_total = float((pmf * k).sum())
    out: dict = {"exp_total": exp_total, "pmf": pmf,
                 "over": {line: float(pmf[k > line].sum()) for line in LINES[post.target]}}
    if post.target == "corners_total":  # split the total by the expected share
        share = float(row.get("share", 0.55))
        out["exp_home"], out["exp_away"] = exp_total * share, exp_total * (1 - share)
    out.update(extra)
    return out
