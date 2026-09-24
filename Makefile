UV ?= uv

.PHONY: audit test lint

audit:  ## Download football-data.co.uk CSVs (cached, rate-limited) and print the audit
	$(UV) run python -m fp.audit

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check src tests scripts
	$(UV) run python scripts/check_dashes.py
