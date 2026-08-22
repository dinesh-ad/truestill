# (afe) A CATALOG THAT GOES UNWRITABLE MID-RUN ABORTS WITH A TRACEBACK AND LEAVES A FILE IT DID NOT RECORD.

*Body of backlog entry `(afe)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afe) THE WORST OF SOAK THREE.** Found 2026-08-21 by **step R5**. Three separate rules broken
  by one unhandled exception.

  ## MEASURED

  120 files, `chmod 555` on the directory holding `catalog.sqlite` once five had landed - SQLite
  must create `-wal` and `-journal` **beside** the database, so this refuses writes without
  touching the file:

  ```
  exit=1
  files on disk : 48
  catalog rows  : 47
  EXECUTED block: NOT PRINTED
  last line the user sees:
      sqlite3.OperationalError: attempt to write a readonly database
  ```

  ## THREE RULES, ONE CAUSE

  **1. §1's partial-failure policy is broken.** *"One bad file never aborts a batch - it is
  logged, counted, and reported at the end."* The batch **aborted**. 72 of 120 files were never
  attempted, and nothing says so.

  **2. §9 is broken in the most basic way: a raw Python traceback is the product's final output**,
  ending in `sqlite3.OperationalError`, with our own file paths and line numbers
  (`catalog.py:2738`, `record_uploaded`). `catalog_busy.py` exists precisely to turn a SQLite
  condition into a sentence; this condition reaches none of it.

  **3. A file is on the destination that the catalog does not know about.**
  `20140805_014501_Kodak PIXPRO FZ201.jpg` was copied and not recorded. That is the state `rescan`
  exists to repair, **reached silently** - because the traceback replaced the report that would
  have said so.

  ⚠ **The 48/47 gap is the copy-then-record ordering doing its job**, and that is worth saying:
  the copy lands *before* the row is written, so a crash between them leaves a file with no row -
  which is the safe direction. A row with no file would be the dangerous one, and it did not
  happen. The defect is that nothing **reports** the gap.

  ## WHY THE DESTINATION SURVIVED THE SAME TEST AND THE CATALOG DID NOT

  R3 refused the **destination** mid-run and every safety property held: catalog matched disk
  exactly, `.partial` was used, a re-run resumed, §1's accounting was complete. The difference is
  where the failure is caught. A destination write is inside the per-file `try` that §1's policy
  is built on; a catalog write is not inside anything.

  ## READ-ONLY INVESTIGATION, 2026-08-22 - and it corrects this entry's own diagnosis

  ### ⚠ 1. The catalog write IS inside the per-file boundary. The TUPLE is too narrow.

  **This entry says *"a catalog write is not inside anything"*. That is wrong**, and the
  correction shrinks the fix considerably. The chain:

  ```
  organizer.py:1789   try:
  organizer.py:1791       _execute_one_write(...)
  organizer.py:1508           -> _record_organized_file(...)
  organizer.py:1379               -> catalog.record_uploaded(...)
  organizer.py:1807   except (OSError, DestinationError) as exc:
                          record(ActionResult(..., ActionStatus.FAILED, None, str(exc)))
  ```

  The catalog write is **four frames inside** the try that §1's partial-failure policy is built
  on. What lets it escape is the exception tuple: `sqlite3.OperationalError`'s MRO is
  `OperationalError -> DatabaseError -> Error -> Exception` - **it is not an `OSError`**, verified.
  So the boundary is there, the write is inside it, and the tuple does not name the one error the
  write can raise.

  **The smallest boundary is therefore the tuple**, not a new structure. What it must not become
  is `except Exception`: the same argument `(aet)` makes at `_hash_one` does **not** transfer, because
  a catalog write has a knowable failure set (`sqlite3.Error`) where an image decoder does not.

  ### 2. Nothing repairs the gap, and ⚠ THE NEXT RUN MAKES IT WORSE - measured

  `rescan` **detects and names** the orphans and says so in its own words: *"No command repairs any
  of the above yet. This one only tells you."*

  The next `organize` does not repair, skip, or merely re-copy. Measured on three files left on
  disk with no rows:

  ```
  before   3 files on disk
  after    6 files on disk   -   ..._Canon_PowerShot_S40.jpg AND ..._Canon_PowerShot_S40_1.jpg
  the run reported:  organized (unique) : 3        exit 0
  ```

  The mechanism: dedup misses (no row for the sha), `_already_at_target` is a `samefile` check and
  is **false in copy mode** (source and destination copy are different files), so `_free_relative`
  finds the path occupied and **suffixes to `_1`**. Every subsequent run duplicates again.

  ⚠ **So "the gap is in the safe direction" is true about DATA and false about CONVERGENCE.** No
  row promises a file that is not there, and nothing is lost - but the state is not self-healing,
  it is self-*worsening*, and it worsens while reporting **exit 0 and a clean success**.

  ### 3. The §1 question, with the options rather than a recommendation

  §1: *"one bad file never aborts a batch - it is logged, counted, and reported at the end."*
  Does that extend to one bad catalog write?

  ⚠ **The asymmetry that makes this a real question**: a failed destination write costs **one
  file**, and the run's other files are unaffected. A failed catalog write costs **the record of a
  file that is now on disk** - and by §2 above, that record's absence is what duplicates the
  library on the next run. The blast radius is not the same, so §1 answering for one does not
  settle the other.

  **A. Extend §1: a catalog write failure is a per-file failure.** Add `sqlite3.Error` to the
  tuple; the file is `FAILED`, counted, named, and the run continues.
  *For:* smallest possible change; §1 read literally; a transient lock costs one file.
  *Against:* a permanently unwritable catalog produces **one failure per remaining file** - the
  run becomes N identical failures, which `(afd)` has already shown is an uncapped list of raw
  errno text. And every one of those files is **still copied**, so the run maximises the
  bytes-ahead-of-rows state that §2 shows is self-worsening.

  **B. A catalog that cannot be written is a legitimate stop - but a REPORTED one.** Catch it,
  stop, and print what landed, what was recorded, the difference, and where to go next.
  *For:* it is the honest reading of what the failure means - the run can no longer keep its
  promise to account for files. Bounded: the gap stays at one file.
  *Against:* it is a new state in the CLI's vocabulary (neither "finished" nor "one file failed"),
  and §1's sentence has to gain a stated exception rather than being read as covering everything.

  **C. Split by errorcode - transient continues, permanent stops.** ⚠ **The vocabulary already
  exists**: `catalog_busy.is_catalog_busy` distinguishes `SQLITE_BUSY`/`SQLITE_LOCKED` from
  everything else, by `sqlite_errorcode` rather than by message text.
  *For:* it matches what the two failures actually are - a lock clears, a read-only directory does
  not - and reuses a home rather than inventing one.
  *Against:* two behaviours to explain and to test; a lock that never clears degrades into A's
  worst case one file at a time.

  **D. Stop, and stop COPYING too.** As B, plus refuse to write further bytes once the catalog is
  unwritable, on the ground that bytes-ahead-of-rows is precisely the state §2 measures as
  self-worsening.
  *For:* it is the only option that treats the duplicate-on-next-run consequence as the thing to
  prevent rather than as a side effect.
  *Against:* the strongest reading, and it stops a run that could still be placing files correctly
  - a user with a full catalog disk but a healthy destination gets nothing organized.

  ⚠ **Whichever is ruled, `rescan` should be pointed at.** It already detects this exact state and
  already says nothing repairs it; a run that ends in this state and does not name `rescan` leaves
  the user with a report and no next step.

  ## NOT DECIDED

  - **Whether a catalog write failure should be per-file or fatal.** Continuing to copy files that
    cannot be recorded may be worse than stopping - but stopping must then be a *reported* stop
    with a count, not a traceback.
  - **Whether `catalog_busy`'s vocabulary extends to `readonly database`**, which is a different
    condition from a lock: waiting will never clear it.
  - **Whether the run should re-check the catalog's writability at all**, or whether preflight
    checking it once is the same mistake R3 was written about - *checked at the start, refused in
    the middle.*
  - **What `rescan` should be told.** The repair exists; nothing points the user at it.
