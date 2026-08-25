PYTHON := uv run
CORE := packages/truestill-core/src/truestill_core
CLI := packages/truestill-cli/src/truestill_cli
APP := packages/truestill-app/src/truestill_app
# scripts/ is in the type fence too: it is real code that imports the core, and the one file
# left out of it silently imported a module that had not existed for two renames.
SCRIPTS := scripts
# packaging/ is in the fence for the same reason scripts/ is: real code that imports the core.
PACKAGING := packaging
# ⚠ THE FENCE IS A PROPERTY, NOT A DIRECTORY LIST, and these two are where that became visible
# ((aga), 2026-08-23). The rule the two comments above state is *real code that imports the
# core*; it was implemented as a list of directories, so a file at the repo root satisfied the
# rule and sat outside the fence anyway. `suite_scratch.py` decides where EVERY test in the
# suite writes and `conftest.py` decides what every test can reach - neither contains a test,
# asserts anything, or is collected as one. Both report ZERO errors under `strict`; being
# unchecked was never a judgement about them. Same shape as `(afu)`.
ROOT_CODE := conftest.py suite_scratch.py
# The test trees, checked under `mypy-tests.toml` rather than the strict fence above - that file
# carries the ruling and the measurement behind it. One invocation PER TREE, not one for all of
# them: the four `conftest.py` files share a module name, and mypy refuses a run that sees two.
TEST_TREES := packages/truestill-core/tests packages/truestill-cli/tests packages/truestill-app/tests tests/e2e
MYPY_TESTS := --config-file mypy-tests.toml

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
	$(PYTHON) ruff format --target-version py313 .

# Mirror CI's read-only format gate so `make check` fails the same way CI does.
format-check:
	$(PYTHON) ruff format --check --target-version py313 .

typecheck:
	$(PYTHON) mypy $(CORE) $(CLI) $(APP) $(SCRIPTS) $(PACKAGING) $(ROOT_CODE)
	@for tree in $(TEST_TREES); do $(PYTHON) mypy $(MYPY_TESTS) $$tree || exit 1; done

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
# ⚠ THE MARGIN MOVED ON 2026-08-23 AND THE CEILING DID NOT, which is `(afx)`'s rule applied to
# the other lane: a bound raised to fit its subject measures nothing. The suite's scratch left
# tmpfs for a disk (root `conftest.py`, `(afy)`), so every catalog build now pays a real `fsync`.
# Measured, three runs each, same machine, same commit:
#
#     /tmp    tmpfs   19.38  20.62  18.90 s   median 19.38 s
#     /data   ext4    27.02  22.96  22.85 s   median 22.96 s   (+18%, first run cold)
#
# 45s still holds and no test changed verdict. What changed is the headroom this file was
# calibrated on: ~2.5x -> ~2.0x, worst observed 27.02s. Stated HERE, beside the number it is
# headroom against, because that is where somebody about to raise it will be standing.
# `PERFORMANCE.md` §6 is the source for both readings; anything here is a copy.
#
# NOT enforced in CI, deliberately: the same Windows step measured 566s, 1009s, 1472s and 596s
# on commits within 2% of each other, so a CI ceiling would fail on variance rather than on
# drift and would be switched off within a week. See §4's eighteenth member.
TEST_SECONDS_MAX ?= 45
# RAISED FROM 600 WITH WEBKIT, and the WebKit addition is the justification rather than an
# excuse attached to one. The cost buys the engine the app actually ships in - WebKitGTK on
# Linux, WKWebView on macOS - and Chromium-only was never a Tauri-specific gap: the .deb
# already opens in whatever browser the user has.
#
# MEASURED, and the first number here was an estimate that came in 7% low. Chromium 434s,
# WebKit 897s alone; the combined lane measured **1431s**, not the 1330 those two suggested.
# The headroom is deliberately the same PROPORTION the previous ceiling carried (600 against a
# 434s lane, 1.38x) rather than a new tolerance invented for the occasion: 1431 x 1.38 ~= 1975.
# A 1500 ceiling would have left 4.8% margin and tripped on the first slow run, which is how a
# ceiling gets raised in a panic instead of on evidence.
E2E_SECONDS_MAX ?= 2000

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

# --- frontend ------------------------------------------------------------------------------
# `npm ci`, not `npm install`: ci installs exactly the lockfile and fails if package.json and the
# lock disagree, which is the reproducibility the frozen artifact needs. Seconds on a warm cache.
frontend-install:
	cd packages/truestill-app/frontend && npm ci

# The bundle is gitignored, so this is what a fresh clone runs before the browser lane. Cheap
# (tens of ms) and idempotent, so `e2e` depends on it rather than trusting somebody to remember:
# a stale bundle is invisible to lint, mypy and every Python test.
#
# NOT a prerequisite of `check`. `check` is green with no browser AND no Node - that is the
# fresh-clone promise in PROJECT_STATUS §0, and the bundle guard lives in the browser lane where
# a bundle is needed anyway.
#
# ⚠ `tsc --noEmit` FIRST, and it is not decoration. This target called `npx vite build` directly
# for as long as the seam has existed, which skipped the `tsc --noEmit &&` in package.json's own
# build script - so `strict`, `noUncheckedIndexedAccess` and every other compiler flag were
# configured and never read by anything. Vite strips types; it does not check them. When the
# check was finally run it was not clean: three TS2591 errors in `vite.config.ts`, unseen since
# the seam landed.
frontend:
	cd packages/truestill-app/frontend && npx tsc --noEmit && npx vite build

# --- browser end-to-end ----------------------------------------------------------------
# Deliberately outside `check` and outside pytest's testpaths: a fresh clone runs `make check`
# green with no browser installed. Run `make e2e-install` once, then `make e2e`.
# BOTH ENGINES, in one command, because "green on my machine" is the failure this target
# exists to prevent. WebKit needs four extra system libraries (libevent, libavif, libmanette,
# libwoff1); `--with-deps` installs them, which is why it is here rather than in a README step
# somebody skips.
e2e-install:
	$(PYTHON) playwright install --with-deps chromium webkit

# No retries, on purpose. A retry-until-green browser suite launders exactly the
# nondeterminism this layer exists to expose; a flaky test gets quarantined and filed instead.
# Traces and video are kept only for failures, so a red run arrives with a replay.
#
# CI CALLS THIS TARGET RATHER THAN REPEATING THE COMMAND, and that is the point of `E2E_EXTRA`.
# CI used to run its own `pytest tests/e2e --browser chromium ...`, so when this target gained
# WebKit and a frontend build, CI silently kept running neither - the coverage existed only on
# the machine that added it. One definition, and CI passes only its own reporting flags.
e2e: frontend
	@$(call time_ceiling,$(PYTHON) pytest tests/e2e --browser chromium --browser webkit \
		--tracing retain-on-failure --video retain-on-failure \
		--output tests/e2e/.artifacts $(E2E_EXTRA),$(E2E_SECONDS_MAX),the browser lane,E2E_SECONDS_MAX)

# THE MIGRATION'S EARLY-WARNING SET, and the reason it is a target rather than a note.
# These 96 tests belong to no screen, so no screen's commit carries them - and an island landing
# on a DIFFERENT screen changes the DOM around them without touching a line of their own. Run
# after every island lands; the final gate is the run that cannot tell you which island broke
# them. Chromium only on purpose: this is the fast loop, and `make gate` still runs both engines.
e2e-shell: frontend
	$(PYTHON) pytest tests/e2e -m shell --browser chromium

# --- the pre-commit gate: check always, e2e only when the diff reaches the browser ----------
# WHY A TARGET RATHER THAN A JUDGEMENT. `make check` covers everything except client-side
# behaviour, because `app.js` is not imported by Python - so no amount of it can see a defect in
# the browser. That is not a gap to close; it is why the e2e lane exists, and it is what makes
# skipping e2e sound rather than convenient. The condition must therefore be CHECKABLE, and this
# target prints its own reasoning either way so the justification can be shown rather than
# asserted.
#
# WHY THIS PATH SET, measured over 60 commits rather than chosen: `static/` and `templates/`
# alone fires on 5 and would have SKIPPED THE E2E TESTS' OWN COMMITS - eight of them in one
# session, including every readiness change. `tests/e2e/` is in the set for that reason.
# `packages/truestill-app/src/` is in it because the app's Python builds the payloads the browser
# renders, so a field renamed there breaks a screen without touching a `.js` file. Core-only and
# CLI-only work skips the lane: 45 of those 60 commits.
#
# NOT A CONTROL, and §4's twenty-seventh member says to say so: you must still choose to type
# `gate` rather than `check`. A blocking pre-commit hook was considered and refused - every
# existing hook here is sub-second, and one that can demand six minutes would be routinely
# bypassed with `--no-verify`, which is worse than an honest nudge. CI is the backstop.
BROWSER_PATHS := packages/truestill-app/src/ tests/e2e/
# THE BASE IS WHAT HAS NOT BEEN PUSHED, NOT WHAT IS UNCOMMITTED - changed from HEAD 2026-08-10.
# `HEAD` asks "does THIS commit reach the browser", which was right while every commit was pushed
# on its own. Under the standing commit-freely-push-in-batches ruling it is the wrong question:
# the batch is the unit CI sees, so a batch whose last commit is a docs edit skipped the lane
# while carrying an app.js change three commits back. Found on a real batch - 03c06b9 was docs,
# 172e3e2 was the custody sentence - where the default printed SKIPPED and `BASE=origin/main` ran
# 436 browser tests.
#
# origin/main rather than `@{upstream}`, which is the tempting general answer: on a feature branch
# the upstream is that branch's own remote copy, so the diff would NARROW to what is unpushed on
# the branch, while what CI eventually sees is the merge into main. An origin/main that is stale
# or behind only ever widens the diff, which errs toward running the lane.
#
# HEAD stays as the override, for the intermediate commits of a long batch where the lane has
# already been run once and seven minutes per commit would get `gate` abandoned for `check`.
BASE ?= origin/main

# A BASE THAT DOES NOT RESOLVE MUST NOT READ AS "NOTHING CHANGED". Measured before making the
# change above, and it is what turns a one-word edit into two branches: `git diff --name-only
# no-such-ref` exits 128 and prints nothing to stdout, so `touched` comes back empty and the old
# shape skipped the browser lane with a reassuring message. `HEAD` always resolves and could never
# reach that state; `origin/main` can be absent - no remote, a clone of a clone, a fork whose
# default branch is named something else - so moving the default INTRODUCES the failure and has to
# answer for it in the same breath. Unreadable means RUN: seven minutes costs less than a
# regression on someone else's push.
gate: check
	@if ! git rev-parse --verify --quiet $(BASE) >/dev/null; then \
	  echo ""; echo "e2e RUNNING: BASE=$(BASE) does not resolve, so the diff cannot be read."; \
	  echo "  An unreadable base must not be reported as 'nothing changed'."; echo ""; \
	  $(MAKE) --no-print-directory e2e; \
	else \
	  touched=$$(git diff --name-only $(BASE) -- $(BROWSER_PATHS); \
	             git diff --cached --name-only -- $(BROWSER_PATHS)); \
	  if [ -n "$$touched" ]; then \
	    echo ""; echo "The diff reaches the browser, so the e2e lane applies:"; \
	    echo "$$touched" | sort -u | sed 's/^/    /'; echo ""; \
	    $(MAKE) --no-print-directory e2e; \
	  else \
	    echo ""; echo "e2e SKIPPED: nothing in the diff touches $(BROWSER_PATHS)"; \
	    echo "  (checked against $(BASE). The default base is origin/main - everything"; \
	    echo "   not yet pushed; 'make gate BASE=HEAD' narrows it to the working commit.)"; \
	  fi; \
	fi

build:
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) truestill organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
