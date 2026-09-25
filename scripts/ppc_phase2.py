"""Posterior predictive checks for the Bayesian Dixon-Coles model (Phase 2).

Fits each league as of the end of 2025/26, then replays the 2025/26 season many
times from the posterior. If the model is sound, the real season should look like
a typical replay. Saves reports/figures/ppc_<league>.png.

    uv run python scripts/ppc_phase2.py
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fp import ROOT  # noqa: E402
from fp.ingest.matches import PROCESSED  # noqa: E402
from fp.models import bayes_dc  # noqa: E402
from fp.models.priors import season_teams  # noqa: E402
from fp.models.promotion import fit_promotion_model, promoted_priors  # noqa: E402
from fp.validate.leakage import known_as_of  # noqa: E402

SEASON = 2025
REPLAYS = 400
OUT = ROOT / "reports" / "figures"
# Colour-blind-safe pair (Okabe-Ito blue and vermillion).
REPLAY_COLOUR, OBSERVED_COLOUR = "#0072B2", "#D55E00"


def replay(post: bayes_dc.Posterior, games: pd.DataFrame, rng: np.random.Generator):
    """Simulate every match once per posterior draw subset; returns (REPLAYS, n) goals."""
    draws = rng.choice(len(post.mu), REPLAYS, replace=False)
    home = np.empty((REPLAYS, len(games)), dtype=int)
    away = np.empty_like(home)
    for j, r in enumerate(games.itertuples()):
        mats = post.score_matrices(str(r.home_id), str(r.away_id))[draws].reshape(REPLAYS, -1)
        cells = np.array([rng.choice(mats.shape[1], p=row) for row in mats])
        home[:, j], away[:, j] = np.divmod(cells, bayes_dc.MAX_GOALS + 1)
    return home, away


def main() -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    second_tier = pd.read_parquet(PROCESSED / "second_tier.parquet")
    promo = fit_promotion_model(matches, second_tier)
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    for league in ("EPL", "LaLiga"):
        lg = matches[matches["league"] == league]
        games = lg[lg["season"] == SEASON]
        as_of = games["result_available_utc"].max()
        teams = sorted(set(lg["home_id"]) | set(lg["away_id"]))
        priors = promoted_priors(promo, season_teams(matches, league), second_tier, league,
                                 SEASON)
        post = bayes_dc.fit_checked(known_as_of(lg, as_of), as_of, teams, priors,
                            bayes_dc.BayesParams(xi=0.0, window_days=330))
        h, a = replay(post, games, rng)
        x, y = games["home_goals"].to_numpy(), games["away_goals"].to_numpy()
        stats = {
            "Goals per match": ((h + a).mean(axis=1), (x + y).mean()),
            "Draw share": ((h == a).mean(axis=1), (x == y).mean()),
            "0-0 share": (((h == 0) & (a == 0)).mean(axis=1), ((x == 0) & (y == 0)).mean()),
            "Home win share": ((h > a).mean(axis=1), (x > y).mean()),
        }
        fig, axes = plt.subplots(1, 4, figsize=(14, 3.2))
        for ax, (title, (sim, obs)) in zip(axes, stats.items(), strict=True):
            ax.hist(sim, bins=25, color=REPLAY_COLOUR, alpha=0.7, label="model replays")
            ax.axvline(obs, color=OBSERVED_COLOUR, lw=2.5, label="real season")
            pct = (sim < obs).mean()
            ax.set_title(f"{title}\nreal season at replay percentile {pct:.0%}", fontsize=9)
            ax.tick_params(labelsize=8)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"{league} {SEASON}/{(SEASON + 1) % 100:02d}: 400 model replays "
                     "against the real season", fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / f"ppc_{league}.png", dpi=110)
        plt.close(fig)
        print(league, {k: f"obs {v[1]:.3f}, replay pct {(v[0] < v[1]).mean():.0%}"
                       for k, v in stats.items()}, post.diagnostics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
