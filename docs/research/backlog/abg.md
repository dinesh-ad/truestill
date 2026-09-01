# (abg) The reassured state has no notion of staleness - "Schrodinger's backup".

*Body of backlog entry `(abg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abg) The reassured state has no notion of staleness - "Schrodinger's backup".**
  - 📌 **READ THIS FIRST: THE EXPOSURE RANKING IN THIS ENTRY IS INVERTED, measured 2026-08-10 on
    the maintainer's own catalog.** The 395 on `Morrowkeep` are **already reported** - `status`
    says *"395 file(s) exist on only ONE drive"* and names the drive. The user is being told.
    The silent case is the other one: `Output` and `The Memory Cabinet` hold the **same 2,269
    files** (full overlap, checked), so those read as **safe in 2 places** - while `Output` is
    reachable, carries its marker, and contains **zero media files**. Nobody is told anything.
    **It is larger, it is silent, and it is the only one that is checkable.** Lead any fix with it.
  - ⚠ **AND `Morrowkeep` CAN NEVER LEGITIMATELY REACH `GONE`.** Its path is absent because the
    **entire cloud mount it lived on is absent**, so *gone* and *unplugged* are indistinguishable there. A
    `GONE` that fired on it would be the cry-wolf failure on the very case that motivated this
    entry. Reachability is a **precondition** for the state, not a detail of it.
  - ⚠ **`GONE`'s justification is narrower than this entry claims, and the narrower one is the
    real one.** `OFFLINE` is not "we have not looked recently": `drive_reach` is a **live** marker
    read and `drive.py:149` says verbatim *"we know where it was; it is not there now"*. So `GONE`
    is **not** the first state meaning we looked. What it adds is **durability** - it persists an
    observation that is currently computed and thrown away (`service/verify.py:72-79` produces
    `CopyStatus.MISSING` per copy and records nothing; `mark_copy_verified` fires only on
    success). A narrower claim honestly stated beats a flattering one.
  - ✅ **STAGE 2 SHIPPED 2026-08-11 - and it leads with a defect STAGE 1 INTRODUCED.** Stage 1
    carried `drives.last_verified` to the sentence a person reads. It did not ask what advances
    that date, and the answer was: every verify run, unconditionally, on both surfaces. So a run
    whose own summary said `missing: 2269` reported the claim as **checked today**, and so did a
    run cancelled at the first file. That is this entry's own thesis - history reported as state -
    reappearing inside this entry's own fix, and it is worse than what Stage 1 addressed: Stage 1
    made the claim datable and the date meaningless. Recorded as `ENGINEERING_STANDARD.md` §4's
    **thirty-sixth** member, because the mistake generalises to any freshness field.
    - **The drive's date is now DERIVED from its copies**, `MIN` and NULL the moment any copy has
      never been confirmed - which covers missing, unreadable, unverifiable and *not reached
      before the user cancelled* without enumerating them. Not a new rule: it is
      `custody_freshness`'s own weakest-leg argument one level down. Structurally incapable of
      over-claiming beats correct while every call site remembers.
    - **Rejected: "do not stamp when anything failed."** One `UNREADABLE` file on a 10,000-copy
      drive would leave the claim permanently undated. A different lie is still a lie.
    - **v19 `file_copies.missing_at` persists what verify already computed and threw away.** Only
      `MISSING`: `UNREADABLE` is *we could not look* and `MISMATCH` is a drive still holding
      something at that path - different facts needing different words, `(ach)`. **The row is
      never deleted**; it is the only remaining clue that content was once written there.
    - **TWO PRECONDITIONS WERE ALREADY STRUCTURAL AND WERE NOT BUILT. Do not "fix" the second.**
      `verify_run` starts by reading the marker and soft-fails without one, so `Morrowkeep` -
      where *gone* and *unplugged* are indistinguishable - **cannot reach the code at all**. And
      `verify_copies` answers every `MISSING` in `_partition`, **before any hashing starts**, so a
      cancelled run's set of absences is complete rather than truncated. The second is
      counter-intuitive and is what makes persisting from a cancelled run sound.
    - **Two counting rules, deliberately opposite.** A custody **promise** excludes what was looked
      for and not found (`custody_floor`, `single_copy_count`, `single_copy_shas`,
      `drives_holding`). A **history** gains a number rather than losing one: the drive card keeps
      `files` and adds `not_found`, so `Output` reads *"2,269 photos … 2,269 not found on
      2026-08-11"*. A count quietly dropping to zero destroys the only clue to what happened.
    - **Mutation found a hole reasoning did not:** removing the `missing_at = NULL` from
      `mark_copy_verified` killed no test, so a restored drive would have stayed uncounted with
      nothing the user could do. `ENGINEERING_STANDARD.md` §4's **thirty-seventh** member.
  - ~~⏳ **WHAT IS STILL OPEN IS STAGE 3, AND IT IS THE HARDER HALF: instance (2), `Output`.** Its
    marker went with its contents, so `read_marker` returns `None` and verify soft-fails - *the
    drive most in need of examination is the one the tool cannot be pointed at*, which is this
    entry's own line and is untouched by Stage 2.~~

  - ❌ **STRUCK 2026-08-15. "ITS MARKER WENT WITH ITS CONTENTS" WAS NOT TRUE OF `Output` WHEN
    WRITTEN.** `Output/.truestill-drive.json` carries `created: 2026-08-08T22:19:04Z` and an mtime
    of the same moment, **unmodified since** - two days *before* the 2026-08-10 observation this
    entry rests on. The file was there the whole time.
    - **Bounded exactly.** The mtime proves the file was **not modified**; a delete-then-restore
      would not preserve a 2026-08-08 timestamp. It does **not** prove what the author ran. The
      plausible innocent reading is that this paragraph describes **`Morrowkeep`** - whose entire
      cloud mount is absent, where the marker genuinely is unreadable - and attributed it to
      `Output`. Two instances, one paragraph.
    - ⚠ **AND `Output` IS SCRATCH, WHICH IS THE REAL LESSON AND IS NOW IN THE CONTRACT.**
      `TruestillLibrary/Input` and `Output` are **freely writable scratch on the maintainer's
      machine only** - copies, messy folders and leftover test output are all fine there. Today's
      grid testing organized into `Output/scratch-grid-test`, which is why a re-reading found
      **338 media files** where 2026-08-10 found none. **The entry is not careless; its evidence
      was PERISHABLE.** Any observation of `Output` is a snapshot of a mutable scratch drive that a
      single test run can undo, and **Stage 3 must not be designed against a state a test run can
      erase.** See `IMPLEMENTATION_STANDARDS.md`'s corpus-fence row.

  - 🧭 **WHICH EVIDENCE STAGE 3 MAY REST ON, since the two kinds behave differently.**
    - **DURABLE - catalog-derived, reproducible on any machine.** The counts held identically
      across both readings: `Output` 2,269, `The Memory Cabinet` 2,269, `Morrowkeep` 395; every
      copy on the first two marked verified and dated **2026-07-28**; `Morrowkeep` never verified;
      `The Memory Cabinet` has **no `path_hint`**, so `drive_reach` answers `UNKNOWN`. **This is
      the arithmetic the defect is about, and it survives anything done to the scratch drives.**
    - **PERISHABLE - filesystem observations of one maintainer's drives.** Marker presence, root
      contents, media counts, and everything derived from them. Unavailable to any other developer
      and mutable by any test run. **Cite with a date; never make it a premise.**
    **The obvious route was examined and refused, so it is not re-derived from scratch:**
    `drive_reach` folds two different observations into `OFFLINE` - *the remembered path is not
    there* and *the remembered path is there and is not this drive*. Splitting them is one `stat`
    and would name `Output` exactly. **It would also name an unmounted USB drive whose mountpoint
    directory persists**, which is ordinary on Linux and is the cry-wolf case wearing the other
    case's clothes. Telling those apart needs `filesystem.facts_for()`, which already parses
    `/proc/mounts` and which custody has never consulted. **That is the design question Stage 3
    owns**; inventing an answer inside Stage 2 would have put a guess where `DriveReach`'s own
    docstring says to report the honest third answer.
  - 🔬 **STAGE 3'S ASSUMED DEPENDENCY DOES NOT ANSWER STAGE 3'S QUESTION. Read 2026-08-15, not
    assumed from this entry.** `FilesystemFacts` has exactly **two** fields - `filesystem` and
    `max_file_bytes` - and `facts_for()` answers *"what filesystem is at this path"*, never *"is
    anything mounted here"*. An unmounted mountpoint resolves to the **nearest existing path** and
    reports the **parent's** filesystem, so `/media/USB` unmounted returns `ext4`, the root's. That
    is not a defect: the module exists for a FAT32 file-size preflight and does that exactly.
    - **Platform reality, from its own docstring:** Linux parses `/proc/mounts`, Windows uses
      `GetVolumeInformationW`, and **macOS and everything else return unknown ALWAYS, by design** -
      *"a guess here would be worse than silence."* Cost is cheap: O(mount lines), or one syscall.
    - ⚠ **So the paragraph above understates the work.** Consulting `facts_for()` would not tell
      `Output` from a drawer USB; it would mean **EXTENDING `filesystem.py` with mountpoint and
      device detection that does not exist** - new platform-specific code on the one axis the
      module already declines to guess, and unavailable on macOS by construction. That is
      materially larger than *"consult a module custody has never consulted"*, and this entry did
      not say so. **Anyone scoping Stage 3 from the paragraph above will under-cost it.**

  - 🔎 **A CHEAPER DISCRIMINATOR, RECORDED AS A CANDIDATE AND NOT AS A DECISION.** `drive_reach` is
    O(1) (one marker read) and counting media is O(files); **the middle was never priced**. *Is
    anything at all present under the root* is `next(os.scandir(root), None)` - **O(1), one
    directory read, no walk, no `/proc/mounts`, no platform-specific code.** It would separate
    three worlds that collapse into `OFFLINE` today: path absent; path present and **empty**; path
    present holding **someone else's files**.
    - **The blast radius is unusually small, checked rather than estimated.** `DriveReach` has
      **six** consumers - `cli.py:1033`, `cli.py:1137`, `decisions.py:1651`, `drives.py:533`,
      `organize.py:433`, `bake.py:354` - and **every one tests `CONNECTED` and nothing else**. Not
      one branches on `OFFLINE` versus `UNKNOWN`, so a fourth state is **additive by
      construction**: every existing caller keeps behaving identically, because they all ask "is it
      here" and a new not-here state answers that the same way.
    - ⚠ **THE CRY-WOLF CASE, AND IT IS REAL: an unmounted USB whose mountpoint directory persists
      is EMPTY.** So *"reachable, marker absent, root empty"* describes `Output` **and** a drawer
      USB, and the drawer USB is by far the commoner. **The test cannot tell a wiped drive from an
      unmounted one, and any message naming a cause will be routinely wrong.**
    - **But that argues against NAMING THE CAUSE, not against MAKING THE OBSERVATION.** The
      distinction that survives is not wiped-versus-unmounted; it is **"we looked and found
      nothing" versus "we could not look at all"**, and the empty-root check separates those
      cleanly and cheaply. Both situations deserve a sentence and the honest sentence is nearly the
      same one - *we can see this path and there is nothing there, so the copies recorded here
      cannot be confirmed* - which claims neither wiping nor unplugging and is strictly more than
      the zero words offered today.
    - ❌ **ANSWERED 2026-08-15, AND IT RULES THE CHEAP TEST OUT FOR THIS CASE.** `Output`'s root
      is **NOT empty**: five entries - `.truestill-drive.json`, `.truestill-decisions.json`, and
      three `scratch-*` directories. So `next(os.scandir(root), None)` returns an entry and the
      cheap test reports *"wrong drive"* for the very case it was reached for. The caveat this
      paragraph raised was the right one to raise, and the answer went against it.

  - ⚠⚠ **AND THE SAME READING INVALIDATES THIS ENTRY'S STAGE 3 PREMISE. Measured, not inferred,
    2026-08-15 against the maintainer's own catalog.** Stage 3 is framed above as *"its marker went
    with its contents, so `read_marker` returns `None` and verify soft-fails - the drive most in
    need of examination is the one the tool cannot be pointed at."* **That is no longer true:**

    | claim in this entry | measured 2026-08-15 |
    |---|---|
    | `Output`'s marker is gone | **present**, `uuid=19411f16…`, `label='Output'` |
    | `read_marker` returns `None` | returns a valid marker, **uuid matches** |
    | verify soft-fails, cannot be pointed at it | `drive_reach` returns **`CONNECTED`** |
    | contains **zero** media files | **338** media files under the root |

    **So the tool CAN be pointed at it, and the case that motivated Stage 3 is not the case that
    exists today.** Whatever emptied `Output` has since been partly refilled - the three
    `scratch-*` directories are test fixtures from other arcs - so the drive now holds 338 files
    that are not the 2,269 the catalog records. That is a **different defect from the one filed**:
    not *"the drive cannot be examined"* but *"the drive can be examined, is CONNECTED, and holds
    different content than recorded."*

    ⚠ **Stage 3 must be re-scoped against a re-measured instance before any design.** The counts
    (2,269 / 2,269 / 395) still match this entry exactly, so the custody arithmetic stands; what
    has moved is the reachability story the design was to be built on. **`The Memory Cabinet` has
    no `path_hint` at all**, so `drive_reach` answers `UNKNOWN` for it - a third shape this entry
    does not discuss.

    🔒 **`Morrowkeep` was NOT examined and must not be.** Its remembered path is under
    `/home/dinesh/pCloudDrive/`, which `IMPLEMENTATION_STANDARDS.md` fences absolutely - never
    read, walked or stat'd, at any depth, under any flag. Its row above is from the catalog only.

  - 🧭 **STAGE 3 AS IT STANDS TODAY, 2026-08-15. IT IS NOT DETECTION. IT IS CONSEQUENCE.**

    Every drive in the catalog is already in a state the product can describe: `Output` is
    **`CONNECTED`** and examinable, `The Memory Cabinet` is honestly **`UNKNOWN`** for want of a
    remembered path, and `Morrowkeep` is fenced and outside reach by construction. Verify already
    runs, already persists `missing_at`, and already derives a drive's date from its copies.
    Freshness is already carried to the sentence a person reads. **What is left is that staleness
    does nothing.** Both non-fenced drives report every copy verified and dated **2026-07-28**, and
    the product treats an eighteen-day-old observation exactly as it treats one from this morning:
    it states the count and offers no consequence, no prompt, and no degradation. **That is the
    title of this entry - history reported as state - surviving in the one place Stages 1 and 2 did
    not reach.** The claim became datable, then dated; it never became *conditional*.

    **Traced, not assumed:** pointed at `Output` today, `verify_run` reads the marker (succeeds),
    loads 2,269 copies, finds the recorded relatives absent, and - because `still_here` is not
    `None` - calls `mark_copy_missing` on each, then `refresh_drive_verified`. **The machinery to
    correct this instance already exists and works.** Nothing asks the user to run it.

    ✅ **THREE CANDIDATE ROUTES ARE RETIRED, and the work that eliminated them is kept because
    eliminating a design is a result.**
    - **`/proc/mounts` via `filesystem.facts_for()`** - retired: it answers *what filesystem is at
      this path*, never *is anything mounted here*, and returns unknown on macOS by design. Using
      it means extending `filesystem.py`, not consulting it.
    - **Splitting `drive_reach`'s `OFFLINE`** into path-absent versus path-present-but-not-this-
      drive - retired: it answers a question no drive in the catalog is currently asking.
    - **The empty-root check** (`next(os.scandir(root), None)`, O(1)) - retired on measurement:
      `Output`'s root is **not empty**, so the cheap test reports *"wrong drive"* for the very case
      it was reached for. The reasoning it produced survives and is worth more than the test was:
      **any message naming a cause will be routinely wrong, so the distinction to build on is "we
      looked and found nothing" versus "we could not look at all"** - not wiped versus unplugged.

    ⚠ **AND STAGE 3 MUST BE DESIGNED AGAINST CATALOG-DERIVED EVIDENCE ONLY.** The filesystem
    observations above come from scratch drives that any test run may rewrite; the counts and dates
    come from the catalog and reproduce on any machine. **Two readings a week apart disagreed about
    the filesystem and agreed exactly about the catalog.** That is the whole argument for which
    kind of evidence a design may rest on.

  - 🧭 **THE STAGE NUMBERS: THIS ENTRY GOVERNS, AND `SHIPPED.md` IS OFF BY ONE.** The freshness
    work is called **Stage 0** in `SHIPPED.md` (`(acr)`'s closure: *"reading `(abg)` Stage 0's own
    output"*) and **Stage 1** here. **Read every "Stage N" in this repo as this file's numbering.**

    `SHIPPED.md` is **not corrected**, and that is the rule rather than an omission: its entries
    are provenance, and a record edited to stay correct stops being one - the same reasoning
    `CLAUDE.md` applies to the dead `docs/CLAUDE.md` pointer, where a note resolves the drift and
    the record stays as written. Noted 2026-08-19.

  - ✅ **STAGE 3 SHIPPED 2026-08-19. STALENESS HAS A CONSEQUENCE, AND IT IS TIERED PER DRIVE.**

    **The blocker, found in design and it invalidated the first shape of the ruling.**
    `custody_freshness` sets `checked_at = min(checked) if checked and not never else None`, so
    **one never-checked drive removes the date for every other drive.** That is Stage 1's rule and
    it is right about a *single* date - none would be true of the whole claim - but it means
    whole-claim tiering can never fire on a library that has one unchecked place, which is the
    shape of this very catalog: `Morrowkeep` undated, `Output` and `The Memory Cabinet` dated
    2026-07-28. Both would have crossed 30 days on **2026-08-27** with nothing said.

    So the tier is computed **per drive and reported at the claim**. `checked_at` is untouched;
    `dated_at` is added beside it - the oldest date among the places that *have* one, which an
    unchecked place does not blank. Two true statements instead of one that hides both.

    - **Thresholds, and they are judgements**: `CUSTODY_SOFTENS_AFTER_DAYS = 30`,
      `CUSTODY_STALE_AFTER_DAYS = 90`, recorded in `drive.py` the way `run_health.TICK_SECONDS`
      is. The 3-2-1 rule is written **3-2-1-1-0** in current practice and the trailing 0 is *zero
      errors* - restores actually tested rather than assumed; CISA carries the form in the joint
      #StopRansomware Guide. The cadence those write-ups converge on is verification monthly and a
      deeper check quarterly. **Nothing was measured**: no library was left unchecked to watch its
      claim stop being true.
    - **The entry's own formulation, and deliberately not a quotation:** *a backup that has never
      been restored is an assumption rather than a control.* The line is widely repeated in the
      trade with no attributable source - searches return *"only a theory"*, *"a hypothesis"*,
      *"an assumption wearing a green checkmark"*. Recorded as this entry's wording so nobody
      later hunts for a citation that does not exist.
    - **Never-checked is its own state, not tier three.** It is a different claim - not *"checked
      long ago"* but *"never looked at"* - it has no age for a threshold to act on, and it already
      pre-empted every date branch on every surface, so it was structurally separate rather than a
      severity. It **leads** the claim, ordered by strength of evidence: no evidence before old
      evidence.
    - **No tone change in tier three.** `at-risk` stays reserved for real exposure; firmness lives
      in the wording. A copy checked in June is probably fine, and taking the alarm tone for it is
      the crying-wolf failure this entry exists to avoid.
    - ⚠ **The date is never replaced by the age.** This entry records that *a date that only gets
      older cannot mislead*, and a bare *"34 days ago"* is not such a value - it changes while the
      fact behind it does not. What legitimately changes with time is the **tier**; the date stays
      beside it. `Last checked: 2026-07-28, 34 days ago`, never the second half alone.
    - **The route is conditional on `drive_reach`, and it follows the same lead rule as the
      wording.** `truestill verify` takes a required path that must be a connected drive root, so
      a real path is named only for a CONNECTED drive and otherwise the line says what to connect.
      ⚠ **Found on the real catalog while building:** offering `verify <whichever drive happens to
      be plugged in>` is a working command that answers the sentence above it not at all - the
      user runs it, it succeeds, and the never-checked place is still never checked. So when a
      never-checked drive leads the claim, the route is about *that* drive.
    - **The app has no Check screen** - "Check a connected backup drive" is the first card on
      **Backups**. The panel's button navigates there and scrolls; it does not fill the path,
      because the claim names drives and not paths.
    - ⚠ **A whole fixture class was a time-bomb.** Once wording depends on the clock, a hardcoded
      `2026-07-28` crosses a threshold **by calendar** and turns a green suite red with no commit
      behind it. Every fixture that seeds a real catalog and renders a claim surface now computes
      its date from now; stub payloads keep literals because they state the tier rather than
      deriving it.
    - **Two mutants survived the first pass**, both real gaps: the reach check replaced by
      `if hint:` (no test had a hint that pointed anywhere, so none exercised a *stale* one - the
      actual `(adx)` gap 2 shape), and the lead rule, whose first mutant was badly designed -
      `insert(len(lines), ...)` is an append and reordered nothing.
    - ⚠ **`checked_at` / `custody_checked_at` WAS REMOVED 2026-08-19, AND THE RULE SURVIVED IT.**
      Stage 3 gave both surfaces `dated_at` to read, after which the older field had **no reader
      anywhere** - not the app, not the CLI, not the payload's consumers. What it encoded was
      *"no single date is true of the whole claim"*, and that rule now lives in two places that
      are actually read: `never_checked` being non-empty, and both surfaces **leading** with that
      rather than with a date. The field was a second encoding of the same fact, derivable from
      what remains (`checked_at == dated_at if not never_checked else None`).

      **Removed rather than kept**, on this repo's own precedent: `(aeb)` is the same shape one
      level up, where two names for one path produced a false claim precisely because nothing
      forced them to agree, and the standing no-users-before-the-first-tag rule removes the only
      other argument for keeping it. **A value computed and read by nobody is how the next
      divergence gets in.**

  - **Related, and filed separately because it is a different defect:** `(acq)` - "place" counts
    somewhere Truestill organized INTO, not somewhere a copy is kept.
  - **THE MOST IMPORTANT OPEN ITEM ON THIS PROJECT.** Everything below is evidence for the
    paragraph that follows; the paragraph is the point.
  - **THE GENERAL CASE, in the maintainer's framing.** A user copies A -> B. Truestill records two
    copies. The user then **deletes A**, which is normal and is often the whole point of
    organizing. Truestill never looks at A again. **It keeps reporting two places for files that
    now exist in one.**
    Every instance recorded here is that shape with a different cause - a queued write that never
    uploaded, a folder emptied by hand, a mount that vanished. **The defect is none of those. It
    is that the catalog reports HISTORY as if it were STATE.** A `file_copies` row is a true
    statement about the moment it was written and is read as a true statement about now.
  - **WHAT THE CODE SAYS, checked rather than assumed.**
    - **Nothing re-checks a `source_path` after the copy that recorded it.** The only code that
      looks is `reclaim`, which counts `missing_sources` - *"catalog rows whose source_path is
      gone / unreachable"* - and it looks only when a user runs it, for a different purpose
      entirely: deciding what is safe to free. **Custody never asks.** A source deleted the day
      after an organize is indistinguishable, to every count in the product, from one still there.
    - ~~**The custody count carries no freshness.** `last_verified` exists on both `file_copies`
      and `drives` and is surfaced per-drive in the drive list and in stats - but `library_status`,
      which produces the number a person actually reads, counts `file_copies` rows and **never
      consults it**.~~
      ❌ **STRUCK 2026-08-15: PRE-STAGE-1 TEXT, NEVER UPDATED AFTER STAGE 1 SHIPPED.**
      `library_status` **does** consult it - it calls `custody_freshness(catalog, drives,
      registered)` and its payload carries `custody_checked_at` and `never_checked_drives`. That is
      exactly what Stage 1 was for, and this paragraph describes the state Stage 1 removed. So *"kept in 3 places"* appears with no date beside it, and it is a claim the
      system cannot back: the data to qualify it is recorded and simply not carried to the place
      the claim is made.
  - ~~**THE JOB IS SMALLER THAN "ADD FRESHNESS TRACKING".** `last_verified` already exists on
    `file_copies` and on `drives`, and is already surfaced per-drive in the drive list and in
    stats. `library_status` - which produces the number a person actually reads - never consults
    it. **So this is not building a new capability. It is carrying data that already exists to the
    place the claim is made.** That changes the size of the work and should be stated before
    anyone scopes it as a schema project.~~
    ❌ **STRUCK 2026-08-15 - DONE, by Stage 1.** The carrying this paragraph asks for is built. Its
    instinct was right and is worth keeping for the next reader: the job was smaller than it
    looked, and it is smaller again now. See the restated Stage 3 below.

  - **PRIOR ART, and it is better than anything invented here.** `git-annex` solved this directly:
    - **Believed versus verified.** `Annex/NumCopies.hs` states that the ordinary count compares
      copies *"believed to exist"*, and that this *"is good enough for everything except dropping
      the file, which requires active verification of the copies."* **Truestill counts believed
      copies and presents them as custody. That is the defect in one line**, and it is the
      distinction this entry has been circling.
    - **It refuses what it cannot back.** `drop` fails with *"Could only verify the existence of 0
      out of 1 necessary copies"* rather than deleting on the strength of a record.
    - **It arrived independently at `GONE`.** Its trust states are trusted / semitrusted /
      untrusted / **DEAD**, where dead *"indicates the repository has been irretrievably lost."*
      Corroboration for the name, from a system that has lived with the problem for years.
    - **Anything another process can write to is untrusted BY DEFAULT.** `importtree` remotes are
      always untrusted, on the stated grounds that something else could delete or change any file
      at any time, so trusting one for the only copy would cause data loss. Amazon Glacier is
      untrusted because its inventories may not represent the current state. **There is no
      category of place Truestill writes to that this does not describe** - every destination is a
      folder on a disk the user also uses. That is the general statement; the three instances
      below are only evidence for it.
    - **Consumer prior art for the interface.** Lightroom badges missing photos with an
      exclamation mark, greys missing folders with a question mark, and offers
      *Library > Find All Missing Photos*, which users run as weekly housekeeping. It does not
      prevent editing outside the app; it **detects and marks**. One documented gotcha worth
      inheriting the lesson from: that count is **not dynamic** and refreshes only when re-run, and
      users are confused by the stale number - which is this entry's defect in a competitor.
      Immich moves external assets to trash on rescan when they vanish.

  - **SETTLED PRODUCT DECISION (the maintainer, 2026-08-09).** **Organizing is the product.
    Custody is a REPORT, not a promise.** Truestill will not become responsible for backups: no
    scheduling, no monitoring, no syncing, nothing requiring a daemon it has decided not to have.
    Custody exists only because copying inevitably teaches Truestill where things went, and that
    knowledge is reported as **dated fact**, never as an ongoing guarantee.
    **The consequence is the direction the fix should take:** *"kept in 3 places"* is a claim the
    system cannot back. *"394 files copied here on 7 August, not checked since"* is a fact that
    **cannot go stale - it only gets older.** Same data, no promise.

  - **SHOULD A SOURCE EVER HAVE COUNTED AS A COPY? It never did, and the premise is worth
    correcting because it moves the defect.** Checked: `file_copies` is keyed
    `(sha256, drive_uuid)`, a source has no `drive_uuid` and never gets a row, and
    `library_status` reads `file_copies` and not `source_path`. **Truestill already agrees with
    `git-annex` here** - the folder a user is about to empty was never counted.
    So the 2,269 were **destination** copies, genuinely written to a registered drive, and the
    failure is not that a source was trusted. It is that **a destination copy is written once and
    never looked at again.** git-annex's answer applies anyway, just one step further along: a
    destination is *also* a place another process can write to, which is exactly why it treats
    such remotes as untrusted by default.
    **What the count should have said all along:** not *"2,269 files in 2 places"*, but
    *"2,269 files copied to Output on 28 July 2026, not checked since."* Both sentences carry the
    same data. Only the second stays true after the folder is emptied.

  - **THE SHAPE OF A FIX - a design note, not a TODO, because it is schema and vocabulary and
    wants thinking rather than a patch.** Truestill needs a drive state meaning **"recorded, and
    the place it was recorded no longer exists"**, distinct from `offline`, and **custody must
    exclude it from the count.**
    - **Suggested name: `GONE`.** Not `missing` - that reads as "we cannot find it", which invites
      looking again, and is what `offline` already implies. Not `lost`, which sounds like
      Truestill's fault and may be untrue. `GONE` is short, unambiguous, and admits no hope of
      the drive coming back on its own. The existing `DriveReach` triple is
      `CONNECTED` / `OFFLINE` / `UNKNOWN`, and `GONE` sits naturally beside them as the fourth:
      the three current values all mean *we have not looked recently*, and this one means
      *we looked, and it is not there.*
    - **What `status` should say.** Not *"exists on only ONE drive (3-2-1 wants >=2)"*, which is
      what it says today about 395 files that have **no** copies. It should lead with the count it
      can stand behind and name the shortfall separately - along the lines of
      *"2,300 files in 2 places. 395 files have NO copy: recorded on 'Morrowkeep', which is gone."*
      The number a person reads must never include a drive in this state, and the drive must be
      named, because the name is the only clue to what happened.
    - **Why a label is the wrong lever, recorded so it is not tried.** Renaming the drive
      `Morrowkeep (gone)` makes the list read better while the count stays wrong. **A cosmetic fix
      on a wrong number is worse than the wrong number, because it looks handled.**
  - **THREE OBSERVED INSTANCES, 2026-08-07/09, on the maintainer's own library. None is
    hypothetical.** Ordered by exposure, not by discovery.
  - **(1) THE WORKED EXAMPLE - written, believed, verified in place, and gone.** Follow one
    instance the whole way, because it is more instructive than the abstract statement:
    1. **Written.** An organize run copied 395 files to a cloud-mount destination. Every write
       returned success, so custody recorded a second copy.
    2. **Believed.** `status` counted all 395 toward the 3-2-1 goal for two days.
    3. **Verified in place.** `rescan` reported *"395, where the catalog says they are"* in
       **0.15 s** - the local index answering, not the disk. Not wrong by its own definition: it
       states that it reads no bytes. **The definition is the defect.**
    4. **Never actually stored.** The vendor's server index held about 5 of them; 391 sat behind
       an upload task dated 18 July that never moved.
    5. **GONE.** The vendor application was uninstalled on 2026-08-08 and its cache directory went
       with it. **Those 395 organized copies no longer exist anywhere.** Verified: the cache
       directory absent, the mount absent from `/proc/mounts`, free space back to 65 G.
    **And the catalog asserted custody at every one of those five steps**, including the last.
  - **THE VOCABULARY GAP IS THE FINDING.** After all of that, the drive list still reads
    `Morrowkeep  395  offline  LAST VERIFIED: never`, and `status` reports the 395 as
    *"exist on only ONE drive (3-2-1 wants >=2)"* - **recommending a second copy for files that
    have none.** `offline` is the same word the system would use for a USB disk in a drawer, and
    it is the closest thing available. **There is no state meaning "recorded, and the place it was
    recorded no longer exists".** Until there is, the honest answer and the reassuring one are
    spelled identically.
  - **WHAT WAS NOT LOST, so this is not read as a data-loss story.** The 2015 originals are on the
    vendor's servers, untouched, and `TruestillLibrary/Input` still holds the sources. **What was
    lost is an organize run, not photographs** - the arrangement, the naming and the placement,
    all of which can be produced again from material that still exists. The cost is real but it is
    work, not memory.

  - **(2) 2,269 copies recorded on an empty folder, and the tool cannot look.**
    `TruestillLibrary/Output` was emptied by hand - 0 files, 0 bytes - having held 2,269 files
    when `rescan` checked it the same day. The catalog still records 2,269 copies there and
    `status` still counts them. **`rescan` refuses**: the drive marker went with the contents, so
    it answers *"isn't a Truestill drive yet"*. **The shape is worth naming on its own - the drive
    most in need of examination is the one the tool cannot be pointed at.**
  - **(3) A write accepted into a queue and recorded as a copy.** The original instance: a cloud
    mount returns success for a write that has only been queued locally, and custody records a
    second copy on the strength of the return value.
  - **METHOD - how to tell a cache read from a server read on a cloud mount, with numbers.**
    Measured on this mount: **cache reads 2-92 ms; cold server reads 3.9 MB/s.** A 6.3 MB file
    therefore takes about **1.6 s** from the server and about **85 ms** from cache, so **a read
    faster than roughly `size / 3.9 MB/s` did not come from the server.**
    Written down because it is the check that would have caught a wrong conclusion in this very
    investigation: 13 files were hash-verified off the mount in 2-92 ms and reported as proof the
    server held them. It was proof the *cache* held them. The argument rested on the cache having
    been emptied, which the same turn had already measured to be false (38.73 -> 40.35 GB).
    **Anyone measuring a cloud mount will make this mistake without the ratio in front of them.**
  - **THE PRODUCT FINDING, and it is not the clean negative it looks like.** Truestill cannot read
    another vendor's private database and will not ship that. But **it is not true that no signal
    exists. Truestill HAS signals it does not use, and none of them proves storage.**
    - `filesystem.facts_for()` **already** parses `/proc/mounts` on Linux and queries Windows
      directly. It would return `fuse` for this mount. Archive ingest consults it for FAT32 size
      limits; **custody never consults it at all.**
    - `archive_extract.py` **fsyncs and documents why**, while `LocalDestination.upload` is
      `shutil.copy2` with no flush. The write path that records custody never asks the filesystem
      for durability. On this mount `fsync` would very likely return success anyway - but then the
      false statement is the vendor's, not Truestill's silence.
    - A **vendor-neutral tell** exists and was measured: writing 3.39 GB to this mount grew local
      disk usage by 3.41 GB, **1:1**. A destination whose writes grow *local* storage by the same
      amount is being cached locally, whoever makes it. No private database required.
    - **None of the three proves storage.** All three can distinguish "not obviously a local
      disk"; none can say the bytes are on a server. So: **custody today cannot distinguish
      WRITTEN from STORED, and does not even distinguish LOCAL from NETWORK-BACKED, which it
      could.** That is a finding about the product, not about one mount.
  - **Record only. Nothing here is fixed**, and no catalog row, drive or file was modified in
    reaching it.

  Recorded 2026-08-05. **Record only; the product question wants soak evidence, not a design.**
  - **What the strip claims.** "every file in 2 places" is true of the **catalog record**, not of
    the disks. `library_status` counts `file_copies` rows and never consults reachability:
    **offline drives, drives whose location was never known, and drives never verified all
    count.** `last_verified` is recorded on every copy and **is not read on this path**.
  - **Why the wording already hedges.** "safe" was removed from the strip on 2026-08-05 precisely
    because recorded copies are not verified copies; it says where files are, which is what the
    catalog knows. So this is a known limit that is *stated*, not a lie - but the reassurance
    still does not age.
  - **The forum name for it is "Schrodinger's backup": never tested, so simultaneously valid and
    invalid.** A copy written two years ago to a drive not seen since reads identically to one
    verified this morning.
  - **The product question, deliberately unanswered:** should the claim decay - a verified-within
    window, a "last checked N months ago" qualifier, or a distinct state once a drive has not
    been seen for long enough? Every version risks nagging about a drive-in-a-drawer that is
    perfectly fine, which is exactly the trade `(gg)` and the risk-first strip ruling had to make
    elsewhere. **Soak is the instrument**: real usage will show whether stale reassurance is a
    real complaint or a theoretical one.
  - The data is already there - `drives.last_verified`, `drives.last_seen`, and `DriveReach` -
    so this is a wording-and-policy question, not a plumbing one.
