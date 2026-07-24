PYTHON := uv run

.PHONY: install lint format typecheck test check dryrun

install:
	uv sync --group dev

lint:
	$(PYTHON) ruff check .

format:
	$(PYTHON) ruff format .

typecheck:
	$(PYTHON) mypy src/vaeon

test:
	$(PYTHON) pytest tests --cov=vaeon --cov-report=term-missing

check: lint typecheck test

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) vaeon ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
