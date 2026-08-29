# (ahv) RESTORE CANNOT CREATE AN EVENT, ONLY RENAME ONE - AND IT BLAMES THE PHOTOS.

*Body of entry `(ahv)`, **shipped 2026-08-29** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md). The trip half of the recovery story is **not** this entry's: `(ahz)` owns it, and still does.*

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

  Contrast trips, which restore unconditionally because `_apply_trips` (`decisions.py:897`)
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

  ## ⚠ STAGE 1 SHIPPED 2026-08-29 (P125) - A LIVE DEFECT IN ITS OWN RIGHT, NOT SCAFFOLDING

  **The floor the user set was ignored on re-import.** `event_review.propose` and
  `propose_from_catalog` clustered at the hard default of 8 while `events.min_files` sat in the
  catalog - so a user who lowered the floor and named a six-file event had it **silently skipped
  by `_reapply_named_events` on every subsequent import**: the function returns its input
  unchanged when nothing proposes, which at its call site is indistinguishable from "no events
  recur here". Found by P124's call-graph pass while planning option 2, fixed before it:
  `propose` now **requires** `min_files` (a default here would repeat the defect one layer out),
  and the three catalog-owning entry points - `propose_from_catalog`, `run_event_stage`,
  `_reapply_named_events` - read `EventSettings.from_catalog` themselves. The app's trip-review
  path already did (`service/trips.py`), which is how one surface honoured the floor while the
  others dropped it: one concept, read in one place and defaulted in three.
  **`_reapply_named_events` gained its first direct test** with this
  (`test_reapply_honours_the_event_floor.py`) - call-site-only coverage could never catch a
  silent no-op that needs a lowered floor plus a below-default named event to exist. Census run
  with the fix: `heavy_days_for_organize` reads its threshold from the catalog and every
  production caller threads `resolve_scheme` - no second instance of the bypass; the residual
  same-shape risk is the `scheme=DEFAULT_SCHEME` parameter defaults, unexercised in production
  today. Matters for option 2: restore-side re-clustering must use the restored document's
  floor, which this stage makes reachable.

  ## ⚠ STAGE 2 SHIPPED 2026-08-29 (P126) - RESTORE CREATES THE EVENT IT CAN MATCH

  **Option 2, built.** `apply_decisions` now re-clusters this catalog's own timeline
  (`_restorable_clusters`: `propose_from_catalog` over every registered drive) and, on an
  `event_by_signature` miss whose signature a freshly proposed cluster DOES carry, creates the
  row from the document's name and the cluster's members - `record_event` then `set_event_id`,
  both unreachable in preview. The signature is a hash over member sha256s, so the match IS the
  membership; nothing is invented, and a signature matching neither table nor clusters falls to
  `(aia)`'s honest arms unchanged - the code still cannot tell a shifted membership from a group
  never named here, and still does not claim to.
  🔑 **The floor comes from the DOCUMENT, catalog fallback** (`_DocumentFirstSettings`) - stage
  1's thread mattered here first: the preview pass runs before any setting is written, so
  reading the catalog would honour the pre-restore floor on the one run where the document is
  authoritative, and would let the two passes propose different clusters. Where the create meets
  `(ahz)`'s named-root authority: the create consumes the MERGED row, so the winning name lands
  by construction - pinned by
  `test_restore_creates_the_event_it_can_match.py::test_the_created_event_takes_the_name_the_authority_rule_chose`.
  `ApplyReport.created_events` names each recreated event (`EVENT_CREATED`, non-actionable,
  never in `withheld_count`); idempotent by the existing `ON CONFLICT(signature)`. Proven by
  three control-first mutations: create skipped, links dropped, floor read from the catalog.
  **What remains of this entry is stage 3** - the measured 353-file sequence end to end as a
  regression test, re-running `(ahz)`'s five steps.

  ## ⚠ STAGE 3 SHIPPED 2026-08-29 (P127) - THE SEQUENCE RE-RUN, AND THE ENTRY CLOSES

  **The five steps were re-run end to end on the same corpus** (`Input/IV Bangalore`, copy mode,
  1,062 organizable files - ⚠ the *353* recorded above was a subset used that day; the three
  event signatures came back **byte-identical** to the recorded `562ed6c8291b`, `f41e03ca6184`,
  `51aee3db0d41`, which is what makes the two runs comparable). Step 3, which this entry was
  filed on:

  ```
       1  drive
       3  events
       1  trips
    - event 'Morning Market' was re-created: this library's photos still form its exact group.
    - event 'Temple Visit'   ... (same)
    - event 'Rooftop Nine'   ... (same)
    - 5 decision(s) would come back, 0 would not.
  ```

  All three names return **at step 3**, with 55, 26 and 9 photographs linked under them, and the
  `-` marker is correct: nothing is being asked of the reader. Step 5, which `(ahz)` measured as
  *"3 events on dest were older and were not used"*, now reads **"nothing this catalog does not
  already have"** - and step 4's placeholder re-naming cannot take at all, because
  `commit_catalog` reuses the row an existing signature already names. **The loop `(ahz)` found
  is not merely broken but unreachable for events**: there is no longer a step 3 failure to send
  a user into step 4.

  The regression test is `test_a_lost_catalog_gets_its_names_back.py`, which writes a real
  document to a drive root and reads it back. It fails on stage 1's tree (`6ae5219`) with
  `assert set() == {'Morning Market', 'Temple Visit'}` - the names never returning - and its two
  arms are deliberately in one file, because a test proving only the create would pass a fix
  that created indiscriminately. Two mutations, dying **differently**: reverting the create
  fails on the names, dropping `set_event_id` fails on the photographs - which is this entry's
  own warning, a name on screen with no folder behind it.

  ## ⚠ THE RECOVERY STORY, END TO END - WHAT COMES BACK AND WHAT DOES NOT

  **A user loses their catalog and re-organizes to rebuild it. Back: every photograph, its
  category and date, every trip, every event name with its photographs under it, every
  date correction, and the settings. Not back: a trip's NAME where the rebuilt catalog already
  minted a different one for those days** - that is `(ahz)`'s residual, `rename_trip` does not
  exist, and the user is told loudly rather than silently. **Also not back: an event whose
  photographs no longer form the same group** - reported by name as unmatched, never guessed at,
  its name still safe in the drive's document.

  ⚠ **The latent trap this entry recorded is now HONEST rather than silent.** A category flip
  into a side bin drops a member and changes the signature, so the name has nowhere to land -
  but the run now says so per event instead of misfiling. The `min_files` cliff is the same
  shape: 56 clusters per drive sit at 8-9 members (measured P124), so a lost member can drop one
  below the floor. Both end in the honest arm, and neither can invent a group.

  ## THE OPTIONS - A RULING, NOT A FIX

  1. **Carry members in the document** so restore can create the event, as trips do. Widens the
     document; the parser already round-trips an entry carrying `members` (`decisions.py:162`), so
     the shape is not new.
  2. **Re-propose before applying**, and match names to freshly clustered signatures.
  3. ~~**Say the true reason.**~~ **SHIPPED 2026-08-26 in `4981d3e` as `(aia)`.** It was the
     cheapest and independent of the other two: distinguish *"no event here has that signature
     because this catalog holds no events at all"* from *"the photos changed"*, where one sentence
     covered both and only one is ever true after a rebuild. `RestoreNote` now has two arms chosen
     by `unmatched_events_note` (`decisions.py:850`) on `ApplyReport.events_here` -
     `NO_EVENTS_HERE` and `NO_SUCH_GROUP`.

  ⚠ **Option 3 was not optional and is now done. THE ENTRY STAYS OPEN ON OPTIONS 1 AND 2**, and
  the distinction matters: a user told their photos changed goes looking for a problem that does
  not exist, and that is fixed - but **saying the true reason does not put the name back**. The
  create is the remaining half, and it is the data-loss half.

  ## RELATED

  `(ahu)` (when the document is never written at all), `(ahs)` (the file inventory, a different
  gap), `(ahr)`, `(acg)`, [`soak-six-record.md`](../../soak-six-record.md).
