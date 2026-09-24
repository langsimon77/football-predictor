# football-predictor

Predictions for every remaining 2026/27 EPL and La Liga match. Each prediction is locked 24 to 48 hours before kickoff and scored after the match against base rates, Elo, and the betting market.

Status: Phase 0 (data audit) complete, awaiting approval. See `docs/PRD.md` for the plan, `docs/DATA_SOURCES.md` for the sources, and `docs/CHECKPOINT.md` for the latest state.

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

Data credits: match data from [football-data.co.uk](https://www.football-data.co.uk). Fixtures from [openfootball](https://github.com/openfootball/football.json) (public domain).
