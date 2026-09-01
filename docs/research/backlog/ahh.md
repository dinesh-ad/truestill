# (ahh) A FAILED "SAVE NAMES" REPORTS TOTAL FAILURE OVER A PARTIAL SUCCESS.

*Body of backlog entry `(ahh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahh) A FAILED "SAVE NAMES" REPORTS TOTAL FAILURE OVER A PARTIAL SUCCESS.** Filed
  2026-08-25 (P72); ⚠ **re-scoped and re-ranked 2026-08-25 (P74) after reproducing it.** The
  entry as filed described a defect one class more serious than the one that exists, and named a
  trigger no caller can reach. The original text is kept below the correction rather than
  deleted.

  ## THE DEFECT

  `commit_trips` (`trip_review.py:commit_trips`) iterates the reviewed decisions and **catches
  nothing**. Each catalog write is atomic on its own through `Catalog._tx` - `create_trip` writes
  `trips` and `trip_days` in one transaction - but that is **per call, not per apply**. A raise on
  the seventh trip therefore leaves the first six committed, and **nothing anywhere records that
  the run did not finish**.

  It is not hypothetical: `create_trip`'s own docstring advertises the `sqlite3.IntegrityError`
  that would do it (`catalog.py:Catalog.event_by_signature`). `commit_catalog` (`event_review.py:propose_from_catalog`) has the same
  shape for events.

  ## WHY IT CANNOT BE CLEANED UP AFTERWARDS

  ⚠ **Checked rather than assumed**: there is no `delete_trip` and no `unname` in the tree. The
  only `DELETE FROM trips|events|trip_days` anywhere is inside `update_trip_days`
  (`catalog.py:Catalog.source_hints_for_drive`), which deletes a trip's own day rows only to reinsert them. Nothing writes
  `migration_journal` on this path either.

  So a half-applied naming is **neither undoable nor detectable**.

  ## WHAT IT IS AND IS NOT

  ⚠ **Surface-independent.** This is true of the app today and would be equally true of any CLI.
  It is not part of `(ahf)`'s surface question and was deliberately kept out of its closure.

  `ENGINEERING_STANDARD.md` §4 Errors is the rule it fails - *"one bad file never aborts a batch -
  it is logged, counted, and reported at the end"*. **Which remedy is the ruling this entry
  wants**: skip-and-continue with a count, the way `(afw)` Stage 4 fixed backup, or a journal, the
  way migrate records intent before it acts. The first is cheaper; the second is what makes a
  half-applied run resumable rather than merely reported.

  ## ⚠ CORRECTED 2026-08-25 (P74), BY REPRODUCTION

  **What survives**: the behaviour. Ten decisions with a failure on #7 leave six committed, four
  never attempted, and all four run tables empty with no record file.

  **What was wrong**: the trigger, and the rank.

  * The reproduction poisoned `confirmed_days` with a duplicate day. **No caller can.** Checked:
    zero references to `confirmed_days` outside `trip_review.py`; `service/trips.py:apply_event_review_names` builds
    `TripDecision(card.trip, name)` positionally, so days come from `proposal.days`, a `Mapping`.
    The reachable trigger is a cross-process race, which is **`(ahk)`**.
  * It is a **reporting** defect. The catalog stays consistent; the half-state is discoverable
    through `ExistingNames`; **a re-run converges** (proved: a second apply named the remaining
    four, the first six taking `update_trip_days`); and the session survives, because
    `discard_session` runs only at `server.py:create_app.events_apply`.
  * The user is told the save **failed** while six succeeded - the inverse of `(afa)`, and the
    **safe** direction. **So it ranks below `(abm)`-shaped defects**, not above `(ahi)`/`(ahj)`.

  **The fix shape**: `(afw)` Stage 4's skip-count-name - a verdict per decision, counted and
  named, batch finished. **Not a journal**: a re-run converges, so there is nothing to resume.
  **Not a run record**: whether a catalog-only naming is *"a run that changes the library"* is
  `(ahi)`/`(agm)`'s question.
