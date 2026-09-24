"""Keep the last good posterior per league, for the fallback rule in spec S5.1.

If today's fit fails its diagnostics even after a retry, the daily run predicts
from the last posterior that passed, and flags those rows as degraded. It never
publishes from a failed fit. Files live in data/posteriors/ and are carried
between GitHub runs by the Actions cache.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.models.bayes_dc import Posterior

STORE = ROOT / "data" / "posteriors"


def save(post: Posterior, league: str, as_of: pd.Timestamp, store: Path = STORE) -> Path:
    if not post.ok:
        raise ValueError("refusing to store a posterior that failed its diagnostics")
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{league}.npz"
    np.savez_compressed(
        path, mu=post.mu, home=post.home, rho=post.rho, att=post.att, def_=post.def_,
        teams=np.array(post.teams),
        meta=np.array(json.dumps({"as_of_utc": as_of.isoformat(), **post.diagnostics})),
    )
    return path


def load(league: str, store: Path = STORE) -> tuple[Posterior, dict] | None:
    path = store / f"{league}.npz"
    if not path.exists():
        return None
    z = np.load(path)
    meta = json.loads(str(z["meta"]))
    post = Posterior(teams=[str(t) for t in z["teams"]], mu=z["mu"], home=z["home"],
                     rho=z["rho"], att=z["att"], def_=z["def_"], diagnostics=meta)
    return post, meta
