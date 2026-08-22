# (afv) `user_version` MOVED BACKWARDS ON DISK. `(adl)`'s STAMP WAS NOT IDEMPOTENT; `(ady)` ONLY MADE IT VISIBLE.

*Body of backlog entry `(afv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

> ⚠ **CORRECTED AND CLOSED 2026-08-22. THE TITLE ABOVE REPLACED:**
> *"`(ady)` introduced an intermittent failure in the concurrent-migration test, and the mechanism
> is not known."* **Both halves were wrong.** The mechanism is known and recorded below; and the
> defect is `(adl)`'s, dating from 2026-08-19, not `(ady)`'s. The investigation as first written is
> kept unedited beneath this note, because what it ruled out is worth as much as what it found and
> because a correction that deletes what it corrects leaves the next reader unable to tell which
> half moved.
>
> 🔑 **THE READING ERROR, WHICH IS THE REUSABLE PART.** The differential was sound: 12/12 green on
> the pre-`(ady)` tree, ~1 in 8 red after it. What was wrong was the conclusion drawn from it -
> **it proved VISIBILITY, not CAUSATION.** Measured afterwards with a probe that watches the file
> rather than the test's outcome, 40 rounds of six concurrent openers each:
>
> | tree | rounds where `user_version` moved backwards |
> |---|---|
> | pre-`(ady)` (`12076c7`) | **7 / 40** |
> | `(ady)` as shipped | **28 / 40** |
> | both fixes | **0 / 40** |
>
> The defect was there at 18% before `(ady)` existed. Now `ENGINEERING_STANDARD.md` §4's
> **sixty-third member**.
>
> ⚠ **AND THE SEVERITY INVERTED WHEN THE MECHANISM WAS FOUND.** The test goes red only when a read
> lands inside the window; runs where **all six openers returned 20** still moved the file
> `20 -> 5`, `20 -> 19`, `20 -> 4`. **The on-disk corruption is commoner than the test failure**,
> and a version below the schema means the file claims to be *older* than it is, so the next open
> re-runs migrations against columns that already exist.
>
> **THE MECHANISM.** Two openers of a behind catalog both read `version = 3` into a plain local
> before the loop. One completes the chain to 20. The other, still at the start, then runs
> `_apply_step(4)`, whose `PRAGMA user_version = 4` had no check that the file was already past
> it - so it stamped **backwards**. `(ady)`'s copy widened the gap between the two, and did so
> worst by copying on openers that had **zero steps to apply** - four of six.
>
> ✅ **FIXED IN TWO COMMITS, `(adl)`'s first**: `1f0dde7` re-reads the version inside the
> `BEGIN IMMEDIATE` `_apply_step` already holds and skips a step the file is past; `46b100e` gates
> the copy on `version < CURRENT_SCHEMA_VERSION`. Pinned by
> `test_the_stamp_never_moves_backwards.py`, which **constructs** the interleave rather than
> sampling for it - see its own note on why the first version of that test was weak.
>
> ⚠ **`backup()` was exonerated, and re-asking the question properly is what did it.** The first
> check was `Connection.in_transaction`, which returned `False` - the wrong instrument, and
> reported as though it settled the matter. Asked properly (write `99` from another connection
> after a contended backup, then read the source): the source sees **99, three trials of three**.
> No staleness, no lingering read transaction. The `after-copy@4` observation was a **correct**
> read of a file that really was at 4.

- **(afv)** Found 2026-08-22, hours after `(ady)` shipped, by running the gate on a docs-only
  change. **Filed rather than fixed because the cause is not established**, and
  `ENGINEERING_STANDARD.md` §4's twenty-sixth member is explicit: a test that fails
  non-deterministically is **quarantined and filed with its trace, never retried**.

  ## THE FAILURE

  `test_a_migration_step_is_all_or_nothing.py::test_concurrent_openers_of_a_behind_catalog_all_succeed`
  fails roughly **1 run in 8**, on Linux, locally:

  ```
  AssertionError: a concurrent open of a behind catalog failed:
    [20, 4, 20, 20, 20, 20]        <- one of six openers finished at schema 4, not 20
  ```

  ## ⚠ IT IS `(ady)`'s, PROVEN BY DIFFERENTIAL RATHER THAN ASSUMED

  §4's twenty-fifth member: *counting green runs on a mechanism that could lie measures nothing;
  build a differential.* Done, and the first attempt at one was **void** and is recorded because
  it is the fifth member's first worked example:

  - ❌ **Void control.** `pytest <worktree>/…` ran the pre-`(ady)` **test file** while
    `truestill_core` resolved through the **editable install** back to the real repo. 12/12 green,
    measuring the changed code.
  - ✅ **Valid control**, `PYTHONPATH` ahead of site-packages, with the resolution printed:
    `catalog.py` loaded from the worktree, `copy_before_migration` absent. **12/12 green.**
  - With `(ady)`: **~1 in 8 red.**

  ## WHAT HAS BEEN RULED OUT, EACH BY MEASUREMENT

  | hypothesis | test | result |
  |---|---|---|
  | the copy is merely **slow**, widening a pre-existing race | 20 ms `sleep` at the same point, pre-`(ady)` tree | **0/15 red** - not sufficient |
  | openers **desynchronised inside the chain** | random 0-4 ms before each `_apply_step`, pre-`(ady)` tree | **0/15 red** - not sufficient |
  | **staging collision between threads** - `safe_copy.staging_path`'s token is per-**process**, so six threads shared one path | made the backup's staging unique per call (fixed regardless: 1 distinct path -> 6) | **still 2/25 red** - real defect, not this one |
  | `backup()` leaves the source **in a transaction**, breaking later steps | measured directly | `in_transaction` **False** before and after; a later `BEGIN IMMEDIATE` succeeds |
  | `backup()` leaves the source with a **stale page view** | source read `user_version` after a concurrent writer committed | reads **19** correctly - not stale in the simple case |

  ## THE ONE HARD OBSERVATION, WHICH IS WHERE TO START

  Instrumented, on a reproduced run:

  ```
  (408, 'EXIT', 4, 'own-conn-again', 4, 'fresh-conn', 5)
  ```

  The failing opener's **own connection** reads `user_version = 4` while a **fresh connection to
  the same file** reads `5` at that instant, and the file reaches 20 shortly after. So that opener
  **applied only step 4 and returned**, while its siblings ran the chain to completion - and it did
  not raise. A `_apply_step` spy shows no step with `target=4` late in the run, so nothing stamped
  the version backwards over a finished opener; the opener genuinely stopped early.

  **The question to answer first: why does one opener's chain end after a single step without
  raising?** `version` is a local `int` read under the lock, and the loop is
  `for target, migrate in _MIGRATIONS: if version < target: _apply_step(...)` - which cannot end
  early unless the loop is not entered for later targets or `_apply_step` returned without
  stamping. Neither is explicable from the source as read, which is why this is filed rather than
  guessed at.

  ## ⚠ WHY THIS IS NOT "JUST A TEST PROBLEM"

  The scenario is real, not synthetic. `(adm)` records **six concurrent `Catalog._migrate` calls
  inside one app process** on a genuine first run - *"7828 opens reached `_migrate`"* - so an
  opener that silently finishes at the wrong schema version is a live shape, not a fixture
  artefact. A `Catalog` returned at schema 4 while the file is at 20 would then be used by
  whatever asked for it.

  ## OPTIONS, NOT RULED

  - **Revert `(ady)`** and re-land it behind an answer. The copy is valuable and its own tests are
    green; this is the honest option if the mechanism resists a short investigation.
  - **Serialise the copy** so only one opener of a behind catalog takes one - the copy is
    per-catalog, and six openers taking six copies of one file is wasteful independently of this.
  - **Quarantine the test** - explicitly the **worst** option here and named so it is not reached
    for: the assertion is about a real property, and marking it flaky launders the regression.

  ## RELATED

  `(ady)` (the change that introduced it), `(adl)` (which wrote the test and the per-step
  transaction it guards), `(adm)` (the six-concurrent-openers shape in the app), `(ads)`
  (the concurrency model all of this rests on).
