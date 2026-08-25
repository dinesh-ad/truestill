# (ahh) NAMING TRIPS ABORTS MID-WAY AND RECORDS NOTHING ABOUT BEING INCOMPLETE.

*Body of backlog entry `(ahh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahh) NAMING TRIPS ABORTS MID-WAY AND RECORDS NOTHING ABOUT BEING INCOMPLETE.** Filed
  2026-08-25 (P72), found while ruling `(ahf)`'s last surface rather than by looking for it.

  ## THE DEFECT

  `commit_trips` (`trip_review.py:363-392`) iterates the reviewed decisions and **catches
  nothing**. Each catalog write is atomic on its own through `Catalog._tx` - `create_trip` writes
  `trips` and `trip_days` in one transaction - but that is **per call, not per apply**. A raise on
  the seventh trip therefore leaves the first six committed, and **nothing anywhere records that
  the run did not finish**.

  It is not hypothetical: `create_trip`'s own docstring advertises the `sqlite3.IntegrityError`
  that would do it (`catalog.py:2745`). `commit_catalog` (`event_review.py:162-190`) has the same
  shape for events.

  ## WHY IT CANNOT BE CLEANED UP AFTERWARDS

  ⚠ **Checked rather than assumed**: there is no `delete_trip` and no `unname` in the tree. The
  only `DELETE FROM trips|events|trip_days` anywhere is inside `update_trip_days`
  (`catalog.py:2781`), which deletes a trip's own day rows only to reinsert them. Nothing writes
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
