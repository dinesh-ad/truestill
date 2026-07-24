PYTHON := uv run
CORE := packages/vaeon-core/src/vaeon_core
CLI := packages/vaeon-cli/src/vaeon_cli

.PHONY: install lint format typecheck test check build dryrun

install:
	uv sync --all-packages --group dev

lint:
	$(PYTHON) ruff check .

format:
	$(PYTHON) ruff format .

typecheck:
	$(PYTHON) mypy $(CORE) $(CLI)

test:
	$(PYTHON) pytest

check: lint typecheck test

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) vaeon ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
