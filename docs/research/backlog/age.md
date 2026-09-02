# (age) `(aek)`'s SILENT DIRECTION SURVIVES INSIDE `(aek)`'s OWN FIX.

*Body of backlog entry `(age)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(age)** Recorded 2026-08-23, found while investigating `(aft)`. **Filed, not built** - it is a
  preview, and `(aft)` was a watcher.

  ## The measurement was fixed; the report was not

  `(aek)` removed the `0`-means-two-things conflation from `filesystem.preflight_destination`, and
  the comment states the rule (`filesystem.py:preflight_destination`). The repair is real:

  ```python
  free: int | None
  try:
      free = shutil.disk_usage(_nearest_existing(destination)).free
  except OSError:
      free = None
  ```

  **Then it is thrown away one line later** (`filesystem.py:preflight_destination`):

  ```python
  free_bytes=need if free is None else free,
  ```

  ⚠ *That block is quoted verbatim, and holding it that way needed a change to the build.*
  `make check` rewrote it to `free_bytes = (need if free is None else free,)` - a tuple assignment
  the file does not contain - because ruff formats Python inside Markdown. `(agf)`, found here.

  `DestinationPreflight` (`filesystem.py:DestinationPreflight`) has **no field carrying "this was not
  measured"**. So an unmeasurable destination becomes *exactly enough*, `may_proceed` is `True`,
  and `cli._print_preflight` (`cli.py:_print_preflight`) prints **nothing**.

  🔑 **The conflation was removed where it was MEASURED and reappeared where it is REPORTED.** The
  `int | None` lands, does its job for one expression, and is collapsed back into a number before
  anything can carry it to a person. That is what makes this its own letter rather than a note on
  `(aek)`: it is not an unfixed defect, it is a **fix that stops one line short of the surface**.

  ## ⚠ WHY THE BACKSTOP ARGUMENT DOES NOT COVER IT

  Someone will reach for `(aek)`'s own sentence, so it is answered here:

  > *"An unmeasurable destination must not be reported as full: it fails later, and louder, with
  > the real reason rather than a space figure nobody could obtain."* (`filesystem.py:preflight_destination`)

  **That is an argument about a RUN, and this is a PREVIEW.** A preview exists to say what will
  happen *before* it happens. A preview that reports the destination is fine when nothing was
  measured has failed at the one thing it is for. **The later failure is not its backstop - it is
  what the preview was meant to prevent.**

  The `(aft)` half is the mirror image and shows the pair clearly: there, the unmeasured value was
  **loud and wrong** (a stop). Here it is **quiet and wrong** (a reassurance). `(aft)`'s entry
  already names that asymmetry; this is the other end of it.

  ## ⚠ THE ARCHIVE PATH DOES NOT SHARE IT (corrected 2026-09-02, P186)

  This said the opposite from 2026-08-23. `archive_set.py:space_for` calls `shutil.disk_usage`
  with **no** `except OSError`, so an unmeasurable destination raises out of
  `archive_ingest.py:precheck_archives` rather than reading as *"enough room"*. Loud, not quiet.
  The organize-preview half above is exactly as stated; `(agg)`'s drive lock is unaffected.

  ## NOT DECIDED

  - Whether `DestinationPreflight` gains a field (`free_measured: bool`, or `free_bytes: int |
    None` carried through) or whether the preview simply declines to state a space line it could
    not obtain. The second is smaller and matches §9's *named, never counted*.
  - Whether `Destination.preflight`'s default (`destinations/base.py:Destination.facts`), which returns
    `free_bytes=need` as a deliberate stand-down for remotes, should be distinguishable from a
    failed local measurement. Today they are the same number for different reasons - which is this
    entry's own shape, one layer down.

  ## RELATED

  `(aek)` (the fix this sits inside), `(aft)` (the same conflation on the watcher axis, shipped
  2026-08-23, and the investigation that found this).
