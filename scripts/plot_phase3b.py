"""Calibration plots for the corners and cards test seasons (Phase 3b acceptance).

For each over/under line: matches split into ten equal groups by forecast chance
of going over; each point is a group's mean forecast against how often it went over.
Points on the diagonal mean honest forecasts.

    uv run python scripts/plot_phase3b.py TEST_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fp import ROOT  # noqa: E402
from fp.ingest.matches import PROCESSED  # noqa: E402

MODELS = {"cards": ("nb", ("home_yellows", "away_yellows"), (3.5, 4.5, 5.5)),
          "corners_total": ("poisson", ("home_corners", "away_corners"),
                            (8.5, 9.5, 10.5, 11.5))}
COLOURS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]  # Okabe-Ito, colour-blind safe


def main(folder: Path) -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet").set_index("match_id")
    out_dir = ROOT / "reports" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for target, (variant, (h, a), lines) in MODELS.items():
        files = [f for f in folder.rglob(f"test_{target}_*_{variant}.parquet")
                 if not f.name.endswith(".fits.parquet")]
        preds = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        total = (matches.loc[preds["match_id"], h].to_numpy()
                 + matches.loc[preds["match_id"], a].to_numpy())
        fig, ax = plt.subplots(figsize=(5.2, 5))
        ax.plot([0, 1], [0, 1], color="grey", lw=1, ls="--", label="perfect")
        for colour, line in zip(COLOURS, lines, strict=False):
            p = preds[f"p_over_{str(line).replace('.', '_')}"].to_numpy()
            groups = np.array_split(np.argsort(p), 10)
            ax.plot([p[g].mean() for g in groups], [(total[g] > line).mean() for g in groups],
                    "o-", color=colour, label=f"over {line}")
        name = "Yellow cards" if target == "cards" else "Corners"
        ax.set_title(f"{name}, 2023/24 to 2025/26: forecast against what happened\n"
                     f"{len(preds)} matches, ten equal groups per line", fontsize=9)
        ax.set_xlabel("forecast chance of going over")
        ax.set_ylabel("share that went over")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"calibration_{target}.png", dpi=110)
        plt.close(fig)
        print("saved", out_dir / f"calibration_{target}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
