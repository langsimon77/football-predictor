# football-predictor

Predictions for every remaining 2026/27 EPL and La Liga match. Each prediction is locked 24 to 48 hours before kickoff and scored after the match against base rates, Elo, and the betting market.

Status: live. The Bayesian model is published, with corners, cards, team news from a daily question queue, and confidence tiers. The first locks are on Thu 8 Oct 2026.

- Fixtures page (fast, phone friendly): [https://langsimon77.github.io/football-predictor/](https://langsimon77.github.io/football-predictor/)
- Dashboard (seven pages; wakes in about 30 seconds after a quiet night): [https://football-predictor-hvplshfcfv7vsqqkaplmbq.streamlit.app/](https://football-predictor-hvplshfcfv7vsqqkaplmbq.streamlit.app/)
- Latest locked predictions: [`reports/latest.md`](reports/latest.md)
- Backtests: [`reports/backtest_phase4.md`](reports/backtest_phase4.md), [`reports/backtest_1f.md`](reports/backtest_1f.md)
- Model card: [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md)
- How it works, in plain English: [`docs/LEARN.md`](docs/LEARN.md)
- Plan and state: [`docs/PRD.md`](docs/PRD.md), [`docs/CHECKPOINT.md`](docs/CHECKPOINT.md)

## Setup

```bash
uv sync
```

## Commands

| Command | What it does |
|---|---|
| `make audit` | Downloads football-data.co.uk and openfootball files (cached, rate-limited) and prints coverage. |
| `make test` | Runs the unit tests. Run `make audit` first so the data tests have files. |
| `make lint` | Runs `ruff` and the dash check. |
| `make data` | Downloads, builds, and validates every table; writes DuckDB views. |
| `make backtest` | Tunes and tests the fast models; writes `reports/backtest_1f.md`. |
| `make daily-dry` | Runs the daily pipeline without writing anything. |
| `uv sync --group dashboard` then `uv run streamlit run app/Home.py` | Runs the dashboard locally. |

Data credits: match data from [football-data.co.uk](https://www.football-data.co.uk). Fixtures from [openfootball](https://github.com/openfootball/football.json) (public domain).
