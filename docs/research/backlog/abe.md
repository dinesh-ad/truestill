# (abe) CLI-organized files were invisible to custody, and pre-existing rows are not repaired.

*Body of backlog entry `(abe)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abe) CLI-organized files were invisible to custody, and pre-existing rows are not repaired.**
  Recorded 2026-08-05, fixed forward the same day in `a0091cf`.
  - **The mechanism.** `organizer.py` has one `record_uploaded` call site, and `file_copies` is
    written only when `drive_uuid` is given. `cli.py` read a drive marker and never created one,
    so `truestill organize` into an ordinary folder wrote a `files` row with **no** copy row: in
    the dedup index, so a re-run skips that file forever, and outside custody, so `verify`,
    `status` and `where` cannot see it. The app never had this - it registers the destination
    before writing (`service/organize.py`).
  - **Fixed forward** by `cli._register_destination`, gated on `--apply`, rclone excluded.
  - ⚠ **Pre-existing rows are NOT repaired**, and that is the open half. On the maintainer's own
    catalog, 31 rows (ids 1-31, all 2026-07-25) sit in this state; every row from 2026-07-27
    onward has a copy. They now surface on Stats as "not on a registered drive".
  - **Is a repair path wanted? Undecided, and here is what it would cost.** A repair cannot be
    inferred: the catalog records no destination for those rows, so nothing knows *which* drive
    they were written to, or whether the files are still there. The honest options are
    (1) re-import from the originals, which the Stats copy already suggests and which needs no
    code; (2) a `truestill adopt`-style scan of a named drive, matching content by hash and
    writing the missing `file_copies` rows - which is `(hh)`, already filed for a related need;
    or (3) leave them and let the Stats count explain itself. **Option 2 is the only one that is
    new code, and `(hh)` would already cover it** - which argues for doing nothing here beyond
    making sure `(hh)` knows about this case.
