# (ahc) THE MIGRATE SCREENS PAINTED A STOPPED RUN AS A FINISHED ONE.

*Body of backlog entry `(ahc)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared between the two.*

- **(ahc) THE MIGRATE SCREENS PAINTED A STOPPED RUN AS A FINISHED ONE.** Found 2026-08-25 by
  P61, while verifying `(agm)`'s premise rather than by looking for it.

  ## WHAT WAS WRONG

  `(agm)` D1 taught `MigrationOutcome.stopped` to be read, and scoped itself in its own commit
  message: *"D1 and D2 only. No run record, no bake, no app.js - `(agm)` stays open."* Two of the
  three surfaces landed. The third did not, and nothing said so on the screen.

  - `service/migrate.py` flattened the stop faithfully into `MigrationStopPayload`.
  - `static/app.js` read **neither** `summary.stopped` nor, on the forward path, `summary.refused`.
  - **Only a user cancel sets the job's cancel flag** (`jobs.py` derives the status from
    `job.cancel.is_set()`), so every other stop arrived with status `"done"`.

  ⚠ **So a `GROUND_MOVED` or `COULD_NOT_CONTINUE` stop was painted `Moved N files.`** - a disk
  filling, a device changing under the run, or a destination that does not store what it is
  handed, all reported as a completed migration. On the one screen that rewrites every byte of
  the library. `IMPLEMENTATION_STANDARDS.md` §9 never-silent, and `(afa)`/`(abm)`'s shape exactly:
  the payload is computed and the surface drops it.

  ## THE RULING: ONE WORDING HOME

  The CLI derived the cancel-versus-fault split inline as `kind is CANCELLED`. Adding a second
  derivation in JavaScript would have made **three** homes for one decision, in two languages,
  with nothing to make them agree. `test_the_rearrange_card_name.py` records what that costs: one
  card name retyped in four places, drifted, and the feature became unfindable.

  So `truestill_core.migrate.STOP_WORDING` maps each kind to a `StopWording(headline, fault)`.
  The CLI reads it; the service puts `headline` and `fault` **in the payload**; `app.js` renders
  text it was handed and maps no kinds of its own. A table rather than a derivation, and indexed
  rather than `.get()`, so a member added tomorrow raises `KeyError` instead of being worded by
  an `else` nobody wrote for it - the reasoning `test_migrate_survives_one_bad_file._WORDING`
  already gives for its own.

  ## BOTH DIRECTIONS, AND EACH WAS MISSING A DIFFERENT HALF

  | | `stopped` | `refused` |
  |---|---|---|
  | forward apply | dropped | **dropped** |
  | undo apply | dropped | shown since it was written |

  The payload shape is identical, so the renderer was **reused rather than rewritten**. It was
  called `undoRefusalList` and was never undo's; it is `refusalList` now.

  ## TWO DECLARATIONS OF ONE FACT

  The job's cancel flag and `summary.stopped` both know a cancelled run was cancelled. **The
  payload wins**: the flag now only chooses the fallback sentence for a run that recorded no stop.
  A preview never records one - `run_migration` returns before the field can be set - and the CLI
  cannot produce a cancel at all, because it passes no `cancel` event.

  ## WHAT THIS IS NOT

  **Not the run record.** That is `(agm)`, still open and now smaller than its title. P61 measured
  its cost against real `~/TruestillLibrary` path lengths rather than carrying `afw.md`'s 36.9 MiB
  forward: **271 B** per migrate failure entry raw, **52 B** compressed, against
  `DETAIL_BUDGET_BYTES` of 64 MiB. Building a record while the screen still said *"Moved N files"*
  would have written a file nobody reads about a stop the user was never told about.

  ## WHAT THE TEST CANNOT PROVE

  Pinned by reading `app.js` as text, per `test_the_rearrange_card_name.py`, because the browser
  lane is not part of the routine loop. That proves the handlers consult the field and that the
  script maps no kinds of its own. **It does not prove the banner is visible** - that is the
  browser lane's question, and it is stated here rather than implied.
