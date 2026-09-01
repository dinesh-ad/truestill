# Truestill - Project Status & Handoff

Start here in a new session. This file is the **cold-start map**: current state, what is next,
and what blocks it. It is intentionally short; deep rationale and history live elsewhere.

---

## 0. Fresh clone to green (15 minutes)

```sh
# 1) External dependency used by metadata paths
sudo apt install -y libimage-exiftool-perl        # macOS: brew install exiftool
exiftool -ver

# 2) Workspace setup
uv sync --all-packages --group dev

# 3) Hooks (both types)
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
uv run pre-commit install --hook-type pre-push        # refuses a push onto a red run

# 4) Prove commit-msg guard blocks forbidden trailers
git commit --allow-empty -m "test
Co-Authored-By: someone <x@y.z>"                   # MUST be refused

# 5) Confirm author identity
git config user.name && git config user.email      # expect: dinesh-ad

# 6) Gates
make check                                          # no browser, no Node needed
make e2e-install && make frontend-install           # browsers + npm ci, once
make e2e                                            # optional local lane
```

Notes:
- `make check` is the required green gate, and it needs **neither a browser nor Node**.
- Browser E2E is deliberate and separate (`make e2e`).
- **The React bundle is a build artifact and is not committed.** `make e2e` builds it first, so
  the lane cannot run against stale JavaScript; `test_the_served_bundle_was_built_from_these
  _sources` hashes the frontend sources and compares against the digest compiled into the served
  bundle. A content hash rather than an mtime, for §4's forty-ninth member's reason. The added
  setup is one `npm ci` on a warm cache - **§0 is a promise about time, and it holds.**

---

## 1. Current operating picture

- **Core product shape is shipped:** organize, ingest, dedup, drive identity, verify, backup,
  configurable layout + migration, reclaim, in-place organize + undo, local web UI.
- **Date-provenance program: COMPLETE (2026-07-31), six steps.** A user can now see **why** each
  date was chosen, **correct** one that is wrong, have that correction **survive every whole-disk
  operation**, and optionally **write it into the organized copies** so other apps read it too.
  Schema v13-v16. One clause of `(bbb)` item 4 was carried out rather than ticked - see `(aaj)`;
  `(kk)`'s `GPSDateStamp` half was in scope and was **not** built.
- ⚠ **THE FIRST SOAK RAN ON 2026-08-20 AND THE LINE ABOVE THIS ONE IS WHAT IT OVERTURNED.** Seven
  steps against **4,111 real photos and videos**, 11 GB, with the corpus counted independently
  before the product was allowed an opinion. **It produced SIX entries** - `(aei)`, `(aej)`,
  `(aek)`, `(aem)`, `(ael)`, `(aep)` - and **five are shipped**; `(ael)` alone is open.
  ⚠ **This said *"five entries … four are shipped"* until 2026-08-27**, and the missing one is
  `(aep)`, split out of `(aek)` on 2026-08-21 as its third finding.
  [`soak-one-record.md`](soak-one-record.md) has listed six since it was written; this bullet
  predates the split and never absorbed it. `(aep)` has since shipped.
  - ⚠ **CORRECTION, 2026-08-21: THOSE 4,111 FILES INCLUDED `Input/Testing-new`, WHICH
    `IMPLEMENTATION_STANDARDS.md` §5 EXCLUDES.** Measured that day: `Input/2013` + `Input/2014` is
    **2,276 files / 6.3 GB**, `Testing-new` is **1,836 / 5.0 GB**, and `Input` entire is
    **4,112 / 11 GB**. Only the last matches the recorded figure. **The counts above are not wrong
    - 4,111 files really were analysed** - what was wrong is the implication that the fence held,
    and the phrase *"counted independently"* is what invites that reading. §5 was checked rather
    than assumed and is **correct**, so this is soak one's scope and not a stale rule; the method
    and evidence are in [`soak-two-plan.md`](soak-two-plan.md) §1.
  - **It cost nothing, and that is why it went unnoticed.** Soak one was copy-mode throughout:
    nothing moved, nothing was deleted, so including an unbacked folder had no consequence. It
    stops being free the moment a soak relocates or deletes sources, which is why the fence is a
    ruling for soak two rather than a footnote.
  - **`(aei)` is the headline and nothing else would have found it**: `organize` into a fresh
    second destination copied **nothing**, registered a **0-file** drive and reported success,
    while `status` warned in the same breath that 4,088 files sat on only one drive. It deduped
    against the **catalog** instead of the **destination**.
  - **`(aej)`**: `LAST VERIFIED: never` sixteen seconds after a verify that found 7 missing files.
  - **`(aem)`**: a `kill -9` at 340 of 4,105 files left a library that read as complete.
  - **`(aek)`**: a full disk crashed drive setup with a `pathlib` traceback. ✅ **Shipped
    2026-08-21** - the fix was the **ordering** (register after the space check, using a
    sentence that already existed), plus hardening the write anyway, because ordering cannot
    cover a read-only drive or one that fills between the check and the write. ⚠ It also
    turned up a second defect that would have made the ordering inert: a genuinely full disk
    reports **0 free**, and `0` was `preflight_destination`'s *"could not measure"* value, so
    a full drive passed its own space check.
  - ✅ **What the soak also proved sound:** the `.partial` -> rename -> record write path survived
    both a `SIGKILL` and a full disk with no corrupt file and no phantom row, and `(adx)` gap 1's
    clone disclosure fired correctly on an 11 GB clone.
- ⚠ **FIVE MORE SOAKS RAN, AND THE BULLET ABOVE WAS THE ONLY ONE HERE UNTIL 2026-08-22.** Soak
  one is above because it overturned a claim in this file; the rest are here because a
  *"where does the project stand"* document that knows about one of six soaks is stale in the
  direction that costs most. Each has a **record**, and soaks two to four also have a **plan**;
  all are mapped in `CLAUDE.md`.
  ⚠ **THIS BULLET ENUMERATED FOUR SOAKS UNTIL 2026-08-27, AND SIX HAD RUN.** Soak five and soak
  six both ran 2026-08-25 ([`soak-five-record.md`](soak-five-record.md),
  [`soak-six-record.md`](soak-six-record.md)) and neither had a line here - which is this bullet's
  own failure, one iteration on, in the paragraph written to name it. **Soak five** covered the
  whole library and every feature: zero resolver decisions changed across 10,745 files, `Input/`
  byte-identical after every run. **Soak six** covered the reversal paths and a rebuild drill, and
  **falsified the founding *"categories are recomputable"***.
  ⚠ **Soak one's record is a RECONSTRUCTION** ([`soak-one-record.md`](soak-one-record.md), written
  2026-08-22): none was kept on the day, so two of its seven steps are unrecoverable. The bullets
  above were its only account for three weeks, which is why its two findings sat open longest.
  ⚠ **This clause read *"its two open findings are the only soak findings still open"* until
  2026-08-27.** `(aep)` has since shipped and soak six raised three more, so the open set is
  `(ael)`, `(ahs)`, `(aht)`, `(ahv)` - see the correction above. The argument the clause was
  making survives; only its arithmetic was time-bound.
  - **Soak two** (2026-08-21, `soak-two-record.md`) - scale and sequence on 2,276 files / 6.3 GB.
    **Five findings**, and ⚠ **three harness defects that each nearly became a false one**. Its
    stock-take is what set the next two soaks' subjects.
  - **Soak three** (2026-08-21, `soak-three-record.md`) - **refusal**: every step makes the
    filesystem say no, staged with real `chmod` and unprivileged FUSE mounts so the **kernel**
    returns a real errno to an unmodified product. Six steps, **four findings under three
    letters** - `(afc)`, `(afd)`, `(afe)`, two of them folded into `(afd)` because they shared its
    remedy - and **the two most dangerous properties held**: no automatic path keys off
    a *"gone"* verdict, and a destination that refuses mid-run corrupts nothing. **What failed was
    what the product SAYS.**
  - **Soak four** (2026-08-22, `soak-four-record.md`) - the **deleting** commands, `reclaim` and
    `clean-empty`, which nothing had soaked. Seven steps, **four findings** - `(afh)`, `(afi)`,
    `(afj)`, `(afk)` - plus `(afd)` confirmed independently in a second command. ⚠ **The two
    properties most likely to destroy irreplaceable data both held**: `reclaim` deleted exactly
    the set it promised and nothing where the source *was* the only copy.
  - ⚠ **The soaks have outproduced the backlog, and every entry these three raised is closed.**
    **Twelve**, counted rather than recalled: `(aer)`-`(aev)` from soak two, `(afc)`-`(afe)` from
    three, `(afh)`-`(afk)` from four - all in `SHIPPED.md` as of 2026-08-22. Four more were **split
    out while fixing them** and are also shipped: `(afl)`, `(afm)`, `(afn)`, `(afo)`.
    ⚠ **FOUR soak findings are still open**, so *"the soaks are all closed"* is false and this
    bullet is the correction to it. Derived from `BACKLOG.md`'s open section rather than recalled:
    `(ael)` from soak one, and `(ahs)`, `(aht)`, `(ahv)` from soak six.
    ⚠ **This read *"soak ONE's `(ael)` is the one soak finding still open"* until 2026-08-27, and
    it was wrong in both directions.** It was wrong when written - `soak-one-record.md` says
    *"two of soak one's six findings are still open"*, `(ael)` **and `(aep)`** - and it is right
    about `(ael)` today only by accident, because `(aep)` shipped while soak six raised three more.
    A count nobody derives is a count that is correct twice a day. **The pattern is not "the product
    is broken"**: across four soaks the safety invariants held every time they were tested, and
    nearly every finding was in what the product **reports** - a run that could not say what it
    did, a folder described as full when it could not be opened, an identity minted on evidence
    nobody could gather.
  - ⚠ **Yield is falling and the method is what to watch.** Soak four's harness produced **three**
    defects of its own, two of which would have produced false results, and a fourth soak needed a
    positive control before its cleanest pass could be believed. **Steps that cannot be staged
    honestly are said rather than skipped** - the records name what each soak did *not* test.
- **Two Truestill processes can no longer overwrite each other's photos** (2026-08-22, `(aaw)`).
  A kernel-enforced per-drive lock covers every mutating operation on both surfaces; a second run
  refuses and names the holder. ⚠ **Measured rather than reasoned, and the measurement is the
  argument**: two concurrent applies lost **99** and **45** organized copies, proven by content;
  0 after. ⚠ **Unique staging shipped first and made it WORSE** - it fixed the mechanism (two runs
  writing one `.partial`) and removed the only loud signal, leaving both runs exiting 0 with a
  catalog row silently wrong. A fix that improves the mechanism and quietens the harm is the trade
  this project refuses. `(afp)` closed with it: a cold start no longer offers to delete a catalog
  another process is writing.
  ⚠ **Not covered, on purpose**: the app's synchronous settings writes, which is `(adt)`.
- 🔑 **THE RECOVERY STORY, in plain English - the product's central claim, and it changed three
  times in the week to 2026-08-29.** A user loses their catalog and re-organizes to rebuild it.
  **Back**: every photograph, its category and date, every trip, **every event name with its
  photographs under it** (`(ahv)`, shipped 2026-08-29 - before that day every event name was
  lost), every date correction, and the settings. **Not back automatically**: a trip's NAME where the rebuilt
  catalog already minted a different one for those days - the restore reports the clash and skips
  it (`decisions.py`'s `conflicting` list), because a partial claim is not a partial restore; and
  an event whose photographs no longer form the same group, which is reported by name and never
  guessed at.
  ⚠ **THE REMEDY NOW EXISTS, AND THIS SENTENCE SAID IT DID NOT UNTIL 2026-08-30.** It read
  *"`rename_trip` does not exist, so the user is told loudly instead"*, which was true when
  written and stopped being true in stages: `(aix)` shipped renaming on the CLI (P159/P160) and in
  the app (P162). So the residual is now **"told, with something to do about it"** rather than
  "told, and stuck": rename the trip and the drive's document takes the new name, because
  `(aix)` stage 2b records a per-key lease that lets a deliberate rename through the guard
  `(ahz)` step 3 put there. **The restore still does not resolve the clash itself** - it reports
  it - and closing that is not `(aix)`'s scope.
  Proven end to end on the real corpus, not argued: `soak-six-record.md` falsified the founding
  *"categories are recomputable"*, and this is where that arc now stands.
- ⚠ **"The library" names two different things, so cite the subject, not the phrase**
  (2026-08-29): the soak records' **20,237 files** is `/data/TruestillLibrary/Input` alone and
  is still exact - those records are right and must not be touched - while the full tree is
  **~105,125 files** once soak outputs and working copies are in, and P121's hot-path benchmark
  measured **84,167 media files across the full tree**. Derive, don't quote:
  `find /data/TruestillLibrary/Input -type f | wc -l` versus the same over the root.
- **Schema is at v22** (`catalog.CURRENT_SCHEMA_VERSION`); `organize_runs` arrived at v20 (`(aem)`), the in-place intent columns at v21 (`(agk)`), and `file_copies.bake_started_at` at v22 so an interrupted bake is not read as damage. ⚠ **This line said v21 until 2026-08-26** and was noticed twice without being fixed - a third notice with no fix is the half-refresh `ENGINEERING_STANDARD.md` §4's seventy-first member is about. Read `CURRENT_SCHEMA_VERSION` rather than this sentence.
- **`(aad)` installers remain the launch gate**, and its two largest items are now built AND
  proven: the release lane and the Windows installer both work on both platforms
  (run 32555392424, 2026-08-22). What is left of it is the **download page** and the
  never-fired **publish** job - see §2b.
- **Python 3.14 since 2026-08-22** (`DECISIONS.md` **D13**, reversing D10). `requires-python` is
  `>=3.14`, the check lane runs one interpreter again, and the release lane builds on it.
- **Trademark residual (live pre-monetization obligation):** TruStile Doors remains a low-risk
  residual in different IC classes; attorney clearance is still required before monetization
  (full analysis in `DECISIONS.md`).
- **Recent critical portability/safety posture:** loud failures are in place (stale hints,
  catalog-open visibility, reclaim/undo stale-path messaging); remaining work is portability
  follow-through, not silent safety failures.
- ⚠ **The run record changed shape on 2026-08-23, and it is a CONTRACT change** (`(afw)`,
  `IMPLEMENTATION_STANDARDS.md` §1). One rolling `last-run.json` per catalog became
  `last-run.json` **plus** an append-only `runs/index.jsonl` kept forever and bounded per-file
  detail beside it - because an undo record written to the old path **destroyed the organize
  record of the run it had just reversed**. Undo is now the fourth surface that writes one;
  migrate and bake are deliberately undecided (`(agm)`).
- **Catalog schema REACHED v21 on 2026-08-23** (`(agk)`); it is v22 today, see above. The in-place journal is an **intent log**:
  the row is written *before* the rename, not after, so a crash in that window leaves a file that
  undo can still put back. Measured before the fix: 2 of 8 `SIGKILL`s left a photograph moved
  with no undo row, and `undo-organize` reported success. Undo now verifies **identity** before
  restoring, not just position.
- **The docs source-of-truth split is strict:**
  - binding contract: `IMPLEMENTATION_STANDARDS.md`
  - settled stances + why: `DECISIONS.md`
  - open work + build constraints: `BACKLOG.md`

What this file no longer does: carry stage-by-stage implementation history, old commit-by-commit
narrative, or volatile counts.

---

## 1b. The build order - engine, then contract, then UI

⚠ **Written down 2026-08-25 because it never had been.** The maintainer has worked to this since
the first handoff and it has been re-argued at least three times, twice in two days by an agent
that could not find it. Checked before writing: no phased-plan text existed in `PROJECT_STATUS.md`,
`IMPLEMENTATION_STANDARDS.md`, `ENGINEERING_STANDARD.md` or `CLAUDE.md`.

**It is a plan, not law.** `IMPLEMENTATION_STANDARDS.md` is binding rules about code *behaviour*;
an order of work is neither binding nor about behaviour, and filing it there would make it read as
enforceable when nothing enforces it - `(agc)`'s shape. Nothing enforces what follows except this
page.

1. **The engine finishes first.** The CLI and `truestill-core` carry every behaviour. The app is a
   panel over them and never the only home of anything.
2. **The payload shapes are then declared STABLE and pinned by contract tests.**
3. **Only then is the UI built** - React, replacing `app.js` entirely (`(adi)`).

### The rule that makes step 3 safe

🔑 **A surface consumes only what the contract declares, and assumes nothing that is not in it.**
This is the whole point of the order, and it is what `app.js` failed. Live evidence, not argument:

| computed by a service | read by the surface |
|---|---|
| `BakeSummary.absent` (`service/bake.py:166`, emitted `:217`) | **0** in `bakeCompletion` (`app.js:4194`). ⚠ Its sibling `BakePreview.absent` (`:238`) **is** read, at `app.js:4158` |
| `DriveAttachment.unmatched` (`service/drives.py:132`) | **0**, and correctly so since `(abm)` shipped: the fact is named by `truestill rescan`, not counted twice |
| `DriveAttachment.unreadable_dirs` (`service/drives.py:137`) | ✅ **surfaced by `(abm)`** 2026-08-25. It was the worst of the four: a file under such a folder gets no copy row, so both surfaces said the backup was complete |
| `migrate.py`'s `stopped` and `refused` | **0** until `(ahc)` closed it 2026-08-25 - a stopped run read as *"Moved N files."* |

⚠ **THE TWO `absent` ROWS ABOVE USED TO BE ONE, AND IT WAS COUNTED THREE DIFFERENT WAYS.** This
table said *"3 sites"*, the status table below said *"2 sites"*, and `service/bake.py` has **4**
occurrences across **two** TypedDicts **one of which is read**. Neither number was right and a site
count was the wrong unit: the question is which PAYLOAD KEY no consumer reads, not how many times
a name appears. Resolved 2026-08-25 by `(ahl)` in favour of naming the field and its payload -
counted from source, both ends cited.

**Rewriting the UI against a contract nobody has declared reproduces every one of these in a new
language.** `test_surface_parity.py` already exists and does not cover this: its own docstring
says it *"protects the REPAIR, not the contract."*

### STABLE, and what it does not mean

The field-standard lifecycle is **DRAFT -> BETA -> STABLE -> DEPRECATED**; step 2 heads for
STABLE. ⚠ **"Freeze" is the wrong word and would mislead a later reader.** STABLE constrains the
**shape** of what a route returns - its keys, their types, whether a field may vanish. It says
nothing about quality. **A bug behind a stable contract is still a bug and still gets fixed**;
what stops is changing *what a route returns* under a consumer that already reads it.

### Step 1's exit condition, so it can be checked rather than felt

*"The engine is finished"* is not testable. These four are, and each names its own subject:

1. **Every mutating run leaves a line in the run history, and as much per-file detail as the run
   actually holds.** ⚠ **This read *"writes a record"* until 2026-08-25 and could never have been
   ticked as worded.** `(agm)` ruled that bake correctly writes an index line and **no detail** -
   it counts files and names only drives, so its `files` would be `[]` at any size, while
   `file_copies.date_baked_at` holds which copies it wrote permanently. A condition that a correct
   run fails is a condition that gets quietly ignored, so the wording follows the ruling rather
   than the other way round. ⚠ **SEVEN** of the nine meet it since 2026-08-29, when `(ahi)`'s undo half shipped; `clean empty`,
   `archive unpack` and **`undo`** remain (`(ahi)`). ⚠ **THE ABSENT THREE READ *"trip apply, clean empty, archive unpack"* UNTIL 2026-08-27 AND `trip apply` WAS NEVER ONE OF THEM.** Derived from `server.py` by AST rather than recalled: `trip apply` calls `service.migration_apply`, which records - the maintainer established this on 2026-08-26 by reading the ROUTE's call graph rather than the module sharing its name. The operation that actually writes nothing is **migrate's `undo`**: `migration_undo` READS the reversible run's id (`service/migrate.py:395`) and writes no record of its own. Absent from a run history, an undo is the one operation whose absence makes the history lie about the state of the disk. Pinned by `test_the_app_records_what_a_run_did.py`, which
   lists each surface *with its reason*.
2. **Every surface reports its own stop.** `(ahc)` closed migrate's last one.
3. **No route computes a field no consumer reads.** ⚠ **BLOCKED ON `(ahn)`, not on any count.**
   ⚠ **The table above is EVIDENCE, not the list.** Derived from the AST by `(ahl)`, and ⚠ **the
   inventory figures are DERIVED, never quoted - they rotted once already.** A 2026-08-25 snapshot
   read *"117 TypedDicts, 579 key slots, 289 distinct key names"* and by 2026-08-29 the tree was at
   roughly **123 / 594 / 293**, while the prose still presented the old numbers as current. The
   guards use `>=` floors with slack so only the prose was wrong, which is exactly why a number
   here is worse than a command. Run the census rather than trusting a figure -
   `test_no_thirty_fifth_dead_payload_key.py` holds the derivation and its `MEASURED_*` constants.
   **The one figure worth carrying is `34` dead keys**, and it is a FLOOR rather than a count - ⚠ **34 is a FLOOR rather than a count**, because a key-name
   because a key-name census cannot see a collided field: `absent` is read in one payload and dead in
   another, so it never enters the 34.
4. ⚠ **No mutating behaviour lives only in the app** - added here because step 1's own sentence
   requires it and nothing was checking. ⚠ **This said *"Bake fails it today"* until 2026-08-25
   and named only bake.** Checking it found **three**: bake, backup and trip apply. `(ahd)` gave
   bake a CLI, `(ahf)` gave backup one, and trip apply turned out to be **two operations** - the
   placement already had a CLI, and the naming is app-only **by recorded decision** (*App-surface
   deferrals*). **The condition is met.**

### Where the engine actually stands, so it is one place rather than four letters

| | condition | status |
|---|---|---|
| 1 | every mutating run leaves a line in the run history | ❌ **7 of 9** since 2026-08-29 - `clean empty` and `archive unpack` remain, which is `(ahi)`; ⚠ this read **6 of 9** until migrate's `undo` gained its record, and the guard that should have watched it could not see inside a module; see §1b's note on why `trip apply` was named here wrongly until 2026-08-27. ⚠ Reworded 2026-08-25: *"writes a record"* could not be met by bake, which correctly writes a line and no detail |
| 2 | every surface reports its own stop | ✅ `(ahc)` closed migrate's last one; ⚠ **it was ticked here while FALSE for one of them, until `(ajd)` on 2026-08-31** - `backup`'s CLI caught only `ValueError`, so a drive that vanished mid-copy reached the user as a **Python traceback**, twice, measured. The app was fine (`jobs.py` wraps any exception into an error event), which is exactly why a tick taken per-defect rather than per-surface missed it. 🔑 **The condition is met and STILL UNGUARDED**, and this is the second time that has cost something |
| 3 | no route computes a field no consumer reads | ❌ **BLOCKED ON AN UNTYPED CONSUMER**, and that is a different blocker from *"nothing declares the join"* - `(ahn)` stages 1, 2 and 4a built it, and **4a left no route payload untyped**: the seven dict literals are gone and the guard's ceiling is zero. The CONSUMED end is still a text search over `app.js`, so **no number here is a ceiling** - both methods err toward calling a dead field live. ⚠ **Stage 4b STOPPED at its own gate** (re-derived count 25, not 3) and is where the next turn starts. **Ticks at stage 5**, when a read is a type reference |
| 4 | no mutating behaviour lives only in the app | ✅ **met AND GUARDED** since `(ahj)` - every mutating operation names a CLI subcommand the parser defines, or a recorded deferral |

⚠ **TWO of the four are checked by a guard, and each pins a DECLARATION rather than behaviour.**

* **Condition 4** is guarded outright by `(ahj)` - both ends read from source, the operations from
  `server.py`'s AST and the subcommands from `cli.py`'s. ⚠ It proves a route **names** a
  subcommand that exists, **not** that the subcommand does the same work; a route naming `verify`
  while copying files would pass. And the one genuinely deferred capability - naming a trip - is
  **invisible to it**, because that route declares no operation at all.
* **Condition 1** has `test_the_app_records_what_a_run_did.py`, covering **5 of 9** operations
  (`(ahi)`) while **7 of 9** meet the condition since 2026-08-29 - `trip apply` records and has no row - and what
  it proves is **wiring**: that the code contains a call to a record entry point, not that a
  record is written on every run.
  🔑 **AND ITS TABLE IS KEYED DIFFERENTLY FROM THE CODE IT GUARDS, WHICH IS WHY THE ARITHMETIC
  NEVER LINED UP.** Two of its five rows are the same operation under another name: `bake` is
  `operation="set dates"` (`server.py:683`, added by the bake-as-a-job commit) and
  `organize_undo` is `operation="undo organize"`. A guard whose keys are not the strings the
  routes declare cannot be checked against them by anything, and nothing does. `(agj)` is the defect it would not catch.
  ⚠ **All five of its rows now read `True`**, so the table no longer demonstrates its own
  negative; the floor was moved onto the DETECTOR, which must answer `False` for the three
  services that still write nothing. A table that legitimately goes uniform must not cost a guard
  its teeth.
* **Condition 2 is met and unguarded**, checked rather than assumed: there are per-surface tests
  and two censuses over `MigrationStopKind`'s wording, and **nothing enumerates the surfaces** and
  asserts each reports its stop. Nothing proposes one.
* **Condition 3 was a hand census and is now derived** (`(ahl)`), but only **one end** of it is
  mechanical. The DECLARED end is an AST pass, and it must be AST: `test_migrate_reports_its_stop.py:149`
  records that asserting on `__required_keys__` was **vacuous** under
  `from __future__ import annotations`. The CONSUMED end is a text search over JavaScript -
  stripping comments is worth five keys, measured - so what is buildable is a **declaration**
  that goes red on a 35th field, not a liveness proof. ⚠ **No ecosystem proves field liveness
  statically**; GraphQL answers it at runtime (Apollo GraphOS Insights, Hive's
  `deprecatedSchema(period:)`) and REST has no equivalent. The mechanical-at-both-ends route is
  `(ahn)`, and it is what retires `(ahl)` when `app.js` is deleted.
* ⚠ **CONDITION 3 CANNOT BE TICKED BY EMPTYING THE 34, and that is why it is BLOCKED rather than
  counted.** ⚠ **The BLOCKER WAS RENAMED on 2026-08-25**, and the rename is the useful part: it was
  *"nothing declares the route-to-payload join"*, and `(ahn)` stages 1-3 built that join. It is now
  **the consumer is untyped**. `BakeSummary.absent` is no longer hidden - stage 3 names it dead
  alongside `drive_label` and `elapsed_seconds` - but only where the JavaScript binding is
  unambiguous: **7 of 16** job blocks, and the route channel not at all, because it over-collects
  (69 scoped reads against 25 declared keys). The method is blind in **two different ways**, and
  closing one does not touch the other:
  * **`BakeSummary.absent`** - a **name collision**. `BakePreview.absent` is rendered at
    `app.js:4158`, so the NAME reads as live and the dead sibling never enters the census.
  * **`DriveAttachment`'s five** (`absent`, `unreadable`, `unmatched`, `unreadable_dirs`,
    `blocked_by`) - **not a TypedDict at all**. It is a frozen dataclass that no route serialises,
    so a payload census cannot see it from either end. `(abm)` reached two of the five by hand.

  Both need **payload granularity** - which JavaScript variable holds which route's response - and
  that is `(ahn)`'s route-to-payload join, measured absent: **50 routes, and not one names a
  payload type**. ⚠ **This said *"all 50 handlers annotated `-> JSONResponse`"* until 2026-08-29;
  it is **46 of 50**, the other four returning HTML, SSE or bytes. The claim the number supports -
  that nothing declares which payload a route returns - is unaffected, which is why the wording
  now carries the claim rather than the arithmetic.** Until it exists the honest answer is a floor, so the condition names its
  blocker rather than a number that cannot reach zero.

The app **lacking** a route for a CLI subcommand is a different question and belongs to step 3 -
[`cli-app-parity.md`](cli-app-parity.md) owns it.

### Not in scope, so this does not read wider than it is

CLI **human wording**; internal function and dataclass shapes; **schema versions** (`catalog.py`'s
migrations are governed by `IMPLEMENTATION_STANDARDS.md`); and anything with **no consumer outside
the process**. The contract is about what crosses a process boundary to a reader that cannot be
changed in the same commit.

---

## 2. What is next (in order)

1. ⚠ **SUPERSEDED 2026-08-20: THE SOAK RAN.** The deferral below was ruled on 2026-08-12 and
   held for eight days; the text is kept because its reasoning was sound and is what a reader
   needs to understand the order things happened in. **What it predicted is now measured** - see
   §1. The paragraph beginning *"is still real and still unfound"* is the one line the soak
   answered, five times over.

   **Soak is DEFERRED, deliberately - ruled by the maintainer 2026-08-12. It is no longer the
   gate in front of everything else.**
   - **The reason, in his words:** he will not organize the 33,000-photo library until the product
     is good enough that a mistake is not 33,000 files to unpick. Soaking earlier does not buy
     confidence, it buys a large and expensive way to discover a defect.
   - **This is a change of order, not of belief.** The class soak exists to find - what only
     appears when a real library meets an operation nobody modelled - is still real and still
     unfound. What changed is when it is worth paying for.
     ⚠ **ANSWERED 2026-08-20.** It was real, and one run of seven steps found five instances. The
     sentence stands as written because the prediction was correct; only its tense is out of
     date.
   - **Read every "behind the soak gate" sentence elsewhere against this line.** They were written
     while soak was the gate. `BACKLOG.md` `(aad)` is the one that mattered most and now carries
     its own note.
   - Any soak finding that does arrive from ordinary use still outranks queued feature work.
   - ⚠ **The paragraph below was written to argue against deferring, and it is kept.** It says the
     remedy for a week of code-reading findings is not more auditing - which was true, and is why
     the deferral is a ruling about *cost and blast radius* rather than a disagreement with it.
   - ⚠ **A FACT ABOUT METHOD, recorded 2026-08-11 because it is measurable and easy to miss: in
     the week to 2026-08-11, NINE items were closed or retired - and a tenth, `(abg)`, advanced a
     stage - and NOT ONE came from real use.**
     *(Counted from the `Closes`/`Retires` trailers. The paragraph said eight when it was written
     and was overtaken the same day by `(acj)` and `(abg)` Stage 2, both found by reading code.
     The number moving while the paragraph explains why it should not is the finding, not an edit
     to it.)* Every one
     was found by reading code, measuring, or auditing documents - a pixel cap used as a claim, a
     preview tally, a custody sentence, a lost click, private paths in a public repo. **A week of
     code-reading finds the class code-reading finds**: two written things that disagree.
     ⚠ **AND ON 2026-08-20 THE OTHER METHOD RAN AND PRODUCED THE OTHER CLASS.** `(aei)` is the
     proof this paragraph was waiting for: organize copying **nothing** onto a second drive while
     reporting success was reachable in one command, sat in the code for as long as the feature
     existed, and **no amount of reading found it** - four surfaces agreed with each other and
     three of them were right. Kept undated in the text above so the contrast is legible.
     The soak exists for the other class - what only appears when a real library meets an
     operation nobody modelled - and that class produced nothing this week, because nobody used
     the product. **The list got shorter and the gate did not move.** This is not a criticism of
     the work, which was real; it is the reason **the remedy is not more auditing**.
   - Collapsible sidebar (`SHIPPED.md` `(fff)`) and adaptive day-folder threshold (`(gg)`)
     are built; pull next from backlog priority.
   - **`(gg)` soak note (2026-07-30):** correct but rare on real data - one un-evented hit
     (`2013-09-30`, 62 photos). The 2,057-photo 2014-08 Everyday folder that prompted `(gg)`
     was the Wayanad trip claim, not threshold behaviour (see `SHIPPED.md` `(gg)`).

2. **Repo-public audit + newcomer README**
   - Ensure no sensitive/local-only leakage and that user-facing docs/screenshots are current.

3. **Publish pipeline** ⚠ *(was "when soak closes" - the first soak ran 2026-08-20; the gate is
   now `(aad)` installers, not the soak)*
   - **REQUIRED STEP: make the repository private.** It is public today for the Actions minutes
     and goes private at launch. Git history carries the maintainer's cloud-storage and
     private-folder strings and a rewrite was declined on cost - `BACKLOG.md` `(acv)` holds the
     exposure, the reasoning and the residual. **This is the mitigation**, so launching without it
     leaves the accepted risk unmitigated rather than merely untidy.
     - **It changes what CI costs.** Measured over three runs **while the e2e job still ran**:
       **23, 27 and 42 wall-minutes** per push across four jobs, Windows alone 14-31 of them.
       ⚠ **SINCE 2026-08-20 A PUSH IS THREE JOBS** - the browser lane does not run on push - and
       one measured at **3m26s** wall. **Re-measure before pricing the private-repo switch on the
       figures above.** ⚠ *This clause read "e2e is disabled" until 2026-08-24, contradicting §4
       of this same document, which has said since 2026-08-22 that the lane runs nightly. The
       schedule is `IMPLEMENTATION_STANDARDS.md` §6.1's to state; what belongs here is only the
       COST, which is what this paragraph is about.* Private repositories bill Windows and
       macOS at a multiplier on the included quota - **verify the current rates before switching**
       and decide then whether the matrix stays as it is.
     - **It changes how a vulnerability is reported** (`SECURITY.md` points at this repository).
       Confirm the route still works for someone outside the org.
   - ~~Package release sequence and launch steps are still pending and should be run only after
     soak is explicitly accepted.~~ **Soak is deferred (§2 item 1), so it is no longer what these
     wait behind.** They are still pending; what has changed is the reason they have not happened.
   - **Larger than a PyPI release, and it sits in front of this:** `BACKLOG.md` `(aad)` desktop
     installers is **launch-blocking** for the paid product - pip is not a channel the buyer can use.
     **`(aad)` was the work in progress as of 2026-08-12** ⚠ *(and is not what has been in
     progress since 2026-08-18: the soak, `(aei)`, `(aej)`, `(aem)` and CI cost are)*, starting
     with an artifact that can
     report what it contains - both of its acceptance criteria are on the frozen bundle and every
     guard that existed read the source tree.

4. **Post-launch queue**
   - Pull from `BACKLOG.md` in written priority order, with soak findings first.

---

## 2b. What stands between here and a first tag (2026-08-22)

⚠ **THE REPOSITORY CANNOT ANSWER THIS ON ITS OWN, AND THAT IS `(aef)`.** Counted there: of the
open entries, **almost none** carry a release marker in their own text. ⚠ **This said "of 64 open
entries" until 2026-08-22, when the section held 81** - the figure was `(aef)`'s 2026-08-19
reading, quoted here as if it were current. A count in prose rots; the command does not:

```
sed -n '/^## Approved - still to build/,/^## Settled technical stances/p' docs/BACKLOG.md \
  | grep -cE '^ *- \*\*\([a-z]+\)'      # open entries. 81 -> 80 -> 77 -> 76 -> 75 -> 76 across 2026-08-22.
``` The release question *"is not stored
anywhere - it is RECOMPUTED from judgement every time it is asked, which is why it comes out
different."* What follows is such a recomputation, dated so the next one can disagree with a
version rather than with a memory. It is not a substitute for `(aef)`.

### ⚠ THE RELEASE LIST - the one place that answers "what must ship before v1"

**This is `(aef)`'s Option B, and it exists because the answer was not stored anywhere**: it was
recomputed from judgement every time it was asked, which is why it came out different. Below is
the list; the prose after it is the reasoning, and where the two disagree **the list wins** and
the prose is stale.

⚠ **STATE IS DERIVED, NEVER TRUSTED.** `test_the_release_list_is_answerable.py` reads this table,
resolves every letter against `BACKLOG.md` and `SHIPPED.md`, and **fails when the declared state
and the real one disagree** - so a letter here that ships without this line changing is caught by
a test rather than by somebody re-reading. That is the whole point: the 2026-08-22 whole-backlog
re-read found two entries closed in fact and four diminished, and **nothing automatic could see
any of it**. This list is the part that can be made to see.

| letter | state | why it is on the list |
|---|---|---|
| `(aad)` | DONE | ✅ **Closed 2026-09-01 (P175).** `packaging/installer.iss` (`06f3796`) and `packaging/build_deb.py` (`c2120ae`) both exist and the release job builds them. ⚠ **The entry corrected itself on 2026-08-30** and moved its one surviving blocker - the download page - to `(afg)`; it was still being quoted as the launch gate for two days after that, and this row is where that was visible. |

🔒 **THE LIST IS DELIBERATELY SHORT, AND ITS SHORTNESS IS NOT AN OVERSIGHT.** `(aef)` rules that
populating it *"from the backlog as it stands would encode today's guesses as the answer - the
same mistake in one file instead of 57"*, and that **the list itself is a ruling the maintainer
makes**. So it is seeded with what the repository already declares and nothing else: `(aad)`
because it says so, and no letter here on anyone's inference. **Adding to it is a decision, taken
here, on purpose.**

⚠ **AND B'S HONEST LIMIT, restated where a reader meets it rather than left in the entry: this
makes the LIST answerable, not the BACKLOG.** Asking *"is `(aci)` needed for v1?"* still returns
silence. That is the state the project is actually in, and a shape that admits it beats one that
manufactures 57 answers.

**Not on the list and not letters at all** - they have no entry to resolve against, so the guard
cannot hold them and this line is what carries them: the **publish job has never run**, and
`(aad)` item 5's **download page** (whose home is `(afg)`, itself undecided as to whether it
blocks). Both are detailed below.

### Actually blocking

| | |
|---|---|
| **`(aad)` installers** | The **only** entry the backlog calls *"LAUNCH-BLOCKING"*. Its two biggest items are ✅ built and now proven: the release lane and the Windows installer. |
| **`(aad)` item 5 - the download page** | D9 requires Windows users be told what SmartScreen will show, **in plain language, above the button, before they download**. Not written. ⚠ Confirmed still mandatory 2026-08-21: an unsigned installer on winget still shows the warning, so there is no second path. |
| **The publish job has NEVER RUN** | `gh run list --workflow release.yml` shows **0** tag-triggered runs. Build is proven on both platforms; **sigstore signing and `gh release create` are not**. This is now the largest untested subsystem, and it is untested *by construction* - only a real `v*` tag fires it. |

### Not blocking a tag, corrected from a working list

- **`(afe)` is closed** (2026-08-22), so it is no longer on the list above. A catalog that cannot
  be written now ends the run with a report rather than a traceback, and removes the one copy it
  could not record so the next run converges instead of duplicating. Measured end to end: run one
  stops at 33 files / 33 rows with no traceback, run two finishes 72 / 72 with no `_1` suffixes.

- **Attorney clearance is required before MONETIZATION, not before a tag.** §1 above: *"attorney
  clearance is still required before monetization"*. A free release does not wait on it. What is
  live now is the trademark residual as a **pre-monetization obligation**.
- ✅ **`truestill.app` and the download page are `(afg)`, filed 2026-08-22 by this section.**
  Whether it blocks a first tag is **not decided** and the entry deliberately does not assume -
  it records the arguments both ways so the ruling is made against them. The domain is bought
  (maintainer, 2026-08-22); D9's *"above the button, before they download"* requirement is
  quoted there in full.
  ⚠ **This bullet read *"appears NOWHERE in this repository - no entry, no decision, no mention …
  recorded here as a question, not as an item"* until 2026-08-22, after `(afg)` existed.** Left
  visible because it is the fifty-eighth member closing and the sixty-second member opening in one
  bullet: writing the claim down is what let `(afg)` be filed against it, and then **the sentence
  that produced the entry was the one place the entry was not recorded.** A section that files an
  item is the section most likely to still describe the gap it filed.
- **`(aad)` item 6, frozen CLI startup, is UNMEASURED** and is a *quotable-number* gap rather than
  a gate: nothing claims a figure, so nothing is wrong yet.

### ⚠ What the first tag COSTS, which is not a blocker but must not be a surprise

- **`(adz)` expires at the first tag.** Its rule - no compatibility paths, no legacy fallbacks,
  because no users exist - holds *"until the first release tag"*. Every entry justified by it stops
  being justified the moment one is cut.
- **A `v*` tag is the PUBLISH trigger, not a dry run.** On a tag push there are no
  `workflow_dispatch` inputs, so `github.event.inputs.dry_run != 'true'` is true and the publish
  job runs. There is no such thing as a rehearsal tag; rehearse with `workflow_dispatch`.

### What is no longer a risk

**The release lane was the largest untested subsystem and is not one now.** Proven on both
platforms across three dispatch runs, most recently **32555392424**: build, self-check on the
frozen artefact, installer, install/verify/uninstall, and - since `(aex)` - correct versioning on
all four artefacts from one derivation. Everything except publish.

## 3. Current blockers / risks

- ~~**Soak not closed yet.** No launch actions should outrun this gate.~~ **Soak is DEFERRED, not
  failing** (2026-08-12, §2 item 1). It is not closed and is not claimed to be; it is no longer
  what other work waits behind. What remains open is the *knowledge* - the failure class that only
  a real library produces is still unmeasured, and nothing below should be read as covering it.
  ⚠ **MEASURED 2026-08-20** - see §1. Five entries, three shipped.
- **Absolute-path portability remains open** (`BACKLOG.md` `(xx)`; ⚠ `(yy)` was listed here too and is **BUILT 2026-08-02** as `truestill repoint-sources OLD NEW` - reconnect UX is done, the portability of the stored paths is not. This line was right and `BACKLOG.md` was wrong: `(yy)` stayed listed as unbuilt there until **2026-08-22** and was in `SHIPPED.md` not at all, which is the one thing the 2026-08-01 split exists to prevent):
  `files.source_path`, inplace roots, reclaim journal path semantics, and reconnect UX.
- **Known coverage gap: the unreadable-directory path is unverified on Windows.**
  `scan_source` was swapped from `sorted(rglob("*"))` to `Path.walk(on_error=...)`, and the
  every `test_unreadable_source.py` test (`grep -c '^def test_'
  packages/truestill-core/tests/test_unreadable_source.py` - **6** on 2026-08-15) plus
  `test_unreadable_paths.py::test_a_real_locked_directory_raises_from_is_dir` **skip on
  Windows** - `chmod 000` does not deny the owner there, so the fixture cannot create the
  condition. Ordinary traversal *is* exercised on Windows (`test_organizer.py`, `test_heif.py`,
  `test_exiftool_original_backups.py`), so what is untested is specifically the part the swap
  introduced: the `on_error` callback and `SourceScan.unreadable_dirs`.
  The skip is legitimate. It is **not** coverage, and a green Windows lane must not be read as
  proof this works. Closing it needs one of: a Windows-specific denial mechanism (an ACL denying
  the current user via `icacls`, which is the real equivalent of `chmod 000` there), or a
  deliberate decision to accept the gap and say so here instead. Not yet chosen.

- **Known coverage gap: `CREATE_NO_WINDOW` suppression is unverified - and since 2026-08-01 it
  is unverified for a MEASURED reason rather than an untried one.** The distinction matters:
  this is no longer "we have not tried", it is "we tried and the flag did not demonstrably
  suppress".

  The Windows throwaway (`BACKLOG.md` `(aad)`, run 30692798020) exercised the `AttachConsole`
  technique for the first time, and **the technique is measuring the wrong thing.**
  `CREATE_NO_WINDOW` creates an **invisible console** - the child *is* attached to a console,
  it simply has no window. `DETACHED_PROCESS` is the flag that yields no console at all. So the
  flagged child being attachable is **exactly what that flag should produce**, and attachability
  cannot distinguish suppressed from unsuppressed. This is not a contaminated measurement to be
  re-run; it is the wrong observable.

  The control still earned its place twice over. Under Briefcase it failed with
  `ERROR_ACCESS_DENIED` - that process already owned a console - and the gate refused to report
  a measurement, which is the false pass it exists to prevent, caught on its first run.

  **What would actually measure it:** the console's *window*, not its existence.
  `GetConsoleWindow()` returns `NULL` for a console that has none, so attaching to the child and
  then asking for its console window distinguishes the two - the attach stops being the verdict
  and becomes the setup.

  *Green CI still proves the plumbing:* the flag resolves to a real constant on Windows rather
  than the `0` it is on POSIX, and all five call sites capture output and return exit codes
  through the wrapper. *It does not prove the window is suppressed.*

- **PARTLY CLOSED 2026-08-01: the windowed-launch branch of the legacy-catalog probe.** The
  Windows throwaway's PyInstaller artifact reported `has_console: {stdout: false, stderr: false}`
  with a `reports\catalog.sqlite` in its working directory and resolved to the **data
  directory** anyway (`skipped_the_probe: true`). No faked `sys.stdout = None` involved, so the
  branch is proven to work when the streams really are absent.

  **The caveat, since the same run's console reading turned out to be a measurement artefact:**
  that artifact had null streams because PyInstaller's `--noconsole` bootloader nulls them in
  software, not because the launch was detached. The branch is proven; *that a double-clicked
  app reaches it* is a separate claim resting on the same unmeasured question as the rest.

  Recorded rather than deleted because the pair used to be one entry and are now different in
  kind: **this one is answered; the one above is measured and still open.** The third launch fix,
  the uvicorn no-console startup crash, was never in this category at all - its failure is in
  *configuration* rather than in windowing, so it is proven on every platform and closed.

- **`(aad)` packaging is NO LONGER PARKED** (2026-08-13; this bullet said PARKED until then).
  The signing gate was waiting for a decision D9 had already made, and soak is deferred (§2).
  **Both acceptance criteria are discharged on three of four bundler/platform pairs**; the
  bundler is still unchosen and the open work is in `BACKLOG.md` `(aad)`, which is the source.

- **Kept for the mechanism, since it cost two runs to learn:** the console reading that appeared
  to block the choice was a **measurement fault**, not a bundler difference. Briefcase's config
  applied exactly as written - GUI stub, `formal_name.exe` naming, and the stub's PE header reads
  `Subsystem = 2 (WINDOWS_GUI)`. The console came from the launcher: **a GUI-subsystem process
  does not get a console *allocated* but still *inherits* one**, and the job used PowerShell
  `Start-Process` from a shell that owns one. PyInstaller only looked different because its
  `--noconsole` bootloader nulls the streams in software regardless of launch.

---

## 4. Standing session rules (short form)

- 🔑 **A BRIEF THAT ASSERTS A CAPABILITY EXISTS NAMES THE SYMBOL** (2026-08-29). Measured: over
  five consecutive briefs, **four specified something that did not exist** - a folder-date tier, a
  `year_only` field, a `find --duplicates` flag, and a photo dated `2019-01-01` from a `filename`
  source. **All four died in briefs; ZERO of them exist in `BACKLOG.md`** (checked by grep), so
  this is not backlog rot - recorded work verified fine, and the citation guard
  `test_live_documents_cite_code_that_exists.py` is green over every live document.
  **What the four shared:** each named a mechanism at the vocabulary layer - a tier, a field, a
  flag, a subcommand - and asserted it **already existed** rather than that it was wanted. That
  framing is what disabled the check: *"build X"* invites *"where would X go?"*, while *"X already
  returns groups, route to it"* invites only *"where is the route?"*. **The false half was always
  the premise clause, never the requested change.**
  **So: name the symbol.** `find --duplicates` costs one grep and would not have survived being
  written down. ⚠ **Filed here rather than in `ENGINEERING_STANDARD.md` §4 deliberately** - §4 is
  the portable canon about how CODE is written, and this is about how work is SPECIFIED in this
  project's briefs. A rule about session conduct in the engineering canon would be `(agc)`'s
  shape, filing something where nothing enforces it and where a reader would not look for it.
- 🔑 **AN ENTRY YOU ACT ON IS RE-READ AGAINST THE COMMIT THAT CHANGED ITS GROUND** (2026-08-30).
  The rule above catches a **brief** that asserts something false. This catches the opposite
  direction, and they are different mechanisms with different fixes:

  | | source of the false premise | fix |
  |---|---|---|
  | the rule above | a brief asserts a capability exists | name the symbol |
  | **this rule** | **an entry was true when filed and OUR OWN WORK made it false** | re-read it against the commit that did |

  ⚠ **Both are now evidenced, and neither guard would have caught the other.**
  P150 found two phantoms - `classify_unwritable`'s "EPERM inconsistency" and `(ael)` - that came
  from **me repeating a report**, not from a brief; the citation guard was green over both because
  the code they name exists, it just no longer does what the prose says. Then `(aad)` was quoted
  as *"no desktop installer exists"* **eight days after run `32555392424` proved both installers**,
  in a release-readiness answer where it was the headline.

  **The check is one command and it is cheap**: before acting on an entry, `git log --grep '(xxx)'`
  and read the newest commit that touches its subject. `(aad)`'s premise died the day the release
  lane went green, and nothing connected the two because the lane's commit did not name the letter.

  ⚠ **`test_live_documents_cite_code_that_exists.py` CANNOT close this and should not be expected
  to.** It proves a citation resolves to a line that exists; it cannot read prose and cannot know
  that a workflow going green retired a sentence three files away. **Stated so the next person does
  not read a green suite as coverage of it** - `ENGINEERING_STANDARD.md` §4's silent instrument,
  on documents rather than on code.
- **Staged workflow:** one requested step at a time; no silent run-ahead.
- **Research-first + conflict-first:** flag spec/engineering conflicts before coding.
  Research sources: repo docs (outrank), source, free public only - **no paid third-party
  research APIs or hosted tools** (`ENGINEERING_STANDARD.md` §3.1).
- **Dry-run default:** writes happen only on explicit apply paths.
- ⚠ **`make check` before every commit; do NOT run `make gate` for backend work** (2026-08-20).
  The CI `e2e` job runs **nightly and on `workflow_dispatch`** (re-decided 2026-08-22; it was
  `if: false` on a condition that could not fire), so a push costs ~3 minutes instead of ~25 and
  the browser lane is not dark. ⚠ **This said *"the 470 browser tests"* until 2026-08-22, when the
  lane held 502** - count it (`uv run pytest tests/e2e --collect-only -q`), never quote it.
  If a change genuinely reaches a screen, **say so and ask**.
  Its silence is not coverage. The three-OS `check` matrix is kept - it is the only thing that
  sees Windows and macOS, and on 2026-08-22 it caught **two** platform defects in one primitive
  that no Linux run could (`(aaw)`; `ENGINEERING_STANDARD.md` §4's sixty-first member).
- **Never push unless asked.** ⚠ And a `pre-push` hook judges the tip being pushed onto:
  a RED tip refuses (`TRUESTILL_PUSH_ANYWAY=1` waives that one check - the agent runs it
  itself when the push IS the fix, ruled 2026-08-24); a run STILL IN FLIGHT is waited out,
  bounded at 480 s, then refused - `TRUESTILL_PUSH_CANCELS_THE_RUN=1` is the separate,
  named escape that kills it. §2's *pending result outranks a ready batch* covers
  **contention and outcome**; only the first used to be honoured (three commits on a red
  `main`, 2026-08-21), and the gate itself ran INERT from 2026-08-23 to 08-24 because
  pre-commit never forwards the stdin it read - `check_push_gate.py`'s docstring is the
  full story.
- **Commit identity policy:** `dinesh-ad`; no co-author/AI signature trailers.
- **Corpus fence for real-library testing/profiling/soak** (short form; the binding wording is
  `IMPLEMENTATION_STANDARDS.md` §5, which is the source - do not restate it here):
  - test / profile / soak against **only** source `~/TruestillLibrary/Input` → destination
    `~/TruestillLibrary/Output`. `Input/Testing-new` stays out.
  - **`/home/dinesh/pCloudDrive/` and `/home/dinesh/Icedrive/` are FENCED OUTRIGHT**: never read,
    never walked, never stat'd, at any depth, under any flag. Never root a `find` at
    `/home/dinesh` - a bare `find /home/dinesh -maxdepth 4` walks both. ⚠ Tightened 2026-08-14
    from *"READ-ONLY: resolve, stat and read a path to understand structure"*; both are FUSE mounts
    backed by a network service, so a `stat` is a round-trip billed to the maintainer's disk, and the old rule
    named no path so it could not be checked before a command ran.
  - **The locked folder inside it is OFF LIMITS, unconditionally** - do not resolve into it,
    stat inside it, or descend. No task-scoped exception exists; only the maintainer grants one.

Full wording and enforcement details live in `IMPLEMENTATION_STANDARDS.md` and `BACKLOG.md`.

---

## 5. Easy-to-rediscover traps (keep these cached)

- **Two stacked `@pytest.mark.skipif` decorators do not short-circuit.** Every decorator's
  condition is evaluated at import, so `skipif(os.name == "nt")` above `skipif(os.getuid() == 0)`
  raises `AttributeError` on Windows and the **whole module fails to collect** - its tests stop
  running on that lane while the others stay green. Write one condition:
  `sys.platform == "win32" or os.geteuid() == 0`. Enforced by
  `packages/truestill-app/tests/test_platform_skips_collect_everywhere.py`.

- Density-relative thresholds invert at both extremes (dense days shatter, sparse years fuse),
  and synthetic fixtures can hide it - see `events-clustering-research.md`.
- One string cannot express two shapes (event axis, Everyday bucket, effective-layout truth) -
  see `trip-grouping-research.md` and `migration-routing-research.md`.
- A fixture that cannot fail against the bug is not a regression guard - run it against the bug;
  process + examples in `ENGINEERING_STANDARD.md`.
- UI source assertions do not prove end-to-end flow correctness (the `innerHTML` re-parse case
  left resume dead; Playwright caught it) - see `IMPLEMENTATION_STANDARDS.md` and `DECISIONS.md`.
- Measure before optimizing (SHA-256 ~1% wall vs exiftool ~74%) - see `PERFORMANCE.md` and
  `preview-performance-profile.md`.
- **`(gg)` is not the fix for the 2,057-photo 2014-08 Everyday folder.** That dump was
  trip-claimed (Wayanad). The threshold guards rare un-evented heavy days (soak: one hit,
  `2013-09-30` / 62). See `SHIPPED.md` `(gg)`.

---

## 6. Where to look up details

- Product stance and superseded decisions: `DECISIONS.md`
- Binding engineering/data/process contract: `IMPLEMENTATION_STANDARDS.md`
- Open items with build-ready constraints: `BACKLOG.md`
- Performance evidence and do-not-optimize list: `PERFORMANCE.md`
- Historical investigations and alternatives considered: `docs/*-research.md`
- Move/remount user procedure: `moving-machines.md`

If a research note and the contract disagree, the contract wins.
