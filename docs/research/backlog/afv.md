# (afv) `(ady)` INTRODUCED AN INTERMITTENT FAILURE IN THE CONCURRENT-MIGRATION TEST, AND THE MECHANISM IS NOT KNOWN.

*Body of backlog entry `(afv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
