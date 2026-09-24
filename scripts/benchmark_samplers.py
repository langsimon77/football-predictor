"""Benchmark NUTS samplers on the real model (spec S5.1: pick the faster on the runner).

Fits the EPL and La Liga models as of the first lock after the international
break, with and without the shots-on-target layer, once per sampler, through
fit_checked (centred first, non-centred retry), exactly as the daily run does.
Times include each sampler's compile step, which the daily run also pays. Prints a
Markdown table; the workflow writes it to the job summary.

    uv run python scripts/benchmark_samplers.py
"""

from __future__ import annotations

import os
import platform
import sys

import pandas as pd

from fp.ingest.matches import PROCESSED
from fp.models import bayes_dc
from fp.models.priors import season_teams
from fp.models.promotion import fit_promotion_model, promoted_priors
from fp.validate.leakage import known_as_of

AS_OF = pd.Timestamp("2026-10-08 04:41", tz="UTC")
SAMPLERS = ("nutpie", "numpyro")


def main() -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    second_tier = pd.read_parquet(PROCESSED / "second_tier.parquet")
    fixtures = pd.read_parquet(PROCESSED / "fixtures.parquet")
    promo = fit_promotion_model(matches, second_tier)
    rows = []
    for league in ("EPL", "LaLiga"):
        lg = matches[matches["league"] == league]
        tbs = season_teams(matches, league)
        tbs[2026] = set(fixtures.loc[fixtures["league"] == league, "home_id"])
        teams = sorted(tbs[2026])
        priors = promoted_priors(promo, tbs, second_tier, league, 2026)
        known = known_as_of(lg, AS_OF)
        for sot in (False, True):
            for sampler in SAMPLERS:
                params = bayes_dc.BayesParams(sampler=sampler, use_sot=sot)
                post = bayes_dc.fit_checked(known, AS_OF, teams, priors, params)
                d = post.diagnostics
                rows.append({
                    "league": league, "shots_on_target": sot, "sampler": sampler,
                    "seconds": round(post.seconds, 1), "rhat_max": round(d["rhat_max"], 4),
                    "ess_bulk_min": int(d["ess_bulk_min"]), "divergences": d["divergences"],
                    "retried": bool(d.get("retried", False)), "ok": post.ok,
                })
                print(rows[-1], flush=True)
    cpu = os.cpu_count()
    table = pd.DataFrame(rows)
    lines = [f"Machine: {platform.platform()}, {cpu} CPUs, Python {platform.python_version()}",
             "", "| " + " | ".join(table.columns) + " |", "|" + "---|" * len(table.columns)]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in table.itertuples(index=False)]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
