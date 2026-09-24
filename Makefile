UV ?= uv

.PHONY: data audit rebuild test lint typecheck check

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
	$(UV) run ruff check src tests scripts
	$(UV) run python scripts/check_dashes.py

typecheck:
	$(UV) run mypy src

check: lint typecheck test  ## Everything CI runs
