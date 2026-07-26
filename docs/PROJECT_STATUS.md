# Truestill - Project Status & Handoff

**The first thing to read in a new session.** It says where the project stands, what happens
next and in what order, and the rules that govern how work is done here. Everything below is
current as of **2026-07-26**.

---

## 1. What Truestill is

Truestill is a **local-first media organizer, de-duplicator and backup pipeline**. It analyses
a photo/video library, derives each file's folder label from that file's own metadata, and
places copies into a stable `<Label>/YYYY/MM/` tree - never re-encoding a pixel, never moving
or deleting an original except through two explicitly opt-in, verify-gated paths. It was built
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
| **Feature completeness** | All planned pre-launch features shipped: organize, Takeout ingest, dedup (exact + perceptual), events/trips, drive identity, offline catalog, verify, 3-2-1 backup, configurable layout + migration, reclaim, and the full web UI. |
| **QA verdict** | **Launch-ready.** Every screen passes on the fixed build (Organize · Trips & events · Import · Backups · Find · Settings · first-run empty states · clean console). All four blockers from the first walkthrough are fixed and regression-tested. See `walkthrough-qa-report.md`. |
| **Tests** | 259 passing. Assert behaviour, never counts - this number is context, not a gate. |
| **Quality gates** | `make check` = ruff lint + ruff format-check + mypy (all three `src` trees) + pytest. Green. |
| **CI** | `.github/workflows/ci.yml` - {ubuntu, macos, windows} × Python 3.13. Green on the rename. |
| **Catalog schema** | **v9** (`CURRENT_SCHEMA_VERSION`). Tables: `files`, `albums`, `file_albums`, `events`, `skipped_clusters`, `drives`, `file_copies`, `settings`, `migration_journal`, `reclaim_journal`. |
| **Packages** | `truestill-core` (library, `py.typed`), `truestill-cli` (the `truestill` command), `truestill-app` (the `truestill-app` UI). uv workspace, hatchling, all building clean wheels. |
| **Repo** | `github.com/dinesh-ad/truestill` (renamed from `.../vaeon`; GitHub redirects the old name - **never create a new repo called `vaeon`**, it would kill that redirect). |
| **Not yet done** | Nothing is published. No PyPI release, no public repo, no domain, no landing page. |

---

## 3. The road ahead, in order

Work these **in sequence**. Do not start a later item because an earlier one is slow.

### 1. Soak test - **the launch gate** 🔴

The user runs Truestill on their **real library** for **2-3 weeks**. Nothing ships until this
passes. This is not a formality: it is the only test that exercises real drives, real volumes,
real interruptions and real heterogeneous metadata. Bugs found here outrank every other item
in this list. Treat a soak-test report as the highest-priority work in the queue.

### 2. Repo-public audit + README with screenshots

Full read-through before the repo goes public: no stray absolute paths, no personal data in
docs or fixtures, no leftover tokens, LICENSE correct, `.gitignore` complete. Rewrite the root
README for a **newcomer** rather than a maintainer, with real screenshots (the QA set in
`docs/qa-screenshots/` is a starting point) and an honest capability list.

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
- **Copy-only.** Never move or delete a user's file except via the two scoped, verify-gated,
  opt-in paths (`--move`, `reclaim`), and never without proving the destination copy re-hashes.
- **`make check` before done.** Lint, format, types and tests. Green, every time.
- **One fix per commit.** Focused and reviewable.
- **Commits as `dinesh-ad`, with no AI co-author trailer** - no `Co-Authored-By`, no
  Anthropic/Claude email or signature anywhere in history. Enforced by
  `scripts/check_commit_msg.py` on the `commit-msg` hook; activate it in a fresh clone with
  `uv run pre-commit install --hook-type commit-msg`. **This overrides any default assistant
  behaviour to add such a trailer.**
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

- **The external test corpus lives at `/home/dinesh/Damon/vaeon-corpus`** and is treated
  **strictly read-only**. It deliberately **keeps its `vaeon-` name** - the research and QA
  documents cite that exact path, and renaming it would invalidate those records. It is not
  part of the repo.
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
