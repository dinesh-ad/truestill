# (ahv) RESTORE CANNOT CREATE AN EVENT, ONLY RENAME ONE - AND IT BLAMES THE PHOTOS.

*Body of backlog entry `(ahv)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahv) RESTORE CANNOT CREATE AN EVENT, ONLY RENAME ONE - AND IT BLAMES THE PHOTOS.** Filed
  2026-08-26 (P103).
  **Every event name is lost after a catalog rebuild, and the reason the product gives is false.**

  ## MEASURED

  353 files, one trip and three events named through the app's HTTP routes, drive document
  written, catalog moved aside, library rebuilt by re-organize, then `truestill restore <drive>`:

  ```
       1  drive
       2  settings
       1  trips
    ! event 'Morning Market' does not match anything here - its photos have changed,
      so its name is reported rather than guessed at.
    ! event 'Temple Visit'   ... (same)
    ! event 'Rooftop Nine'   ... (same)
  ```

  **Trips came back. All three event names were lost.**

  ## THE STATED REASON IS FALSE, AND THAT IS THE WORSE HALF

  The photos had **not** changed. Same 353 files, byte-identical, and the rebuild put all 353 in
  `Camera` - `(ahr)`'s fix holds on this corpus. Re-proposing the same clusters on the rebuilt
  catalog produced signatures **identical to the document's**: `562ed6c8291b`, `f41e03ca6184`,
  `51aee3db0d41`, all three.

  🔑 **So clustering IS idempotent and the signature IS stable.** The data needed to restore was
  present and correct. What defeats it is the order of operations, not drift.

  ## THE MECHANISM

  `apply_decisions` looks the event up by signature and, finding nothing, reports it:
  `decisions.py:526-531`. After a rebuild the `events` table is **empty** - `record_event`
  (`catalog.py:2703`) runs only when a human names a proposed cluster - so **every** name lands in
  `unmatched`, whatever the photos did.

  Contrast trips, which restore unconditionally because `_apply_trips` (`decisions.py:442`)
  **creates** them from the days the document carries, and `trip_days.day` is a primary key, so a
  day list is an identity rather than a hint. Events carry a `signature` and no members
  (`decisions.py:601-604`) - the document has no material to create from.

  ⚠ **A category flip would break it too, and could not be reached to prove it.** The events query
  tests timeline membership (`camera_copies_for_events`, `catalog.py:1327`, via
  `catalog.timeline_label_sql`), so a label flipped **into a side bin** removes a file from the
  cluster and changes the signature (`events.py:187-190`). ⚠ **This paragraph said the query
  filters `f.category = 'Camera'` until 2026-08-26** - true when the entry was filed and replaced
  by `(ahw)` the same day, with the sense INVERTED: the test is now `category NOT IN (<side
  bins>)`, so an unrecognised label is on the timeline rather than off it. **The trap survives the
  correction and its shape narrows** - only a flip into a side bin can now drop a member, not any
  flip at all. Attempted: re-organizing an
  already-organized library with `--by-device` **deduped to 0 files and never re-categorised**, so
  this path is currently unreachable and is recorded as a latent trap rather than a live defect.
  `min_files` (default 8, `events.py:95`) is a second-order amplifier: one lost member can drop a
  cluster below the floor.

  ## WHAT THIS IS NOT

  **Not a rate.** One constructed corpus, drawn from one folder of one library. It proves the
  mechanism end to end and says nothing about how often a user meets it - though the trigger is a
  catalog rebuild, so the rate is the rate of catalog loss, not of any drift.

  ## ⚠ DATED NOTE - 2026-08-26 (P106a): THE TWO-STEP IS MEASURED NOT TO WORK

  Re-running review and restoring again does **not** bring the names back, and reaching for it
  makes things worse. The rebuild publishes a decisions document to the recovery drive, so the
  names typed during recovery are **newer** than the originals and outrank them permanently. That
  is `(ahz)`, and it is why this entry's remedies must not mention a two-step.

  Measured the same day: the premise below still holds exactly - same three signatures, same
  dropped names. ⚠ **NOT the same sentence, from 2026-08-26**: `(aia)` replaced it, and the
  clause reading *"same sentence"* is corrected here rather than left to mislead a reader who
  greps for it. `grep -rn "photos have changed" packages/` now returns exactly one hit - a comment
  in `decisions.py` recording what the old sentence said.

  ## THE OPTIONS - A RULING, NOT A FIX

  1. **Carry members in the document** so restore can create the event, as trips do. Widens the
     document; the parser already round-trips an entry carrying `members` (`decisions.py:162`), so
     the shape is not new.
  2. **Re-propose before applying**, and match names to freshly clustered signatures.
  3. ~~**Say the true reason.**~~ **SHIPPED 2026-08-26 in `4981d3e` as `(aia)`.** It was the
     cheapest and independent of the other two: distinguish *"no event here has that signature
     because this catalog holds no events at all"* from *"the photos changed"*, where one sentence
     covered both and only one is ever true after a rebuild. `RestoreNote` now has two arms chosen
     by `unmatched_events_note` (`decisions.py:826`) on `ApplyReport.events_here` -
     `NO_EVENTS_HERE` and `NO_SUCH_GROUP`.

  ⚠ **Option 3 was not optional and is now done. THE ENTRY STAYS OPEN ON OPTIONS 1 AND 2**, and
  the distinction matters: a user told their photos changed goes looking for a problem that does
  not exist, and that is fixed - but **saying the true reason does not put the name back**. The
  create is the remaining half, and it is the data-loss half.

  ## RELATED

  `(ahu)` (when the document is never written at all), `(ahs)` (the file inventory, a different
  gap), `(ahr)`, `(acg)`, [`soak-six-record.md`](../../soak-six-record.md).
