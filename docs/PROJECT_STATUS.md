# Truestill - Project Status & Handoff

**The first thing to read in a new session.** It says where the project stands, what happens
next and in what order, and the rules that govern how work is done here. Everything below is
current as of **2026-07-27**.

---

## 0. First fifteen minutes in a fresh clone

Everything needed to go from `git clone` to a green, trustworthy checkout. Assembled here
because it was previously spread across three sections and a README.

```sh
# 1. The one external dependency. Nothing metadata-related works without it.
sudo apt install -y libimage-exiftool-perl        # macOS: brew install exiftool
exiftool -ver

# 2. The workspace. --all-packages matters: without it the CLI and app are not installed.
uv sync --all-packages --group dev

# 3. Hooks. BOTH types - the generated hooks bake in an absolute path to .venv and stop
#    working silently if the repo directory is ever moved or renamed. Reinstall after a move.
uv run pre-commit install                          # ruff + mypy
uv run pre-commit install --hook-type commit-msg   # the no-AI-trailer guard

# 4. Prove the guard BLOCKS, not merely that it runs (see §4 - this is not paranoia,
#    26 commits once carried the wrong identity because nothing checked).
git commit --allow-empty -m "test
Co-Authored-By: someone <x@y.z>"                   # MUST be refused

# 5. Confirm your identity is right. The hook checks the message, never the author field.
git config user.name && git config user.email      # expect: dinesh-ad

# 6. The gates.
make check                                         # must be green
make e2e-install && make e2e                       # optional; needs a ~114 MB chromium
```

**What "green" looks like:** `make check` runs ruff, ruff-format, mypy over the three `src`
trees, and the full Python suite. `make e2e` is separate and opt-in - a fresh clone is green
**without** a browser installed, and that is deliberate (§6).

**If `make check` fails on a fresh clone**, suspect step 2 before suspecting the code: a
partial sync (missing `--all-packages`) is the usual cause, and `exiftool` being absent makes
metadata tests *skip* rather than fail - so a green run without it does **not** prove the
metadata path works.

---

## 1. What Truestill is

Truestill is a **local-first media organizer, de-duplicator and backup pipeline**. It analyses
a photo/video library, derives each file's folder label from that file's own metadata, and
places copies into a stable `<Label>/YYYY/MM/` tree - never re-encoding a pixel, never moving
or deleting an original except through three explicitly opt-in paths. It was built
to rescue a Google Photos Takeout export (where real capture dates survive only in JSON
sidecars) but nothing in it is Google-specific. Beyond organizing it owns the whole custody
story: content-addressed drive identity, an offline catalog of which drive holds which copy,
re-hash verification, 3-2-1 copying to a second drive, crash-safe re-layout, and reclaim of
source files that are provably backed up. Two co-equal front-ends sit on one core library -
the `truestill` CLI and `truestill-app`, a token-authenticated local web UI. **Your files never
leave your machine: no accounts, no telemetry, permanently** (`DECISIONS.md` D1).

### The rename: vaeon → truestill (2026-07-26)

The project shipped its whole pre-launch life as **vaeon** and was renamed to **truestill**
before going public, after a five-gate availability check: PyPI (`truestill-core` / `-cli` /
`-app` all free), GitHub (no repos; the bare `TrueStill` user handle exists but is dormant and
empty), npm (nothing), trademark (USPTO **and** EUIPO/TMview return zero for the exact term -
both negatives validated with a control query), and a web-presence scan (no company or product
by that name).

**Known-and-monitored residual:** *TruStile Doors* is an active US filer, but its live marks
sit in classes 019/035/040 (doors, door manufacture, online door retail) with **no software or
SaaS class**, and *stile*/*still* are not homophones. Category distance is large; the risk is
visual similarity plus an active enforcer. **Formal attorney clearance is on the
pre-monetization checklist** - do it before money changes hands.

> ⚠️ **If you re-run the trademark check, do not trust a URL-parameter search.**
> `tmsearch.uspto.gov/search/search-results?q=<term>` returns **"No results found" for every
> term**, including marks that are demonstrably live - it silently reports a false negative.
> Use the real search UI, and **always run a known-positive control query first**
> (`trustile` should return 6 USPTO hits / 7 in TMview). The same applies to scripted
> checks: Justia, Trademarkia and `uspto.report` are all Cloudflare-gated and return a
> challenge page to `curl`, not data. A clean "no results" is only meaningful once the
> control has proven the query path actually works.

**Legacy drive-marker rule (binding, do not break).** Drives initialised before the rename
carry `.vaeon-drive.json`. The canonical marker is now `.truestill-drive.json`, and:

- reads fall back to the legacy name; if both exist the **canonical file wins**
- **a read never writes** - `read_marker` runs on preview/browse paths, where writing would
  break the dry-run invariant and touch read-only mounts
- upgrading is explicit only: `truestill drives --migrate-marker ROOT`
- an upgrade copies `uuid` / `label` / `created` **verbatim** - the uuid is the catalog's
  foreign key, so re-minting would orphan every recorded copy and under-report the custody count
- the legacy file is **kept, never deleted**; retiring it is a future opt-in step

Full rules and their enforcing tests: `IMPLEMENTATION_STANDARDS.md` §3.1.

---

## 2. Current state

| | |
|---|---|
| **Feature completeness** | All planned pre-launch features shipped: organize, Takeout ingest, dedup (exact + perceptual), events/trips, drive identity, offline catalog, verify, 3-2-1 backup, configurable layout + migration, reclaim, in-place organize + `undo-organize`, and the full web UI. |
| **QA verdict** | The 2026-07-26 walkthrough returned **launch-ready** (`walkthrough-qa-report.md`), and the **soak test then found ten further defects** - see §2.1. That is the walkthrough working as designed, not failing: a scripted pass over synthetic data cannot find what a real library at real scale does. Treat "launch-ready" as *the state before the soak*, not a current verdict. |
| **Tests** | 339 Python + 16 browser end-to-end. Assert behaviour, never counts - these numbers are context, not a gate, and **must not be pasted into a doc as a target**. Re-derive with `uv run pytest --collect-only -q`. |
| **Quality gates** | `make check` = ruff lint + ruff format-check + mypy (three `src` trees) + pytest. Plus `make e2e` (opt-in, needs a browser), `uv build --all-packages`, and CI's lockfile + `pip-audit` gates. All green at `8f77de1`. |
| **CI** | `.github/workflows/ci.yml`, **two jobs**: `check` ({ubuntu, macos, windows} × Python 3.13, + Linux-only `pip-audit`) and `e2e` (chromium on ubuntu). |
| **Catalog schema** | **v10** (`CURRENT_SCHEMA_VERSION`). Tables: `files`, `albums`, `file_albums`, `events`, `skipped_clusters`, `drives`, `file_copies`, `settings`, `migration_journal`, `reclaim_journal`, `inplace_runs`, `inplace_moves`. **Next free version is v11** (v10 went to the in-place journal, not to date provenance - see `IMPLEMENTATION_STANDARDS.md` §1). |
| **Sidecar** | `catalog.cache.sqlite` beside the catalog - the hash cache. Machine-local, disposable, path-keyed; **never** part of the custody record. Delete it and nothing is lost but time. |
| **Packages** | `truestill-core` (library, `py.typed`), `truestill-cli` (the `truestill` command), `truestill-app` (the `truestill-app` UI). uv workspace, hatchling, all building clean wheels. |
| **Repo** | `github.com/dinesh-ad/truestill` (renamed from `.../vaeon`; GitHub redirects the old name - **never create a new repo called `vaeon`**, it would kill that redirect). |
| **Not yet done** | Nothing is published. No PyPI release, no public repo, no domain, no landing page. |

### 2.1 The soak test is IN PROGRESS - and it is producing findings

The user is running truestill on their **real library**. This is the launch gate (§3.1), it is
**not finished**, and it has already produced ten shipped fixes. A soak finding outranks
everything else in the queue; when one arrives, drop what you are doing.

**What the soak has found and what shipped for it (all 2026-07-27):**

| # | Finding | Shipped as |
|---|---|---|
| 1 | The organize progress display was too bare to tell you anything was happening | `538fad8` - progress display rebuilt (phase, rate, ETA, cancel) |
| 2 | The completion message said "uploaded" - backend jargon for an event that did not occur - and told no story | `538fad8` - honest completion cards; `status_label` is now the single source of outcome wording |
| 3 | Preview blocked the UI and could not be cancelled | `ff23059` - Preview runs as a job on the same SSE path as everything else |
| 4 | "Check now" on a non-backup folder rendered `NaN verified · NaN missing · NaN changed` | `49a5c4b` - `streamJob` normalizes terminal events; the whole bug *class* is gone |
| 5 | The Backups screen explained nothing about what it was for | `49a5c4b` - the screen explains itself; all six screen headers audited |
| 6 | **The golden path was broken**: organize never registered its own destination, so the app rejected the library it had just built | `9afb4b7` - `service.attach_drive` on a real organize run (`IMPLEMENTATION_STANDARDS.md` §3.1) |
| 7 | A path typed into one Backups field had to be typed again in the next | `41d0725` - known values prefill; Browse is for overriding |
| 8 | After a real backup: stale "isn't a backup yet" state, wrong wording, no completion weight, thin drive cards | `c78222a` |
| 9 | Preview re-hashed 2,275 unchanged files on every run (~16s each) - **the recorded placement trigger for the hash cache fired** | `bdce242` - `hash_cache.HashCache`, 15.8s → 4.7s |
| 10 | Every one of the above lived in client-side JavaScript, where pytest cannot reach | `9be7529` + `0103454` - the browser E2E suite, one named regression test per bug |

**The pattern worth carrying forward:** eight of the ten were *client-side truth* defects - the
screen said something the system had not done. That is what the E2E lane now exists to catch,
and why its assertions are on **text a user reads**, never element ids.

Two further items shipped in the soak era from recorded backlog work rather than from a
finding: **(q) in-place organize + `undo-organize`** (`dee4785`) and the
**performance audit's convictions** (`1e458df`, `39d889a`, `8f77de1` - see `PERFORMANCE.md`).

---

## 3. The road ahead, in order

Work these **in sequence**. Do not start a later item because an earlier one is slow.

### 1. Soak test - **the launch gate** 🔴 **IN PROGRESS**

The user runs Truestill on their **real library** for **2-3 weeks**. Nothing ships until this
passes. This is not a formality: it is the only test that exercises real drives, real volumes,
real interruptions and real heterogeneous metadata. Bugs found here outrank every other item
in this list. Treat a soak-test report as the highest-priority work in the queue.

**Status: running, ten findings shipped** (§2.1). It is not closed and there is no date on
which it closes; it closes when the user says the library is organized and the tool stopped
surprising them. **Do not start item 2 because the soak looks quiet.**

Three things the soak has already taught, recorded so they are not re-learned:

- **The engine was right; the reporting was wrong.** Not one finding was a mis-placed or
  lost file. Every one was the product describing itself incorrectly. Weight review effort
  accordingly - the user-facing string is the defect surface.
- **A recorded trigger actually fired.** The hash cache had a written placement clause
  ("earlier if the soak shows repeat-run pain at real scale"); the soak produced exactly that
  evidence and the item moved. Deferral clauses are worth writing because they get honoured.
- **Scale changes the answer.** The performance audit was only possible once there was a real
  library to measure. Two of its three convictions were invisible at fixture scale.

### 2. Repo-public audit + README with screenshots

Full read-through before the repo goes public: no stray absolute paths, no personal data in
docs or fixtures, no leftover tokens, LICENSE correct, `.gitignore` complete. Rewrite the root
README for a **newcomer** rather than a maintainer, with real screenshots and an honest
capability list.

**A first pass of this audit already ran (2026-07-26)** - commit identity unified to
`dinesh-ad` across all 55 commits, `.claude/settings.local.json` (and the stale app token in
it) removed from history, and machine-specific paths / one personal filename scrubbed from the
docs. What that pass did **not** fix, and what remains for this step:

- **The screenshots must be re-captured.** All 11 in `docs/qa-screenshots/` are pre-rename:
  they show the **`vaeon.` wordmark** and `vaeon` body copy, so none can ship in a
  user-facing README. Re-shoot on the truestill build against a **neutral demo library**
  (not the personal corpus) - best done **after the soak test**, when there is a real library
  worth photographing. They stay in the repo meanwhile as the QA evidence record.
- The remaining read-through: fixtures, LICENSE, `.gitignore` completeness.
- **The root README is the known-worst document and is only partly repaired.** A 2026-07-27
  pass removed its outright falsehoods (it claimed no runtime dependencies, and documented a
  pre-subcommand invocation that no longer exists). It is now *true but thin*: it describes
  organize and says the rest exists. The **full newcomer README with screenshots is this
  step**, not done.

### 3. PyPI publish

`truestill-core`, `truestill-cli`, `truestill-app`. All three names verified free at rename
time - **re-verify immediately before publishing**, availability is not a reservation. Build
with `make build`. Publish core first, then cli/app.

### 4. `truestill.app` landing page

Domain is **committed but not yet purchased** - buy it before this step. Static, fast,
honest. Analytics, if any, must be the Plausible-class cookieless kind described in
`DECISIONS.md` D1; the no-telemetry promise governs the product, and the site must not
undermine it in spirit.

### 5. Community announcement

**r/DataHoarder** and **r/selfhosted**, led with the **Takeout-rescue angle** - "your Google
Photos export lost its dates; here is how to get them back" is the story that lands with that
audience. Read each subreddit's self-promotion rules first. Expect and welcome scrutiny of the
privacy claims; they hold up, so answer plainly.

### 6. Post-launch

**First: BACKLOG item (n)** - the "how your dates were determined" honesty stat: surface the
provenance mix of capture dates ("82% embedded EXIF, 11% filename, 5% Takeout, 2% Undated").
The concrete first slice is making the organize result's "**N no date → Undated**" line
**explorable** rather than a bare count - validated as a real confusion in the UI walkthrough.
Persisting `date_source` is the enabling schema work.

**Then: monetization.** Open-core. A **one-time Pro license**, never a subscription-by-default.
**Offline-verified license keys - no accounts, ever** (`DECISIONS.md` D1 is binding here, and
the Audacity 2021 precedent is the recorded rationale). Pro-tier candidates already sit behind
a clean capability seam. Get formal trademark clearance before charging money.

---

## 4. Standing rules for any new session

These are not suggestions. `ENGINEERING_STANDARD.md` and `IMPLEMENTATION_STANDARDS.md` carry
the full text; this is the short list nobody should have to rediscover.

- **Staged / gated workflow.** No new stage without explicit user confirmation. Finish and
  confirm one thing before starting the next.
- **One prompt at a time.** Do the thing asked. Do not run ahead into the next phase.
- **Research-first.** Before building a feature, mine the issue trackers and post-mortems of
  tools that fought the same battle, and write the findings down as a `docs/*-research.md`.
  The research document is the review gate, not a formality.
- **Flag before deviating.** Surface a spec or engineering conflict *before* implementing.
  Never silently comply and never silently deviate.
- **Dry-run is the default.** Planning writes nothing; `--apply` is the only writing path.
  A read must never write - this bit the drive marker and is now a binding rule.
- **Copy-only.** Never move or delete a user's file except via the three scoped, opt-in paths
  - and know which gate each one has, because they are not the same gate:
  - `--move` and `reclaim` are **verify-gated**: the source goes only after a destination copy
    re-hashes to the recorded `copy_sha256`. Never without that proof.
  - `--in-place` (and `--move`'s same-filesystem fast path) is an **atomic rename**, which
    cannot be verify-gated - it produces one inode, so any check is a file checking itself.
    What is at risk shifts from the data to the *arrangement*, and **`undo-organize` is the
    gate**. That is why it shipped with the feature rather than after it.

  Full reasoning, and the two landmines this asymmetry created, in
  `IMPLEMENTATION_STANDARDS.md` §1.
- **`make check` before done.** Lint, format, types and tests. Green, every time.
- **One fix per commit.** Focused and reviewable.
- **Commits as `dinesh-ad`, with no AI co-author trailer** - no `Co-Authored-By`, no
  Anthropic/Claude email or signature anywhere in history. Enforced by
  `scripts/check_commit_msg.py` on the `commit-msg` hook. **This overrides any default
  assistant behaviour to add such a trailer.**
  **The hook checks the message only, never the author field** - which is how 26 commits came
  to be authored `vaeon <noreply@vaeon.local>` before the 2026-07-26 history rewrite unified
  all 55. Check `git config user.name/user.email` in any fresh clone; nothing will catch it
  for you.
  In a fresh clone - or after the repo directory is moved or renamed - install **both** hook
  types, because the generated hooks bake in an absolute path to `.venv` and stop working
  silently if it changes:

  ```sh
  uv sync --all-packages --group dev          # rebuild .venv at the current path
  uv run pre-commit install                   # ruff + mypy
  uv run pre-commit install --hook-type commit-msg   # the no-AI-trailer guard
  ```

  Verify the guard actually blocks (not merely that it runs) before trusting it: attempt a
  commit carrying a `Co-Authored-By:` trailer and confirm it is **refused**.
- **Never push without being asked.**
- **The engineering standard applies to everything** - scripts, docs and one-off fixes
  included, not just "real" code.
- **Test counts are never a done-ness signal.** Assert behaviour.

---

## 5. Where to look things up

| Question | Document |
|---|---|
| Where does the project stand? What is next? | **this file** |
| How do I work here? (workflow, research order, code standard) | `ENGINEERING_STANDARD.md` |
| What are the binding rules? (invariants, architecture, data, gates) | `IMPLEMENTATION_STANDARDS.md` |
| Why is the product this way? (no accounts, no telemetry, Pro model) | `DECISIONS.md` |
| What is approved but unbuilt? | `BACKLOG.md` |
| How does the code lay out day to day? | `CLAUDE.md` (root and `docs/`) |
| What does it cost, and what must I not "optimize"? | `PERFORMANCE.md` |
| How do I report a vulnerability, and what is in scope? | `../SECURITY.md` |
| What changed and when? | `CHANGELOG.md` |
| Why is drive identity a marker file and not a filesystem UUID? | `drive-identity-research.md` |
| Why is exiftool the only date reader? Why not hachoir/pymediainfo? | `metadata-chain-research.md` |
| How does Google Takeout actually store dates? | `takeout-format.md` |
| Why this folder structure, and how does a custom layout work? | `org-structure-research.md` |
| What does the UI look like and why? | `ui-v1-research.md`, `ui-v2-research.md` |
| Does the app actually work end to end? | `walkthrough-qa-report.md` + `qa-screenshots/` |
| Which formats are covered? | `format-coverage-audit.md` |

**Historical caveat:** `docs/*-research.md` and the QA report are records of what was
investigated and when. Several predate the rename and refer to `vaeon` or
`.vaeon-drive.json`; where that matters they carry an inline historical note. When a research
doc and `IMPLEMENTATION_STANDARDS.md` disagree, **the contract wins.**

---

## 6. Things worth knowing that are easy to rediscover the hard way

- **The external test corpus is referenced as `$TRUESTILL_CORPUS`** and is treated **strictly
  read-only**. Set that variable to your local corpus; the path itself is machine-specific and
  deliberately **not** recorded in the repo. It deliberately **keeps its `vaeon-` directory
  name** - the research and QA documents were produced against it under that name, and renaming
  it would invalidate those records. It is not part of the repo.
- **`exiftool` must be on `PATH`** (Ubuntu: `libimage-exiftool-perl`). Tests that need it skip
  cleanly when absent, so a green local run does **not** prove the metadata path works - CI
  exercises the real thing on Linux and macOS.
- **No legacy-marker drive has ever been seen in the wild.** At rename time a sweep of
  `/media`, `/run/media`, `/mnt` and `$HOME` found zero `.vaeon-drive.json` files and the
  catalog had zero `drives` rows. The compat path is covered by 10 unit tests *and* was
  exercised end-to-end against a deliberately forged legacy drive - but never against a real
  one. **If a genuine pre-rename drive turns up, connect it and verify before trusting it.**
- **The catalog is the only place journals live.** `migration_journal` and `reclaim_journal`
  are in the local SQLite file, never on the user's drive. The drive marker is the *only*
  Truestill-named artifact ever written to a user's drive - which is what kept the rename's
  on-disk blast radius to a single constant.
- **`reports/catalog.sqlite` is the default catalog path** for both CLI and app. It is a
  working file, not a fixture.
- **The house style is shared with `~/ad/application/nexdue`** - uv + hatchling, ruff at
  line-length 100 with double quotes, mypy `disallow_untyped_defs`, pytest, `Makefile`
  wrapping `uv run`. Match it rather than inventing a local dialect.
- **The app deliberately has no build step.** Server-rendered HTML plus vanilla JS; no npm, no
  bundler, nothing third-party vendored. Keep it that way - it is a privacy and
  auditability decision, not laziness.
- **The UI wordmark is `truestill.`** with an accent-coloured dot, monospace, in a 232px
  sidebar. It was re-checked visually after the rename and fits without wrapping.
- **The browser suite is opt-in and stays that way.** `tests/e2e/` is deliberately outside
  pytest's `testpaths`, so a fresh clone runs `make check` green with **no browser installed**.
  Run it with `make e2e-install` once, then `make e2e`. A clean install of the shipped wheels
  pulls no browser at all - and that claim is itself tested
  (`tests/e2e/test_dependency_gating.py` checks the resolver's output rather than trusting the
  manifests).
- **The E2E server runs in-process, not as a subprocess.** `create_app` is a plain factory, so
  the harness binds the socket and picks the token itself. That removes the two classic flake
  sources (scraping a port out of a child's stdout, racing its startup) and lets a test open
  the same catalog the UI is writing to. The stated cost: `__main__.py` is bypassed and stays
  uncovered.
- **`make check` and `make e2e` do not overlap, on purpose.** Engine truth (dating, dedup,
  layout, marker rules, reclaim/undo, migrations) belongs to the fast cross-OS Python tests;
  the browser lane owns only what a user reads on screen. Re-asserting engine logic through a
  browser buys nothing and costs minutes.
- **Two config values still say 3.12 while the packages require 3.13**: `[tool.mypy]
  python_version` and `[tool.ruff] target-version` in the root `pyproject.toml`. Harmless today
  (both are *floors* for the checkers, and the code is 3.13-clean), but they are stale claims
  and should be raised in the next code-touching pass. Deliberately **not** changed in the
  documentation-only pass that found them.
- **`scripts/` is linted but not type-checked.** `ruff check .` covers the whole repo; mypy is
  pointed at the three `src` trees only, and `scripts/` does not currently pass it. That is a
  real (small) gap in the fence, recorded rather than silently widened - see
  `IMPLEMENTATION_STANDARDS.md` §6.
- **Measure before optimizing, and record the number.** The performance audit convicted only
  what evidence convicted, and `PERFORMANCE.md` §4 lists the things that *look* like waste and
  must be left alone. Read it before "improving" the pipeline; the size pre-filter in
  particular is the single best optimisation in the codebase and reads like dead weight.
