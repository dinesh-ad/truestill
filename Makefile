PYTHON := uv run
CORE := packages/vaeon-core/src/vaeon_core
CLI := packages/vaeon-cli/src/vaeon_cli
APP := packages/vaeon-app/src/vaeon_app

.PHONY: install lint format typecheck test check build dryrun

install:
	uv sync --all-packages --group dev

lint:
	$(PYTHON) ruff check .

format:
	$(PYTHON) ruff format .

typecheck:
	$(PYTHON) mypy $(CORE) $(CLI) $(APP)

test:
	$(PYTHON) pytest

check: lint typecheck test

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) vaeon organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
