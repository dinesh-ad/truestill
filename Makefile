PYTHON := uv run
CORE := packages/truestill-core/src/truestill_core
CLI := packages/vaeon-cli/src/vaeon_cli
APP := packages/vaeon-app/src/vaeon_app

.PHONY: install lint format format-check typecheck test check build dryrun

install:
	uv sync --all-packages --group dev

lint:
	$(PYTHON) ruff check .

format:
	$(PYTHON) ruff format .

# Mirror CI's read-only format gate so `make check` fails the same way CI does.
format-check:
	$(PYTHON) ruff format --check .

typecheck:
	$(PYTHON) mypy $(CORE) $(CLI) $(APP)

test:
	$(PYTHON) pytest

check: lint format-check typecheck test

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) vaeon organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
