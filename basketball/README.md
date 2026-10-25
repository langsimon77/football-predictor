# Basketball (phases B0 to B2)

Started 24 Oct 2026 at Lang's request. Lang's decisions so far (docs/DECISIONS.md):
budget $0 with free sources only; team markets first (winner, handicap, total points),
player stats later; the code lives here, in its own folder, with its own ledger and daily
workflow when those exist (like `pipeline_euro/`).

Nothing here forecasts, locks or publishes anything yet. Each phase waits for Lang's approval:
B0 data audit (done), B1 baseline with Elo and a points model (done), B2 challengers (built), B3 choosing a model per league, B4 live run and Model Lab display.

## Files

| File | What it does |
|---|---|
| `audit_sample.py` | B0: reads the open sources (English Wikipedia, CC BY-SA 4.0) at the project's polite rate and counts games, dates, tip-off times and scores per league and season; cross-checks them. Writes `data/basketball/audit_sample.json`. |
| `data.py` | B1: builds the EuroLeague and NBL regular-season game tables (club IDs from Wikipedia links, EuroLeague cross-check against the results grids). Writes `data/processed/basketball/games.parquet` (outside Git) and `data/basketball/b1_data_summary.json`. |
| `models.py` | B1: Elo, the points model, the naive benchmarks and the scores (log loss, CRPS, calibration, bootstrap). |
| `backtest.py` | B1: `tune` chooses settings on the tuning seasons (`data/basketball/b1_settings.json`); `test` scores the test seasons once (`data/basketball/b1_results.json`). |
| `locations.py` | B2: each club's home city and coordinates from Wikipedia, for travel distances (`data/manual/basketball_club_cities.csv`). |
| `features.py` | B2: the challengers' inputs (Elo, points model, rest, travel, form, season stage, last 10 results), from earlier days only. |
| `challengers.py` | B2: the seven challengers (regression, random forest, XGBoost, histogram boosting, small neural network, Kalman ratings, club home edges). |
| `backtest_b2.py` | B2: `tune` (`data/basketball/b2_settings.json`), then `test` once (`data/basketball/b2_results.json`). |

Run order: `uv run python basketball/data.py`, then `basketball/backtest.py tune` and
`basketball/backtest.py test` (add `--offline` to the data step to use cached copies).
Tests: `tests/test_basketball_audit.py`, `tests/test_basketball_b1.py`, `tests/test_basketball_b2.py`.
Findings: `reports/basketball_data_audit_2026_10.md`, `reports/basketball_b1_backtest_2026_10.md`,
`reports/basketball_b2_challengers_2026_10.md`.
Rules: `data/audit/preregistration_basketball_b1_2026_10.md`, `..._b2_2026_10.md`.
