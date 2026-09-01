# (ahk) THE NAMING ROUTE DOES A CHECK-THEN-INSERT WITH NO LOCK, AND `truestill restore` CAN RACE IT.

*Body of backlog entry `(ahk)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahk) THE NAMING ROUTE DOES A CHECK-THEN-INSERT WITH NO LOCK, AND `truestill restore` CAN RACE
  IT.** Filed 2026-08-25 (P74), while verifying `(ahh)` by reproduction. **Ranked above `(ahh)`**:
  that entry is how the collision is *reported*; this is the collision.

  ## THE WINDOW

  `commit_trips` reads `catalog.trip_for_day` for every day (`trip_review.py:commit_trips`) and then calls
  `create_trip` (`:378`). **Two transactions.** `BEGIN IMMEDIATE` serialises each of them and does
  nothing about the gap between them.

  The route around it holds nothing. `events_apply` (`server.py:create_app.events_propose`) is a plain handler: no
  `_start_drive_job`, no `jobs.claim`, no `lock_for`. ⚠ **Established by reading the handler, not
  by grepping three symbol names** - the handler's whole body is `sessions.get`, a
  `run_in_threadpool` call and a `JSONResponse`.

  Meanwhile `truestill restore` reaches `create_trip` through `decisions.py:reconcile_documents`, in another
  process, against the same catalog.

  ## REPRODUCED - AND WHAT THE REPRODUCTION IS NOT

  With a second real `Catalog` connection opened inside the window:

  ```
  RAISED IntegrityError: UNIQUE constraint failed: trip_days.day
  trips     : [(1, 'Restored')]
  trip_days : [('2024-05-01', 1)]
  -> the user's typed name 'Goa' is gone; the day belongs to 'Restored'.
  ```

  ⚠ **That forces the interleaving deterministically. It does not race two OS processes.** The
  window is reproduced; a collision in the wild is not. Said plainly because the alternative is
  promoting a read to a reproduction, which is the failure `(ahh)` was re-scoped for.

  ## THE TWIN PATH IS HARDENED AGAINST THE NEIGHBOURING SHAPE

  `decisions.py:ApplyReport`, verbatim:

  > `# Day -> the name of the trip holding it. Read once and kept in step as trips are created, so`
  > `# a document that names one day twice cannot make `create_trip` fail on the day primary key.`

  Someone met this failure mode and defended against it - **on the restore path, for the
  within-run duplicate**. ⚠ **And because it reads the claim map *once* up front,
  `apply_decisions` is if anything MORE exposed to the cross-process window than `commit_trips`,
  which at least re-reads per day.** Neither path defends against the other process.

  ## `(agu)`'s GUARD SEES THIS ROUTE AND ALLOWS IT

  `test_every_job_declares_whether_it_mutates.py` enumerates every route handler and classifies
  every bare service call. `apply_event_review_names` is entry **:256** -
  *"catalog rows; its own docstring: 'No files move'"*. So the guard is **not blind**; it permits
  this by rule, and its own comment names the class as a recorded gap:

  > *"catalog-ROW writers (serialized by SQLite itself plus the `(agp)` busy handling, and
  > deliberately outside drive locks - the gap `(aaw)` recorded and `(adt)`'s close split into
  > residue letters)"*

  What the guard reds is a **deleting** call outside the exclusion (`_MUST_HOLD_THE_EXCLUSION`,
  currently `{"clean_empty_apply"}`). This one inserts, so nothing fires.

  ## CENSUS: 9 UNLOCKED CATALOG-WRITING ROUTES, 8 SAFE BY CONSTRUCTION

  | route service | shape | exposed? |
  |---|---|---|
  | `set_organize_mode`, `set_sidebar_collapsed`, `set_text_size`, `set_library_root`, `set_layout`, `set_event_settings`, `set_everyday_day_settings` | single-key settings upsert | no |
  | `confirm_file_date` | one `_tx`, `INSERT ... ON CONFLICT(sha256) DO UPDATE` plus the `file_copies` update | no |
  | **`apply_event_review_names`** | **read in one transaction, write in another** | **yes** |

  **It is the only one whose correctness depends on a read in one transaction and a write in
  another.** The other eight are last-write-wins or atomic upserts, where a concurrent writer
  changes the outcome and never the integrity.

  ## ⚠ WHAT THE FIX IS NOT

  **Fixing `(ahh)`'s reporting does not fix this.** A route that reports a collision cleanly is
  still a route that permits one, and the harm here is the **user's typed name being lost** -
  which no amount of good reporting returns.

  The shapes available are the ones the product already uses: `jobs.claim`, which is what `(agu)`
  used for exactly this reason (*"the exclusion half of `jobs.start` ... because apply's screen
  contract is a synchronous result and the lock, not the wrapper, was the requirement"*); or
  closing the window in SQL so the check and the insert are one statement. **Which is right is
  this entry's ruling**, and `(agu)`'s precedent is the strongest argument for the first.

  ## RELATED BUT NOT THIS

  `(ads)` records that the catalog's concurrency **model** was inherited rather than chosen, and
  `(adn)` that nothing stops two processes holding one catalog. **Neither covers an
  application-level check-then-insert**, which no journal mode fixes: WAL would let the two
  writers proceed and the constraint would still refuse.
