# (akg) THE IMPORT SCREEN DEDUPS AGAINST THE WHOLE CATALOG, NOT THE DESTINATION, AND WHETHER THAT IS A DEFECT IS UNESTABLISHED.

*Body of entry `(akg)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(akg)** Filed 2026-09-05 while closing the organize half. **No work attached and nothing
  investigated**: this records the shape so the next reader does not rediscover it.

  ## WHAT IS KNOWN

  `service/takeout.py` calls `organizer.resolve` twice - in `ingest_preview` and in
  `ingest_preview_run` - and neither passes `on_destination`. `organizer._scope_to_destination`
  documents that value as three-valued: `None` is the catalog-global answer, `{}` a local
  destination with no marker, populated the copies `file_copies` records on this drive. With
  `None`, a file the catalog has seen on any drive is an exact duplicate, so an import into a
  fresh second drive skips it. That is `(aei)` - *"organizing into a second drive skipped every
  file the first drive already held"* - which was fixed for `organize` on the run
  (`service/organize.py`, `_scope_to_marker`) and on the preview on 2026-09-05
  (`test_the_promise_holds_for_a_fresh_second_destination`).

  On Import the preview and the run agree with each other, so no promise is broken and the
  promise test cannot see it. `(aei)`'s tests - `test_a_second_destination_receives_the_files.py`,
  `test_dedup_scope_survives_the_registration_move.py` - drive `organize` only.

  ## WHAT IS NOT

  Whether Import means *"bring these into this destination"* - in which case the second drive
  should receive the files and this is `(aei)` on a third surface - or *"bring these into the
  library"* - in which case skipping what the library already holds is the point, and the
  destination is where new content lands. The CLI's `ingest` command is the reference for that
  semantics and was not read. Nothing here decides it.
