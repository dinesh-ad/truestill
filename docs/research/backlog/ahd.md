# (ahd) THE BAKE IS APP-ONLY, AND STEP 1 OF THE FIX IS DONE: THE ENGINE IS IN CORE.

*Body of backlog entry `(ahd)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahd) THE BAKE IS APP-ONLY, AND STEP 1 OF THE FIX IS DONE: THE ENGINE IS IN CORE.**
  Ruled by P64 on 2026-08-25; step 1 built the same day. ⚠ **CLOSED 2026-08-25: step 2 shipped the same day.** The text below is kept as it was written, because it is the ruling and the inheritance rather than a status.

  ## WHY IT IS A GAP AND NOT A DECISION

  `BACKLOG.md`'s *App-surface deferrals* register exists precisely to stop this being implicit -
  its own words: *"an undocumented single-surface contract is indistinguishable from drift."* It
  records `confirm_file_date` as app-only, **and does not contain the bake**.

  Everything else confirms the silence: [`date-provenance-design.md`](../../date-provenance-design.md)
  is a frozen **PROGRAM COMPLETE** whose §4 is *"the three surfaces, and they are one screen"* and
  whose *"not smuggled in"* list names **four** exclusions, none of them the CLI; the founding
  commit is `feat(app)`; and [`cli-app-parity.md`](../../cli-app-parity.md) - the document that
  answers *"what is actually missing"* - has **zero** mentions of bake under any name.

  ## WHY APP-ONLY IS NOT DEFENSIBLE HERE

  The recorded reason for app-only is **review-shaped**. The bake is not: the review happened at
  confirm time, and the bake is batch execution of decisions already made - the shape every CLI
  mutating command already has.

  It is also **the most irreversible operation in the product**. `exif.py`'s `_WRITE_FLAGS` are
  `("-overwrite_original", "-m")` and **no sidecar is kept**. Organize moves and `undo-organize`
  reverses it; migrate journals the whole plan before touching disk; clean-empty reports and never
  removes. The bake overwrites bytes inside a photograph and the date it carried is gone.

  ## STEP 1 - DONE. WHAT MOVED, AND WHAT COULD NOT

  ⚠ **The three functions named in the ruling could not move intact.** `bake_run`, `bake_preview`
  and `bake_preconditions` all return `DriveUnavailablePayload`, which carries `suggested_root`
  and `can_register` - **a button on a screen**. Moving them whole would have put an app affordance
  in core, the direction `IMPLEMENTATION_STANDARDS.md` §2 forbids.

  So the line is the one `drive.drive_identity` already draws: **core computes and returns a core
  value; the app wraps it into its payload.**

  | in `truestill_core.bake` | staying in `truestill_app.service.bake` |
  |---|---|
  | the write loop, `bake_confirmed_dates` | `BakeSummary`, `BakePreview`, `BakeRefusal` |
  | `CONFIRM_WORD`, `unconfirmed_reason` | the `DriveUnavailablePayload` mapping |
  | `IRREVERSIBLE_NOTE`, `VIDEO_EXCLUSION_REASON` | `bake_run` / `bake_preview` / `bake_preconditions` |
  | `completeness_line`, `migration_unfinished_message` | |
  | `is_video`, `migration_unfinished`, `BakeOutcome` | |

  The test for each row was **would a CLI need it**. A sentence spelled twice in two packages is
  the drift `MIGRATE_CARD_NAME` already cost once, so the shared copy moved with the engine.

  ## STEP 2 - OPEN. WHAT IT INHERITS

  **Helpers that already exist**, named so step 2 does not re-derive them: `_typed_confirmation`
  (the `reclaim` shape), an `--apply` gate, a `"bake": "path"` row in `_LOCKS_DRIVE_AT` after
  which `_run_holding_the_drive` takes the lock automatically, and `_progress_printer`, which
  already matches the `ProgressCallback` the engine takes. Cancel is a `threading.Event`.

  ⚠ **THE ONE REAL CONSTRAINT: there is no CLI way to CONFIRM a date.** Checked - zero hits for
  `date_confirmations|confirmations_to_bake|confirm_file_date` anywhere in `truestill-cli`. So a
  CLI bake writes only confirmations made in the app, or restored from a drive's decisions
  document by `truestill restore`. That makes it a **companion** to the review screen rather than
  a standalone path - which is what the deferral register already says the rescue should stay. A
  constraint, not an objection, and the reason it is written here is that step 2 would otherwise
  find it after writing the subcommand.

  ## NOT THIS ENTRY

  **Bake is not the only app-only mutating run.** `backup` (`service/backup.py`, referenced only
  inside `truestill-app`) and `trip apply` (`service/trips.py`'s `apply_event_review_names`) are
  too - established by enumerating every `mutating=True` route against the guarded subcommand
  list. Neither is in the deferral register. They need a row each or a CLI each; silence is not a
  decision. Also not this entry: `(agm)`, the bake's run record, which P64 ordered **after** the
  CLI so that two consumers shape it rather than one.
