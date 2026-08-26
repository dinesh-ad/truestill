# (ahx) `not_applied` REACHES NO CONSUMER, SO A RESTORE NEVER SAYS THE ALBUMS WERE DROPPED.

*Body of entry `(ahx)`, **widened and shipped 2026-08-26** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(ahx) `not_applied` REACHES NO CONSUMER, SO A RESTORE NEVER SAYS THE ALBUMS WERE DROPPED.**
  Filed 2026-08-26 (P103). The
  computed-and-read-by-nobody class, on the restore path.

  ## THE FIELD, AND THE DOCSTRING IT CONTRADICTS

  `apply_decisions` returns `not_applied=("albums",)` whenever a document carries albums
  (`decisions.py:590`); the field is declared at `decisions.py:435`.

  `_print_restore_plan` (`cli.py:1440`) prints `unmatched_events`, `awaiting_content`,
  `already_newer_locally`, `superseded` and `undated` - **and not this one**. Its own docstring, at
  `cli.py:1441-1444`, promises *"What would come back, and - the half that is easy to leave out -
  what would not."*

  ⚠ **So a user restoring is never told the albums section was discarded**, on either surface:
  grep for `not_applied` across `packages/` returns four hits total - the declaration
  (`decisions.py:435`), the write (`decisions.py:590`), one documentation line, and a test whose
  name collides and is about date corrections. **No test asserts it, so deleting `decisions.py:590`
  breaks nothing.**

  ## ⚠ THE CENSUS WAS ONE THIRD COMPLETE - CORRECTED AND WIDENED 2026-08-26 (P107)

  `not_applied` is **one of three**. `conflicting_trips` (`decisions.py:428`) and
  `trips_without_days` (`decisions.py:431`) were computed by core and printed by nobody either,
  and `_print_restore_plan`'s docstring promised *"the half that is easy to leave out"* while
  dropping all three. A fourth sat beside them: the apply-time report was computed and discarded.

  🔑 **Why the first census missed two, and it is the shape this repo keeps meeting**: it searched
  for the field it already knew about instead of enumerating what the report carries. **A search
  shaped like the known instance cannot see the unknown ones** - `(ahu)`'s grep for `set_setting(`
  was blind to `set_local_setting(`, `(ahw)`'s grep for `TIMELINE_RULES` cannot see a string inside
  SQL, and `(ahz)` found a guard keyed by name against a merge keyed by day set.

  ## THIS IS THE INDUSTRY NORM, WHICH IS THE ARGUMENT FOR THE LOOP

  Weighed, not re-derived. **Every one of these is a report that names what it did and stays silent
  about what it did not, and none was fixed by adding one more field:**

  | product | what it says |
  |---|---|
  | IBM `RSTOBJ` | restores 74 of 75 and reports *"74 restored"*. IBM's own manual: *"You are not notified that 1 object was not restored."* **Silent omission, documented as expected** |
  | Veeam VBO | the explorer says *"1 skipped, 1 restored"* while the job log **and the API** say *"was restored successfully"* for **both** - two surfaces disagreeing, and the trusted one wrong |
  | IBM Spectrum Protect Plus | APAR **IT31203**: a partial-successful backup does not report the missing objects when restoring from it |
  | Adobe Creative Cloud | twice: a green *"successfully restored"* for files that never appear |

  ⚠ **And the inverse, taken from IBM's own remedy**: its restore messages report both halves as a
  **pair** - `CPF3773` *"&1 objects restored. &2 not restored"*, and `CPF3839`/`CPF9003` the same
  shape. That is what shipped here: **never a count of successes without the count of omissions
  beside it, in the same sentence, zeroes included** - so silence is structurally impossible rather
  than merely unlikely. A zero the reader sees is the difference between *"nothing was left out"*
  and *"nobody looked"*.

  ## HOW IT SHIPPED - THE LOOP, NOT THE THREE LINES

  `_print_omissions` walks `dataclasses.fields(ApplyReport)` and indexes `REPORT_FIELD_NOTE`;
  `REPORT_FIELD_EXCEPTIONS` declares the three fields a loop cannot render **with the reason for
  each** - `applied` is the restored half rendered as a table, `unmatched_events` needs `(aia)`'s
  two-sentence chooser, and `events_here` is a discriminator that is never shown alone. **A
  declared exception is a decision; an unhandled field is the shape that regrows.**

  `test_every_report_field_reaches_the_reader` fails at import for a field in neither table.

  ⚠ **The docstring is kept as written rather than softened**, because the loop makes its promise
  true: it can no longer name five fields and miss three.

  ## THE APPLY-TIME REPORT - MEASURED, AND THE ANSWER IS A NULL

  `cli.py` computed `apply_documents(..., apply=True)` and discarded it, so a user saw the
  preview's numbers and then *"Restored into X."* with nothing behind it. **Measured: the two
  reports are IDENTICAL in the ordinary case** - `preview == applied` on a document exercising
  every field. So this is **not** a corrected number.

  🔑 What the measurement did show: **the omissions are unchanged by applying.** The same event,
  the same dayless trip and the same albums section are still withheld after `--apply`, and were
  never said at the moment they became permanent. A re-preview afterwards reports `applied={}`,
  so the numbers only ever answered *"what would change"* and nobody was told what did.

  ## WHY THE ALBUMS ARE DROPPED IS RECORDED - THIS IS NOT THAT

  The write-only behaviour is **intended**, ruled at [`acg.md`](acg.md) lines 9-11, which names
  `not_applied` exactly. This entry is not a request to restore albums; it is that the product
  computes a fact about a user's data and shows it to nobody.

  ⚠ **And `(acg)`'s justifying premise is false** - corrected in that entry the same day. It reads
  *"the albums tables are empty today"*; `takeout.py:244` -> `cli.py:2484` builds
  `IngestContext.albums` **unconditionally** on every ingest -> `organizer.py:2121` ->
  `catalog.py:3113`. `--map-albums` does not gate it. Every Takeout user with album folders has
  album names written to their drive on every save and silently discarded on every restore, which
  is what makes the missing sentence matter rather than being tidy-up.

  ## THE ASYMMETRY NOTHING RULES ON

  `decisions.py:863` puts `albums` in `_LOSS_KEYS`, so an album name is **protected from being
  overwritten on the drive** while still never being readable back into a catalog. Written,
  guarded against loss, and unreadable. No document rules on that combination.

  ## `(ahz)`'S VALUE HALF IS NOT CLOSED HERE

  `(ahz)` records that `Superseded` carries `section, drive_label, count, reason` and **no values**,
  so no surface can name *which* trip or event was lost. **That stays `(ahz)`'s**, and the
  distinction is not a technicality: this entry changed what the printer LOOPS OVER, and that is a
  change to what the merge RECORDS. ⚠ **If `Superseded` gained the values, this loop's shape is
  what would print them** - the work is in `_merge_section`, not here.

  ## THE FIX

  One line in `_print_restore_plan`, and the app's restore payload alongside it - the same shape
  `(abm)` used for `unreadable_dirs`. **Loop the report's own fields rather than naming five**, or
  the sixth omission repeats this one.

  ## RELATED

  `(acg)` (the ruling and its corrected premise), `(abm)`, `(ahl)`, `(ahn)`,
  [`decisions-on-drive-research.md`](../../decisions-on-drive-research.md).
