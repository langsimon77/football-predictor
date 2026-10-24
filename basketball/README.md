# Basketball (phase B0: data audit)

Started 24 Oct 2026 at Lang's request. Lang's decisions so far (docs/DECISIONS.md):
budget $0 with free sources only; team markets first (winner, handicap, total points),
player stats later; the code lives here, in its own folder, with its own ledger and daily
workflow when those exist (like `pipeline_euro/`).

Nothing here forecasts, locks or publishes anything yet. Each phase waits for Lang's approval:
B0 data audit, B1 baseline (Elo and a points model), B2 challengers, B3 choosing a model per
league, B4 live run and Model Lab display.

## Files

| File | What it does |
|---|---|
| `audit_sample.py` | Reads the open sources (English Wikipedia, CC BY-SA 4.0) at the project's polite rate and counts games, dates, tip-off times and scores per league and season; cross-checks them. Writes `data/basketball/audit_sample.json`. |

Run it with `uv run python basketball/audit_sample.py` (add `--offline` to use cached copies).
Tests: `tests/test_basketball_audit.py`. Findings: `reports/basketball_data_audit_2026_10.md`.
