# football-predictor

Predictions for every remaining 2026/27 EPL and La Liga match. Each prediction is locked 24 to 48 hours before kickoff and scored after the match against base rates, Elo, and the betting market.

Status: fast-track models live. The daily run locks predictions from Thu 8 Oct 2026.

- Latest locked predictions: [`reports/latest.md`](reports/latest.md)
- Backtest: [`reports/backtest_1f.md`](reports/backtest_1f.md)
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

Data credits: match data from [football-data.co.uk](https://www.football-data.co.uk). Fixtures from [openfootball](https://github.com/openfootball/football.json) (public domain).
