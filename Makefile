PYTHON := uv run
CORE := packages/truestill-core/src/truestill_core
CLI := packages/truestill-cli/src/truestill_cli
APP := packages/truestill-app/src/truestill_app
# scripts/ is in the type fence too: it is real code that imports the core, and the one file
# left out of it silently imported a module that had not existed for two renames.
SCRIPTS := scripts
# packaging/ is in the fence for the same reason scripts/ is: real code that imports the core.
PACKAGING := packaging

.PHONY: install lint format format-check typecheck dash-check name-check redirect-check test test-order check build dryrun e2e e2e-install

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
	$(PYTHON) mypy $(CORE) $(CLI) $(APP) $(SCRIPTS) $(PACKAGING)

# `-n auto` here rather than in `addopts`, deliberately: addopts would sweep in `test-order`
# below, whose whole value is a single deterministic collection order. Measured 89.95s -> 30.00s
# on 16 cores; expect roughly half that gain on a 2-4 core CI runner.
# --- wall-clock ceilings ----------------------------------------------------------------
# A LIMIT THAT FAILS, NOT A TARGET NOBODY READS. §4 asks for impossible rather than unlikely,
# and a suite gets slow the way it gets untested: nobody decides to, it just drifts. These are
# calibrated on the machine below with ~2.5x headroom, so they catch a doubling and ignore a
# busy laptop. Raising one is a decision to be made ON PURPOSE, with a new measurement.
#
# Calibrated 2026-08-09, 16 cores: `test` five samples 15.7-18.8s (median 17.2s); `e2e` 362.7s
# with tracing and video, 252.2s without. Override for a slower machine:
#   make check TEST_SECONDS_MAX=90
#
# NOT enforced in CI, deliberately: the same Windows step measured 566s, 1009s, 1472s and 596s
# on commits within 2% of each other, so a CI ceiling would fail on variance rather than on
# drift and would be switched off within a week. See §4's eighteenth member.
TEST_SECONDS_MAX ?= 45
E2E_SECONDS_MAX ?= 600

# `$$` throughout: this is one shell line per recipe, so the variables are the shell's, not
# make's. The test's own exit status is preserved - a ceiling must not turn a red suite green.
define time_ceiling
start=$$(date +%s); $(1); status=$$?; elapsed=$$(( $$(date +%s) - start )); \
if [ $$status -ne 0 ]; then exit $$status; fi; \
if [ $$elapsed -gt $(2) ]; then \
	echo ""; \
	echo "TOO SLOW: $(3) took $${elapsed}s, ceiling is $(2)s."; \
	echo "Measure before raising it: pytest --durations=25 names where the time went."; \
	echo "If the cost is real and wanted, raise $(4) in the Makefile in its own commit."; \
	exit 1; \
fi
endef

test:
	@$(call time_ceiling,$(PYTHON) pytest -n auto,$(TEST_SECONDS_MAX),the test lane,TEST_SECONDS_MAX)

# The suite in a different collection order - testpaths gives core, cli, app; passing the
# directory gives app, cli, core. Deliberately NOT in `check`: it doubles the local test wait
# to catch a class of bug that CI runs on every push (ubuntu, where it is free). Reach for it
# when touching a fixture that any two tests share.
#
# SERIAL, and that is the point: this pass exists to ask "is the suite green in a different
# ORDER", and a parallel run has no single order to be green in. Speeding it up would remove
# the property it tests.
test-order:
	$(PYTHON) pytest packages/

# Prose gates run alongside the code gates: the em-dash sweep of 2026-07-28 was invisible
# to ruff, mypy and pytest alike, because none of them can see prose.
dash-check:
	$(PYTHON) python scripts/normalize_dashes.py --check

# The product name is "Truestill" wherever a person reads it (docs/brand.md); the command and
# the `truestill-*` / `truestill_*` identifiers stay lowercase.
name-check:
	$(PYTHON) python scripts/check_product_name.py

# Empty root files named ``10.0`` / ``2024-03-24`` are shell redirects, not product files.
redirect-check:
	$(PYTHON) python scripts/check_redirect_artifacts.py

check: lint format-check typecheck dash-check name-check redirect-check test

# --- browser end-to-end ----------------------------------------------------------------
# Deliberately outside `check` and outside pytest's testpaths: a fresh clone runs `make check`
# green with no browser installed. Run `make e2e-install` once, then `make e2e`.
e2e-install:
	$(PYTHON) playwright install --with-deps chromium

# No retries, on purpose. A retry-until-green browser suite launders exactly the
# nondeterminism this layer exists to expose; a flaky test gets quarantined and filed instead.
# Traces and video are kept only for failures, so a red run arrives with a replay.
e2e:
	@$(call time_ceiling,$(PYTHON) pytest tests/e2e --browser chromium \
		--tracing retain-on-failure --video retain-on-failure \
		--output tests/e2e/.artifacts,$(E2E_SECONDS_MAX),the browser lane,E2E_SECONDS_MAX)

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) truestill organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
