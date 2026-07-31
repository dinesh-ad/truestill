PYTHON := uv run
CORE := packages/truestill-core/src/truestill_core
CLI := packages/truestill-cli/src/truestill_cli
APP := packages/truestill-app/src/truestill_app
# scripts/ is in the type fence too: it is real code that imports the core, and the one file
# left out of it silently imported a module that had not existed for two renames.
SCRIPTS := scripts

.PHONY: install lint format format-check typecheck dash-check redirect-check test test-order check build dryrun e2e e2e-install

install:
	uv sync --all-packages --group dev

# --no-cache is not paranoia, it is the fix for a false green that reached CI twice. Ruff caches
# a verdict per file, keyed on that file's contents and the config -- so a file appearing
# ELSEWHERE in the tree, which changed how six untouched files classified their imports, was
# invisible to it. Six stale "clean" verdicts were replayed and `make check` passed while CI
# failed. Measured cost of giving that up: 0.04s -> 0.08s on this repo.
lint:
	$(PYTHON) ruff check --no-cache .

format:
	$(PYTHON) ruff format .

# Mirror CI's read-only format gate so `make check` fails the same way CI does.
format-check:
	$(PYTHON) ruff format --check .

typecheck:
	$(PYTHON) mypy $(CORE) $(CLI) $(APP) $(SCRIPTS)

test:
	$(PYTHON) pytest

# The suite in a different collection order - testpaths gives core, cli, app; passing the
# directory gives app, cli, core. Deliberately NOT in `check`: it doubles the local test wait
# to catch a class of bug that CI runs on every push (ubuntu, where it is free). Reach for it
# when touching a fixture that any two tests share.
test-order:
	$(PYTHON) pytest packages/

# Prose gates run alongside the code gates: the em-dash sweep of 2026-07-28 was invisible
# to ruff, mypy and pytest alike, because none of them can see prose.
dash-check:
	$(PYTHON) python scripts/normalize_dashes.py --check

# Empty root files named ``10.0`` / ``2024-03-24`` are shell redirects, not product files.
redirect-check:
	$(PYTHON) python scripts/check_redirect_artifacts.py

check: lint format-check typecheck dash-check redirect-check test

# --- browser end-to-end ----------------------------------------------------------------
# Deliberately outside `check` and outside pytest's testpaths: a fresh clone runs `make check`
# green with no browser installed. Run `make e2e-install` once, then `make e2e`.
e2e-install:
	$(PYTHON) playwright install --with-deps chromium

# No retries, on purpose. A retry-until-green browser suite launders exactly the
# nondeterminism this layer exists to expose; a flaky test gets quarantined and filed instead.
# Traces and video are kept only for failures, so a red run arrives with a replay.
e2e:
	$(PYTHON) pytest tests/e2e --browser chromium \
		--tracing retain-on-failure --video retain-on-failure \
		--output tests/e2e/.artifacts

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) truestill organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
