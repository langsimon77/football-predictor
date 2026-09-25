# Backtest predictions

Our own walk-forward predictions, kept because GitHub deletes workflow artifacts after 90 days and Phase 4 (stacking and calibration) needs them.

| File | Contents | Source |
|---|---|---|
| `dc_bayes_v1_walkforward_2021_2025.parquet` | 3,800 predictions of `dc_bayes_v1` (shots on target, NumPyro), 2021/22 to 2025/26, both leagues. Home, draw, away, over 2.5, BTTS, expected goals, 80% intervals, and the full 11 x 11 scoreline table per match. | GitHub Actions runs 36184624695 (2021/22, 2022/23) and 36184636547 (2023/24 to 2025/26), 25 Sep 2026 |
| `dc_bayes_v1_walkforward_2021_2025_fits.parquet` | One row per weekly fit: time, diagnostics, pass or fail. 345 fits, all passed. | Same runs |

Each prediction was made at the daily run that would have locked it, from a fit made at or before that time on results known by then.
| `cards_nb_walkforward_2021_2025.parquet` | 3,800 predictions of `cards_nb_v1`: expected total yellows, over 3.5, 4.5, 5.5, the full distribution of the total (0 to 16), whether the EPL referee was known at lock. | GitHub runs 36188267315 (tuning) and 36191021061 (test), 25 Sep 2026 |
| `corners_total_poisson_walkforward_2021_2025.parquet` | 3,800 predictions of `corners_total_poisson_v1`: expected total and per-team corners, over 8.5 to 11.5, the full distribution of the total (0 to 30). | GitHub runs 36190976694 (tuning) and 36192216819 (test), 25 Sep 2026 |
| `*_fits.parquet` | One row per weekly fit with diagnostics and, for negative binomial models, the dispersion estimate. | Same runs |
| `challengers_walkforward_2021_2025.parquet` | 15,200 predictions (3,800 each) of the four Phase 4 challengers: ordered logit, multinomial (C 0.01), Random Forest (depth 6, leaf 50), XGBoost (depth 2, 150 trees). Home, draw, away; refit date and training size per row. Settings chosen by time-ordered cross-validation on 2017/18 to 2020/21 only; refitted at the first lock of every month. | GitHub run 36195202742, 26 Sep 2026 |
| `challengers_walkforward_2021_2025_cv.parquet` | Cross-validation log loss for every setting tried. | Same run |
