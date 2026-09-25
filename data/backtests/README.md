# Backtest predictions

Our own walk-forward predictions, kept because GitHub deletes workflow artifacts after 90 days and Phase 4 (stacking and calibration) needs them.

| File | Contents | Source |
|---|---|---|
| `dc_bayes_v1_walkforward_2021_2025.parquet` | 3,800 predictions of `dc_bayes_v1` (shots on target, NumPyro), 2021/22 to 2025/26, both leagues. Home, draw, away, over 2.5, BTTS, expected goals, 80% intervals, and the full 11 x 11 scoreline table per match. | GitHub Actions runs 36184624695 (2021/22, 2022/23) and 36184636547 (2023/24 to 2025/26), 25 Sep 2026 |
| `dc_bayes_v1_walkforward_2021_2025_fits.parquet` | One row per weekly fit: time, diagnostics, pass or fail. 345 fits, all passed. | Same runs |

Each prediction was made at the daily run that would have locked it, from a fit made at or before that time on results known by then.
