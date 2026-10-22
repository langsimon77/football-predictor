"""Shared scoring helpers for the Europe experiments and the bookmaker benchmark."""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

MAXG, B = 10, 2000
rng = np.random.default_rng(2026)
I, J = np.meshgrid(np.arange(MAXG + 1), np.arange(MAXG + 1), indexing="ij")


def grids(lh, la, rho):
    """Score grids (n, 11, 11) with the Dixon-Coles correction, as dc.probs makes them."""
    i = np.arange(MAXG + 1)
    M = poisson.pmf(i[None, :], lh[:, None])[:, :, None] * poisson.pmf(i[None, :], la[:, None])[:, None, :]
    M[:, 0, 0] *= 1 - lh * la * rho
    M[:, 0, 1] *= 1 + lh * rho
    M[:, 1, 0] *= 1 + la * rho
    M[:, 1, 1] *= 1 - rho
    M = np.clip(M, 1e-12, None)
    return M / M.sum(axis=(1, 2), keepdims=True)


def markets(M):
    tot = I + J
    return {"p": np.stack([M[:, I > J].sum(1), M[:, I == J].sum(1), M[:, I < J].sum(1)], 1),
            "o15": M[:, tot >= 2].sum(1), "o25": M[:, tot >= 3].sum(1), "o35": M[:, tot >= 4].sum(1), "btts": M[:, (I > 0) & (J > 0)].sum(1)}


def ll3(P, y):
    return -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1))


def llb(p, k):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -np.where(k, np.log(p), np.log(1 - p))


def boot(diff):
    """Paired bootstrap of a per-match difference: mean and 95% interval."""
    n = len(diff)
    means = np.concatenate([diff[rng.integers(0, n, (min(200, B - s), n))].mean(1) for s in range(0, B, 200)])
    return {"mean": round(float(diff.mean()), 4), "lo": round(float(np.percentile(means, 2.5)), 4),
            "hi": round(float(np.percentile(means, 97.5)), 4), "n": int(n)}


