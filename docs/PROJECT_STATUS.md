# Truestill - Project Status & Handoff

**The first thing to read in a new session.** It says where the project stands, what happens
next and in what order, and the rules that govern how work is done here. Everything below is
current as of **2026-07-28**.

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
the `truestill` CLI and `truestill-app`, a token-authenticated local web UI. **Your photos never leave your
machine: no telemetry, and nothing about your library is ever transmitted** (`DECISIONS.md` D5,
which supersedes D1 and requires a one-time account activation for licensing - unbuilt).

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
| **Tests** | 486 Python + 16 browser end-to-end. All four CI lanes green. Assert behaviour, never counts - these numbers are context, not a gate, and **must not be pasted into a doc as a target**. Re-derive with `uv run pytest --collect-only -q`. |
| **Quality gates** | `make check` = ruff lint + ruff format-check + mypy (three `src` trees) + pytest. Plus `make e2e` (opt-in, needs a browser), `uv build --all-packages`, and CI's lockfile + `pip-audit` gates. `make check` also runs **`dash-check`** (§4, prose convention). All four CI lanes green at `c80683d`. |
| **CI** | `.github/workflows/ci.yml`, **two jobs**: `check` ({ubuntu, macos, windows} × Python 3.13, + Linux-only `pip-audit`) and `e2e` (chromium on ubuntu). |
| **Catalog schema** | **v12** (`CURRENT_SCHEMA_VERSION`). Tables: `files`, `albums`, `file_albums`, `events`, `skipped_clusters`, `drives`, `file_copies`, `settings`, `migration_journal`, `migration_runs`, `reclaim_journal`, `inplace_runs`, `inplace_moves`, `trips`, `trip_days`. Reversible migration added `migration_runs` and made `migration_journal` undoable at v11. **v12 adds `trips`/`trip_days`** - identity is the row, never a membership hash (`trip-grouping-research.md` §6) - plus the first schema-level *down*-migration in this codebase (`downgrade_v12_to_v11`, testing/rollback only, nothing wires it into a runtime path). **Next free version is v13.** (v10 went to the in-place journal, not to date provenance - see `IMPLEMENTATION_STANDARDS.md` §1). |
| **Sidecar** | `catalog.cache.sqlite` beside the catalog - the hash cache. Machine-local, disposable, path-keyed; **never** part of the custody record. Delete it and nothing is lost but time. |
| **Packages** | `truestill-core` (library, `py.typed`), `truestill-cli` (the `truestill` command), `truestill-app` (the `truestill-app` UI). uv workspace, hatchling, all building clean wheels. |
| **Repo** | `github.com/dinesh-ad/truestill` (renamed from `.../vaeon`; GitHub redirects the old name - **never create a new repo called `vaeon`**, it would kill that redirect). |
| **Not yet done** | Nothing is published. No PyPI release, no public repo, no domain, no landing page. |

### 2.0 CLOSED: the default-layout correction (year-first)

**The arc is complete.** The default destination structure moved from `{category}/{yyyy}/{mm}`
(source above timeline) to a year-first timeline at the drive root, both real drives were
migrated and verified, and the category-first path has been decommissioned. Background and
rationale: `default-layout-research.md`, `migration-routing-research.md`,
`legacy-decommission-research.md`.

| Step | |
|---|---|
| Phase 1 recon + design (`899f6f9`) · **pin** (`149e78b`) | the design gate, and the mechanism that stops a default change reshaping an existing library |
| **2a scheme core** (`ae75ecf`) · **R1/R2** (`e5d2f26`) | routing on rule, events as a second axis, messenger dates refused, year-first guards |
| **2b config** (`e3f09f1`) · **2b-san path safety** (`868e614`) · **2c Settings** (`7dea12f`) | preset registry replaced, NFC + 255-byte + collision handling, live Settings surface |
| **seam wiring** (`01fa8ec`) | the audit's F1/F3: the scheme was unreachable from production until this |
| **2d default flip** (`c0ae0c8`) | year-first becomes the default |
| **2e migration** (`6676617`) · **2e-undo** (`d15fb79`) | migration routes through the same seam; a completed migration became reversible |
| **both drives migrated** | The Memory Cabinet and Output, 2,269 files each, verified 2269/0/0 |
| **clean-empty** (`318d7d3`) · **`--permanent`** (`484a8ae`) | the leftover skeleton removed, behind two distinct confirm words |
| **2f decommission** | category-first removed entirely; both undo records retired on explicit confirm |

**Both real drives are done.** The Memory Cabinet (pCloud FUSE mount) and Output (local ext4):
**2,269 files each, migrated, verified 2269/0/0 after migration and again after cleanup.**
Output's 11 empty folders went **to the trash** (recoverable); the Cabinet's went **permanently**
via `--permanent`, because `gio` cannot trash across a filesystem boundary onto a cloud mount and
the design refuses to downgrade a recoverable removal silently. Both undo records were then
**retired on explicit confirm** - reversibility remains a feature of every future migration.

**What survives from the compat era: nothing but the pin's general job** - a library is never
silently reshaped by a default change, with no knowledge of any particular layout. `{category}`
is valid **only** inside the fixed side-bin shape, which is not user-supplied.

**Reversibility is still a feature.** Every future migration arms its own undo record; what was
retired was two specific records pointing back at a layout that no longer exists.

### 2.1 The soak test is IN PROGRESS - and it is producing findings

The user is running truestill on their **real library**. This is the launch gate (§3.1), it is
**not finished**, and it has already produced ten shipped fixes. A soak finding outranks
everything else in the queue; when one arrives, drop what you are doing.

**What the soak has found and what shipped for it (all 2026-07-27).** These ten came from using the app; the **tab tour** that followed produced a separate, still-open arc - see **§2.2**, which is where a resuming session should start.

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

**An eleventh, soak-class finding, 2026-07-29 - found while planning Stage 2d, not by direct
use, but real and outranking the plan it interrupted.** The app's `migration_preview`/
`migration_apply` (behind both the Settings migrate screen and the "Trips & events" apply-to-disk
button) never resolved `Camera`'s ambiguous label the way `truestill migrate-layout` already
does, so migrating through the app side-binned every `Camera` photo - including named events -
instead of placing it on the timeline. Root cause: the app's migrate wiring (`ad34fd6`) predates
`label_routes`/`rederive_rules` (`6676617`, added for the year-first correction two days later),
and the mechanical adaptation that kept it compiling under the new function signature never
threaded the new resolution through. Fixed same-day: `service._resolve_migration_routes` now
calls `label_routes`/`rederive_rules` exactly as the CLI does, at the same bounded cost
(`O(ambiguous files)`, zero when nothing is ambiguous). Full trace, the (a)/(b) history, and the
two-sided fixture evidence: `trip-grouping-research.md` §13.6-§13.7.

### 2.2 CURRENT ARC: the tab-tour findings - **Stage 13.1 is BUILT; 13.2 next**

**Read this section first if you are resuming.** The layout arc (§2.0) is closed; this is what
the project is actually doing now. It came out of Dinesh's **tab tour** of the migrated library
(the §3.1 soak item), which produced five items, staged and ruled one at a time.

**DONE:**

| Stage | What shipped |
|---|---|
| **Stage 0** | Find pagination (SQL-paged, `FIND_PAGE_SIZE = 50`); the misleading drive-marker error (`locate_drive` walks parents, so "not a drive" no longer means "you pointed at a subfolder"); clickable paths; the date-layering gap check - which **refused `ModifyDate`/`FileModifyDate` as a named constant** and recorded the **XMP null result** (0 of 400 real files carry an XMP date, so the tier was withdrawn, not deferred) |
| **Stage 1** | The events-clustering fix (`29d6fdc`): a **60-minute absolute boundary floor**, a **48-hour hard gap cap**, `min_duration_s` **removed**, `min_files` stays **8**. Turned 4 clusters into 15 and killed a 5.6-year "event". Its stated consequence: segmentation is now **within-day only** |
| **Stage 2a** | The `Placement` StrEnum router refactor (`1247055`) - a prerequisite, not part of trips. Pure refactor, proved byte-for-byte identical over 7 schemes x 4 sample rows |
| **Stage 2b** | `detect_trips` (`packages/truestill-core/src/truestill_core/trips.py`) - pure detection only: active-day gating, run-forming with a bridgeable gap, the year-boundary split, the max-span decline. No schema, no layout, no migration - those are 2c-2e, still pending. Five fixtures, each proven to fail against its named mutation; see `trip-grouping-research.md`'s "Built" note |
| **Stage 2c** | Trip persistence - catalog **v12**, `trips`/`trip_days` (identity is the row, never a membership hash - §6), `create_trip`/`trip_for_day`/`update_trip_days`, and the first schema-level *down*-migration in this codebase (`downgrade_v12_to_v11`). `detect_trips` (2b) is wired to **nothing** yet - the join is 2d's job. Four fixtures, each proven to fail against its named mutation |
| **`(mm)` fix** | `migrate.py` no longer asks `Placement.EVERYDAY`'s template how to spell an event folder; each event's naming now comes from its own placement, resolved via one `classify()` lookup per event in place of the fixed lookup - the router `(mm)` said it should have used all along. Proven both ways: a scheme where `EVERYDAY` and `EVENT_DAY` genuinely differ shows the old code reporting a collision that would never occur on disk, and the same two events on a shared-naming scheme (every shipped preset) still collide exactly as before. **Unblocks Stage 2d.** |
| **Stage 13.0/13.1** | The app's migrate path side-binning `Camera` found and fixed (the eleventh soak finding above). Then Stage 13.1: `truestill_core.trip_review` (`propose_trips_from_catalog` / `commit_trips`) - the `detect_trips` (2b) to persistence (2c) join, catalog-only. Name-once by day: a day `trip_for_day` already claims is refreshed via `update_trip_days`, never re-created - idempotent on a pure re-ask, an edge adjustment when the confirmed days actually differ. Three fixtures, each proven to fail against its named mutation: the re-ask identity fixture Stage 2c deferred, an edge-trim fixture (confirmed edges persisted, not the raw proposal), and a declined-run fixture (nothing persisted). No layout, no `Placement`, no `TRIP_DAY`, no UI, no file moved. |
| **Alongside** | `4c9fcf8` prose repair + user-facing copy guard, `2353efd` the docs-only gate gap and the dash gate, `188eb3b` backlog `(mm)` tracked |

**PENDING, in order:**

1. **Stage 2d - the review stage and layout wiring - IN PROGRESS.**
   `trip-grouping-research.md` §13 (2026-07-29) breaks it into sub-stages with an acceptance
   fixture and an explicit STOP point each - read there before starting any of it. **13.0**
   (verification spike) and **13.1** (the detection-to-persistence join) are built - see the
   Stage 13.0/13.1 row above. **Next: 13.2**, `Placement.TRIP_DAY` and the render seam (pure -
   no persistence wiring, no UI). Then 13.3 (review UI) and 13.4 (migration wiring, which widens
   `(mm)`'s collision-scoping boundary).
2. **Stage 2e - adoption for existing libraries** via `migrate-layout`.
3. **Stage 3 - Trips screen usability.** `min_files` becomes a **setting** (default 8), proposals
   **sorted by count descending**, small proposals **collapsed**, and a trip offered as **one**
   proposal rather than one per day.
4. **Stage 4 - backlog `(gg)`**, adaptive day folders. Sequenced last on purpose: it partitions
   on evented-vs-un-evented, so it needs the evented set to be right first.

#### The open question that blocked Stage 2b - answered

> Was the evening of 2014-08-14 (23 photos, 19:46-21:22) part of the Wayanad trip (drive up /
> arrival) or a separate evening at home?

**Dinesh confirmed: yes, the drive up.** The acceptance fixture
(`test_the_real_wayanad_run_is_one_full_proposal_no_trim`) asserts the real cluster shape and the
real day counts (31 / 635 / 737 / 654) produce exactly one proposal, Aug 14-17, untrimmed - ground
truth and the detector's output now agree. GPS that would settle this kind of edge in general is
still not persisted on this path - that remains backlog `(kk)`.

---

## 3. The road ahead, in order

Work these **in sequence**. Do not start a later item because an earlier one is slow.

### 1. Soak test - **the launch gate** 🔴 **IN PROGRESS**

The user runs Truestill on their **real library** for **2-3 weeks**. Nothing ships until this
passes. This is not a formality: it is the only test that exercises real drives, real volumes,
real interruptions and real heterogeneous metadata. Bugs found here outrank every other item
in this list. Treat a soak-test report as the highest-priority work in the queue.

**Status: running, ten findings shipped** (§2.1), the layout correction it triggered is closed
(§2.0), and the tab tour has opened a second arc that is **still in progress** (§2.2).
**What remains before "soak passed":**

- **Tab tour** - ✅ **done, and it opened the arc in §2.2.** Walking Trips, Find, Settings and
  Import on the migrated library produced five items; Stages 0, 1 and 2a have shipped and
  **Stage 2b is blocked on one question** (§2.2). The tour is finished; the work it started is
  not. Everything below is still outstanding.
- **In-place maiden voyage**, plus **one deliberate `undo-organize`**. `--in-place` and its undo
  have never run outside tests on real files. Do the undo on purpose, while nothing depends on
  the outcome - a reverse gear is only known to work when it has been pulled.
- **Buy `truestill.app`** (~EUR 13). **Not purchased.** It is the cheapest item on the whole
  pre-launch list and the only one someone else can take.
- **~2 weeks of quiet use.** Not a countdown - the point is ordinary days where nothing is being
  tested, because that is when the surprises show up. It is not closed and there is no date on
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
honest. Analytics, if any, must be the Plausible-class cookieless kind: no cookies, no
cross-site tracking, page-level aggregates only (`DECISIONS.md` D1's original measurement
description - D1's *accounts* stance is superseded by D5, but this measurement-channel detail
is not). The in-product no-telemetry promise, restated in D5, governs, and the site must not
undermine it in spirit.

### 5. Community announcement

**r/DataHoarder** and **r/selfhosted**, led with the **Takeout-rescue angle** - "your Google
Photos export lost its dates; here is how to get them back" is the story that lands with that
audience. Read each subreddit's self-promotion rules first. Expect and welcome scrutiny of the
privacy claims; they hold up, so answer plainly.

### 6. Post-launch

**Queue order, when the soak closes:**

1. **A soak-driven backlog pick** - whatever the remaining checklist surfaces outranks anything
   already written down, and the sequencing note in `BACKLOG.md` §Ideas maps the cheap
   combined orders if the pick lands on `(n)`/`(gg)`/`(hh)`/`(ii)`.
2. **The licensing-server spec** (`DECISIONS.md` D5 §5) - new infrastructure, its own research
   and design pass, and the offline-activation fallback story is the part most likely to be
   regretted if it waits.
3. **The monetization build** (`DECISIONS.md` D6) - signed keys and the visible-never-gating
   asks. It depends on the server, so it follows it.


**First: BACKLOG item (n)** - the "how your dates were determined" honesty stat: surface the
provenance mix of capture dates ("82% embedded EXIF, 11% filename, 5% Takeout, 2% Undated").
The concrete first slice is making the organize result's "**N no date → Undated**" line
**explorable** rather than a bare count - validated as a real confusion in the UI walkthrough.
Persisting `date_source` is the enabling schema work.

**Then: monetization**, per `DECISIONS.md` D5/D6 - **not** the earlier one-time-Pro-licence
sketch D6 supersedes. A **perpetual licence**: pay once, keep that version forever, with
**one year of updates included** and **renewal at ~40-50% of full price** for another year
(pricing itself deliberately TBD post-launch). Keys are **Ed25519-signed** with the buyer's
name and email embedded - a share-deterrent by identity, never a lockout. **Accounts are
required**, created at a **one-time activation** against a self-hosted licensing server (D5,
which supersedes D1's no-accounts stance); the app then runs fully offline, with **no
per-launch phone-home** and **photo data never transmitted**, at activation or ever after.
Pro-tier candidates already sit behind a clean capability seam. Get formal trademark
clearance before charging money.

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
- **Hyphens, not em-dashes, in repo prose and source.** The replacement preserves spacing
  (`" - "`, never `word-<space>word`), and **user-facing surfaces are excluded** (`static/`,
  `templates/`, `CHANGELOG`, `README`, `SECURITY`) - UI typography is a choice, not a sweep
  target. Use `scripts/normalize_dashes.py`, never a hand-rolled `sed`. `dash-check` enforces it
  in `make check` and pre-commit. The convention, and why there is no in-repo mechanism to hunt
  for, is `IMPLEMENTATION_STANDARDS.md` §6.1.
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
| Why is the product this way? (accounts + licensing, no telemetry, Pro model) | `DECISIONS.md` |
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
| Do we resolve dates the way other organizers do, and what are we missing? | `date-layering-gap-check.md` |
| Why does Trips propose the clusters it does? | `events-clustering-research.md` |
| Why is the year the top-level folder, and how was the default changed? | `default-layout-research.md` |
| How does a migration decide where a file goes, when the catalog stores a label? | `migration-routing-research.md` |
| Why is a WhatsApp filename date refused when a screenshot's is trusted? | `messenger-dates-research.md` |
| What makes a user-typed name safe as a folder (NFC, 255 bytes, collisions)? | `filename-safety-research.md` |
| What may `clean-empty` delete, and what does it refuse? | `empty-folder-cleanup-research.md` |
| Why was the category-first layout removed rather than kept for compatibility? | `legacy-decommission-research.md` |
| How do multi-day trips get grouped and named, and why is a day never split? | `trip-grouping-research.md` |

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
- **A checker that is not pointed at a file will not tell you the file is broken.**
  `scripts/benchmark_hashing.py` sat outside the type fence and imported `truestill.scan`, a
  module that never existed under that name - through two renames, silently. Closed on
  2026-07-27: `scripts/` is now type-checked alongside the three `src` trees, and the
  pre-commit hook no longer inherits `--ignore-missing-imports`, which was answering "fine"
  for exactly that import. See `IMPLEMENTATION_STANDARDS.md` §6.
- **When you widen a fence, expect it to catch something immediately.** Dropping that one flag
  also revealed that `uvicorn` had been missing from the hook's `additional_dependencies` -
  hidden by the same flag. Both were found the moment the gap was closed, not by review.
- **Measure before optimizing, and record the number.** The performance audit convicted only
  what evidence convicted, and `PERFORMANCE.md` §4 lists the things that *look* like waste and
  must be left alone. Read it before "improving" the pipeline; the size pre-filter in
  particular is the single best optimisation in the codebase and reads like dead weight.
