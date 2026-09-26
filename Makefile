UV ?= uv

.PHONY: data audit rebuild test lint typecheck check backtest daily-dry

data:  ## Download (cached, rate-limited), build, validate, load DuckDB
	$(UV) run python -m fp.pipeline.data

audit:  ## Print source coverage tables (Phase 0)
	$(UV) run python -m fp.audit

rebuild:  ## Rebuild every derived file from the raw downloads
	rm -rf data/processed
	$(UV) run python -m fp.pipeline.data --offline

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check src tests scripts app
	$(UV) run python scripts/check_dashes.py

typecheck:
	$(UV) run mypy src

check: lint typecheck test  ## Everything CI runs

backtest:  ## Phase 1F walk-forward backtest; writes reports/backtest_1f.md
	$(UV) run python scripts/backtest_1f.py

daily-dry:  ## Run the daily pipeline without writing anything
	$(UV) run python -m fp.pipeline.daily --dry-run
