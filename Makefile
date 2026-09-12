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
# BOTH platforms, because mypy resolves `sys.platform` for the HOST and prunes the other arm.
# A correct cross-platform helper therefore looks unreachable on exactly one of them, and on
# 2026-08-25 the Windows lane was the only thing that saw it - three minutes after the push.
# Checking win32 here costs about four seconds and moves that finding to the inner loop.
MYPY_PLATFORMS := linux win32

.PHONY: install lint format format-check typecheck dash-check name-check redirect-check test test-order check build dryrun e2e e2e-install e2e-fast e2e-loop look

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
	@for plat in $(MYPY_PLATFORMS); do for tree in $(TEST_TREES); do $(PYTHON) mypy $(MYPY_TESTS) --platform $$plat $$tree || exit 1; done; done

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
# ⚠ **THAT SENTENCE EXPIRED AND NOBODY NOTICED FOR NINETEEN DAYS.** By 2026-09-11 the worst
# observed was 44s against the same 45s ceiling - 2% headroom, not 2.0x - and the ceiling was
# raised to 90 rather than the measurement being argued with. The paragraph is kept because it
# is the record of 2026-08-23 and its reasoning is why the raise was measured first.
# `PERFORMANCE.md` §6 is the source for both readings; anything here is a copy.
#
# NOT enforced in CI, deliberately: the same Windows step measured 566s, 1009s, 1472s and 596s
# on commits within 2% of each other, so a CI ceiling would fail on variance rather than on
# drift and would be switched off within a week. See §4's eighteenth member.
# ⚠ RAISED 45 -> 90 ON 2026-09-11, ON A FRESH MEASUREMENT, BECAUSE 45 HAD STOPPED MEASURING THE
# CODE. The suite had grown into its own ceiling: five samples on a quiet machine, same commit,
# `pytest -n auto` exactly as the recipe runs it, read 44 / 38 / 40 / 40 / 39 s - median 40,
# worst 44, against a ceiling of 45. That is 2-11% headroom where the calibration above claims
# ~2.0x, so the gate was firing on ordinary variance rather than on drift. It fired FOUR times in
# one session on an identical suite, three of them under CPU contention from a second local run,
# and the fourth was simply a 44 s sample.
#
# 90 is the worst observed (44) at the ~2.0x this file already argues for, and it is not a new
# number: the override line above has offered `TEST_SECONDS_MAX=90` for a slow machine since
# 2026-08-09. The 2026-08-09 calibration (15.7-18.8 s) and the 2026-08-23 one (median 22.96 s on
# ext4) are left above as the record of what was true then.
#
# ⚠ **AND IT STAYS A WALL CLOCK. DO NOT PROPOSE CPU TIME AGAIN - it was measured and refused.**
# The case for it is that CPU is immune to contention where wall is not. Measured 2026-09-11 with
# bash's `times` builtin, which does see the xdist workers because they are forked children:
# four uncontended runs cost 352.2 / 357.1 / 363.9 / 367.4 s of child CPU against 42-44 s of
# wall, and one contended run cost 389.0 s against 48 s. So CPU moved 7.9% where wall moved 14% -
# less sensitive, NOT immune, because contention costs real CPU in cache pressure and scheduling.
# The deciding objection is the other one: **a CPU ceiling cannot see I/O wait**, and `(afy)`
# measured exactly that cost when the suite's scratch left tmpfs for ext4 - median 19.38 s to
# 22.96 s, **+18%**, every bit of it `fsync` this machine waits on and spends no CPU during. A
# ceiling blind to an 18% regression in the thing the product actually does to a disk is a worse
# instrument than a noisy one.
TEST_SECONDS_MAX ?= 90
# RAISED FROM 600 WITH WEBKIT, and the WebKit addition is the justification rather than an
# excuse attached to one. The cost buys the engine the app actually ships in - WebKitGTK on
# Linux, WKWebView on macOS - and Chromium-only was never a Tauri-specific gap: the .deb
# already opens in whatever browser the user has.
#
# MEASURED 2026-08-22, and the first number was an estimate that came in 7% low. Chromium 434s,
# WebKit 897s alone; the combined lane measured **1431s**, not the 1330 those two suggested.
# The headroom was deliberately the same PROPORTION the previous ceiling carried (600 against a
# 434s lane, 1.38x) rather than a new tolerance invented for the occasion: 1431 x 1.38 ~= 1975,
# taken to 2000. A 1500 ceiling would have left 4.8% margin and tripped on the first slow run,
# which is how a ceiling gets raised in a panic instead of on evidence.
#
# ⚠ **RECALIBRATED 2026-09-12 TO 2750, AND 2000 HAD 9 SECONDS LEFT IN IT.** The lane grew from
# 1431s to 1991s in three weeks - the same suite plus the import, recover and rail work - and
# nothing said so, because a ceiling only speaks when it is crossed. Measured twice back to back
# on this machine (AMD Ryzen 7 4800H, 16 cores, 30 GiB, ext4, load avg ~3.5 from an editor and a
# browser):
#
#     1991.00s (0:33:10)   1984.85s (0:33:04)      `make e2e`, both engines, serial, 1224 passed
#     1914.84s (0:31:54)   CI, run 34676698335     ubuntu-latest, nproc = 4, same commit
#
# ⚠ **0.45% of headroom against 2000.** The next run was going to be red on the clock while
# every test passed, and the diagnosis would have been "the browser lane is broken" rather than
# "the suite grew 39%". That is `(akm)`'s class arriving a third time: a number derived from a
# measurement, stored as a literal, unable to go red when its derivation moves.
#
# 2750 is the SAME 1.38 proportion applied to the new worst sample - 1991 x 1.38 = 2748 - and
# not a round number chosen to feel safe. It is deliberately derived the way the line above it
# was, so the next person recalibrating has one method rather than two.
#
# ⚠ **CI DOES NOT USE THIS NUMBER AND NEVER HAS.** `.github/workflows/ci.yml`'s E2E step passes
# `E2E_SECONDS_MAX=3600` explicitly. This default governs a local `make e2e` only. A comment in
# that file claimed the job "enforces its own 2000 s ceiling" until 2026-09-12; it did not.
# ⚠ **AND IT MOVES WITH `E2E_BROWSERS`, because a ceiling calibrated for a 33-minute run is not
# a ceiling on a 10-minute one - it is a number that would let the chromium leg TRIPLE before
# saying anything.** Each is the same 1.38 proportion applied to that selection's own measurement,
# taken 2026-09-12 on this machine (AMD Ryzen 7 4800H, 16 cores, ext4), serial, all green:
#
#     chromium   638.55s (0:10:38), 632 tests     x1.38 ->  881  -> 900
#     webkit    1320.67s (0:22:01), 632 tests     x1.38 -> 1823  -> 1850
#     both      1991.00s (0:33:11), 1227 tests    x1.38 -> 2748  -> 2750
#
# The two legs sum to 1959s against 1991s for the combined lane, so splitting costs no real
# runner time - it buys WALL-CLOCK, and only in CI where the legs run on separate machines.
#
# ⚠ **A selection this does not know gets the combined ceiling**, deliberately: too loose is a
# quiet gate, and too tight is a red run on a configuration nobody calibrated. The first is
# recoverable by reading; the second gets the ceiling raised in a panic.
ifeq ($(strip $(E2E_BROWSERS)),chromium)
E2E_SECONDS_MAX ?= 900
else ifeq ($(strip $(E2E_BROWSERS)),webkit)
E2E_SECONDS_MAX ?= 1850
else
E2E_SECONDS_MAX ?= 2750
endif

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
# ONE DEFINITION, in `package.json`'s `build` script, so the release lane and this target cannot
# drift: `(ajv)` is what drifting looked like - `make e2e` built the bundle through this target
# and `release.yml` built nothing, so the lane was green for nineteen days over a bundle the
# release never had. The lane and the release now run the same script.
frontend:
	cd packages/truestill-app/frontend && npm run build

# --- look at the product ---------------------------------------------------------------
# A SCRATCH LIBRARY FOR LOOKING AT THE PRODUCT, NOT A FIXTURE. `/data/TruestillLibrary/look` is
# 261 real files copied out of the maintainer's library on 2026-09-05 for variety - fourteen
# years, portrait and landscape and square, six videos, thirteen undated, a truncated JPEG and an
# unreadable one - organized once into `Library/` with the catalog beside it. Nothing here can
# reach the dev catalog or a real library: the catalog, the data dir and the cache dir all live
# under that one folder, and the port is not the dev default. One command, then open the URL it
# prints. No test reads this folder and none may: it is a snapshot, never a premise.
LOOK_ROOT ?= /data/TruestillLibrary/look
look: frontend
	@test -f $(LOOK_ROOT)/catalog.sqlite || { echo "no look library at $(LOOK_ROOT) (LOOK_ROOT=... to point elsewhere)"; exit 1; }
	TRUESTILL_DATA_DIR=$(LOOK_ROOT)/data TRUESTILL_CACHE_DIR=$(LOOK_ROOT)/cache \
		$(PYTHON) truestill-app --db $(LOOK_ROOT)/catalog.sqlite --port 7358 --no-browser

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
# ⚠ ONE WAY TO SELECT ENGINES, AND IT IS `--browser`. `e2e-loop` below uses `-k chromium`, which
# DESELECTS - a different thing that also drops the 37 tests parameterised by no engine at all.
# This variable drives the real flag, so a leg that asks for one engine gets that engine's cases
# plus the engine-independent ones, which is what a leg has to run to be worth splitting out.
E2E_BROWSERS ?= chromium webkit
# Built here rather than inline: `$(call ...)` splits its arguments on commas, and a `foreach`
# written inside the call below would be read as three arguments.
e2e_browser_flags = $(foreach browser,$(E2E_BROWSERS),--browser $(browser))

e2e: frontend
	@$(call time_ceiling,$(PYTHON) pytest tests/e2e $(e2e_browser_flags) \
		--tracing retain-on-failure --video retain-on-failure \
		--output tests/e2e/.artifacts $(E2E_EXTRA),$(E2E_SECONDS_MAX),the browser lane,E2E_SECONDS_MAX)

# The same lane under `-n auto`, both engines - run before a commit that reaches a screen.
# Measured 2026-09-05 on 16 cores: 289 s against 1593 s serial, all green, longest call 14.16 s
# under the 30 s assertion budget. `e2e` stays serial: that is the shape CI runs on 4 cores.
e2e-fast:
	@$(MAKE) --no-print-directory e2e E2E_EXTRA="-n auto $(E2E_EXTRA)"

# The iterating loop: chromium only, under `-n auto`. Measured 2026-09-05 on 16 cores: 95 s.
# `-k chromium` deselects the webkit cases, so `e2e-fast` before the commit is what sees them.
e2e-loop:
	@$(MAKE) --no-print-directory e2e E2E_EXTRA="-n auto -k chromium $(E2E_EXTRA)"

# THE MIGRATION'S EARLY-WARNING SET, and the reason it is a target rather than a note.
# The tests marked `shell` (`$(PYTHON) pytest tests/e2e -m shell --collect-only -q` counts them;
# a number written here said 96 while it collected 111) belong to no screen, so no screen's
# commit carries them - and an island landing
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
	  touched=$$(git diff --name-only $(BASE) -- $(BROWSER_PATHS) && \
	             git diff --cached --name-only -- $(BROWSER_PATHS)) || { \
	    echo ""; echo "e2e RUNNING: git diff against $(BASE) failed, so the diff cannot be read."; \
	    echo "  A substitution reports its OUTPUT, and 'could not read' is the same empty string"; \
	    echo "  as 'nothing changed' - so an unreadable diff runs the lane rather than skipping it."; \
	    echo ""; $(MAKE) --no-print-directory e2e; exit $$?; }; \
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

# The wheel sweeps `src/truestill_app` in, so it carries `static/dist/` only if it was built
# first. `(ajv)`: an artifact without the bundle serves a page that 404s it.
build: frontend
	uv build --all-packages

# Dry run against the staging test set. Writes nothing.
dryrun:
	$(PYTHON) truestill organize ~/gphotos-staging/takeout-test/extracted /tmp/organized-preview
