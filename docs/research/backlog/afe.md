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

  **1. The partial-failure policy is broken.** ⚠ *This said "§1" until 2026-08-23; the rule is
  `ENGINEERING_STANDARD.md` §4 Errors, a different authority (`(agc)`).*
  *"One bad file never aborts a batch - it is
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

  The catalog write is **four frames inside** the try that the partial-failure policy is built
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

  ### 3. The partial-failure question, with the options rather than a recommendation

  `ENGINEERING_STANDARD.md` §4 Errors: *"one bad file never aborts a batch - it is logged,
  counted, and reported at the end."*
  Does that extend to one bad catalog write?

  ⚠ **The asymmetry that makes this a real question**: a failed destination write costs **one
  file**, and the run's other files are unaffected. A failed catalog write costs **the record of a
  file that is now on disk** - and by §2 above, that record's absence is what duplicates the
  library on the next run. The blast radius is not the same, so the policy answering for one does not
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

  ---

  # RULED AND BUILT - 2026-08-22. Option **C**, with rollback.

  **The ruling:** busy (`SQLITE_BUSY`/`SQLITE_LOCKED`) is transient and per-file; anything else is
  permanent within the run and a **reported stop** that also stops copying. Plus the rollback the
  convergence measurement forced.

  ## The asymmetry that justifies the exception to §1

  > A failed destination write costs one file. A failed catalog write costs the **record** of a
  > file now on disk, and that absence is what duplicates the library next time. §1 answering for
  > one does not settle the other, and the stop is not a weaker promise - it is the same promise
  > applied to a different cost.

  §1 is about a file the product could not **use**, where skipping costs one file. Here the file
  is fine and already at the destination: there is no skip available.

  ## FOUR MEASUREMENTS THAT CHANGED THE DESIGN

  ### 1. `sqlite_errorcode` carries EXTENDED codes, so every comparison masks `& 0xFF`

  R5's code is **1544** = `SQLITE_READONLY_DIRECTORY` = `8 | (6 << 8)`, **not** `SQLITE_READONLY`.
  The same trap ran the other way and was **live**: `is_catalog_busy` compared the raw code to
  `{5, 6}`, so `SQLITE_BUSY_RECOVERY` (261), `BUSY_SNAPSHOT` (517) and `BUSY_TIMEOUT` (773) all
  answered *not busy* and would have stopped a run that should have waited. A plain contended
  write returns the primary `5`, which is why it never bit.

  ### 2. ⚠ R5 presents as `SQLITE_IOERR_DELETE` as often as `READONLY_DIRECTORY`

  **This is the finding that reclassifies a judgement below** - see *"the code called ambiguous is
  the COMMON presentation"*.

  Measured through the CLI rather than in a unit test: `chmod 555` on the directory does **not**
  stop writes at once. SQLite can keep reusing a `-journal` file it already created - opening an
  existing file needs permission on the *file* - and only the **removal** of it needs the
  directory. So the code depends on where in the transaction the refusal lands. Dropping `IOERR`
  from the recognised family would have left the commoner of the two answering with a traceback.

  ### 3. Guarding the write loop was not enough - the traceback moved

  With the per-file path fixed, a real run still ended in a stack from
  `catalog.finish_organize_run`, **after** `execute` returned. `cli.main` re-raised every non-busy
  `sqlite3.Error` by design. The fix belongs at the one seam that sees every catalog write in a
  command, not at each write.

  ### 4. ⚠ One predicate cannot answer both questions, and a first cut proved it

  *"Should we retry?"* is safe by default **no**, so unknown codes stop the run. *"Should we tell
  the user their catalog cannot be written?"* is safe by default **no** on the other side.
  Complementing busy for both turned `SELECT * FROM no_such_table` - a bug of ours - into advice
  about folder permissions, and reworded every unrelated job failure in the app besides. The
  recognised family is now enumerated (`PERM`, `READONLY`, `IOERR`, `FULL`, `CANTOPEN`); a bug
  keeps its traceback.

  ## BUSY vs LOCKED, and SQLITE_IOERR - reported, not silently sorted

  **They stay grouped, and the comment saying both mean *wait and retry* was false for LOCKED.**
  `catalog.py` opens one connection with no shared cache, so a genuine `SQLITE_LOCKED` is a
  conflict with ourselves: retrying can never clear it. It belongs on the permanent side on the
  evidence. It stays grouped only because an exhausted retry escalates to the same stop, so the
  outcome converges; the imprecision costs retry latency on a case that cannot happen without a
  bug of ours.

  ### ⚠ `SQLITE_IOERR` - the code called ambiguous is the COMMON presentation of the case

  It was placed on the permanent side as an **unresolved** call, and it then turned out to be how
  R5 usually arrives: measured through the CLI, a catalog directory denied mid-run fails with
  **`SQLITE_IOERR_DELETE`** at least as often as with `READONLY_DIRECTORY`, for the reason in
  measurement 2 above. **So this is not an edge that might one day matter - it is the ordinary
  path through the defect this entry exists to fix**, and it was sorted on a tie-break while being
  described as a corner.

  **The tie-break still holds, and it is the reason this is safe rather than lucky.** The evidence
  genuinely does not settle `IOERR`: it covers a failing disk and a flaky USB or network
  filesystem alike, and nothing at the call site distinguishes them. It was broken by **cost, not
  evidence** - calling a blip permanent costs a run the user restarts; calling a dying disk
  transient keeps writing to failing media. Had it gone the other way to "resolve" the ambiguity,
  the commonest form of R5 would now retry ten times and stop anyway.

  ⚠ **What a later reader must not take from this**: that `IOERR` is settled. Its *wording* side
  is settled and pinned - it is always a condition of the user's, never a bug of ours. Its *retry*
  side is still a judgement, and the frequency finding is a reason to look again if a transient
  `IOERR` is ever observed, not a reason to consider the question closed.

  ## THE ANSWER TO "DOES THE NEXT RUN CONVERGE?"

  **Before the rollback: no.** One orphan became two files, exit 0 - dedup misses, `_already_at_target`
  is a `samefile` check false in copy mode, `_free_relative` suffixes `_1`. The stop would have
  **bounded** the damage to one file rather than prevented it.

  **With the rollback: yes, exactly.** Measured end to end, 72 files, catalog denied after five:

  ```
  RUN 1  exit=7  traceback=0  files on disk=33  catalog rows=33
  RUN 2  exit=0  files on disk=72  rows=72  sources=72  _1 suffixes=0
  ```

  ### The rollback, and the one line it must never cross

  On a permanent failure the copy just made is removed, so nothing is left unrecorded. It is
  guarded because we are deleting a file **at a path we constructed**: the checksum is re-read and
  compared first, and any doubt leaves the file alone. A failed removal is **reported in the same
  block as the orphan**, never suppressed.

  ⚠ **`moved_in_place` is checked first and answers structurally.** Under `--in-place` the "copy"
  is a rename and the destination file is the user's **only** copy; no verification could make
  deleting it safe. There is no rollback in that mode - the file is left and named.

  ## The bind worth recording

  **You cannot journal the orphan, because the journal is the catalog.** The one place to record
  *"this file has no row"* is the thing that just refused a write. That is why the remedy is to
  not create the orphan, rather than to note it.

  ## Closes

  Every "NOT DECIDED" above is now decided except `SQLITE_IOERR`'s retry side, which is recorded
  as unresolved on purpose. `rescan` is named in both the stop's report and the backstop refusal.
