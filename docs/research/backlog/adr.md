# (adr) A FAILED CATALOG COPY LEAVES 0 BYTES, AND THE NEXT LAUNCH SILENTLY BUILDS A SCHEMA INTO IT.

*Body of backlog entry `(adr)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adr) A FAILED CATALOG COPY LEAVES 0 BYTES, AND THE NEXT LAUNCH SILENTLY BUILDS A SCHEMA INTO
  IT.** Recorded 2026-08-15, split out of `(adb)` during its investigation because it is a
  **different failure with a different remedy**, and the worse of the two. `(adb)` describes a
  *truncated* catalog; truncation is loud. **Zero bytes is silent**, and silence is the defect.
  - **Measured, not reasoned.** `shutil.copy2` creates the destination before it writes: patching
    the copy to raise `ENOSPC` left the destination **existing at size 0**. Then
    `inspect_catalog` (`catalog_startup.py:90`) opens it, `Catalog._migrate` builds the **full
    schema into the empty file**, and it is reported as `presence=EMPTY`, `tone="notice"` -
    *"Opened empty catalog file at ..."*. A valid, empty 159,744-byte catalog now exists where a
    failure was.
  - **The evidence is destroyed by the act of looking.** After that first open there is nothing
    left to find: no partial, no error, no short file. The distinction between *"this copy
    failed"* and *"you started a new library"* is gone, and `EMPTY` is the calm reading of both.
  - **Why that is worse than truncation.** A truncated catalog raises
    `sqlite3.DatabaseError: database disk image is malformed` - observed at every cut from 1% to
    99% of a 5,000-row catalog - and `cli.main` deliberately re-raises anything that is not a busy
    lock (`cli.py:3379-3383`). The user is stopped. Zero bytes stops nobody.
  - **And the product then tells them to delete the good one.** `catalog_move.py:138` says
    *"Check the copy, then delete the old one when you are happy"*. Checking a 0-byte file by
    opening the app turns it into a healthy-looking empty catalog, which is precisely the state
    that makes deleting the original feel safe. `still_in_use=source` (`:141`) and
    `default_catalog_path` preferring the legacy file (`app_paths.py:162`) are what limit the
    blast radius today - the real catalog stays live **until the user follows the instruction**.
  - **One mitigation already exists and is worth keeping in view:** a second
    `truestill catalog --move` refuses with `DESTINATION_EXISTS` and prints the size via
    `_describe` (`catalog_move.py:117-128`), so a person who re-runs the command sees `0 bytes`.
    That is the only surface that currently tells the truth about this file.
  - **Not a duplicate of `(adb)`.** `(adb)`'s remedy is about *bytes taking a name*; this one is
    about **an empty file being indistinguishable from a new library**. Staging fixes `(adb)` and
    does not touch this: a staged copy that fails still leaves the destination absent, which is
    correct - but the question *"should an empty file at the catalog path ever be silently
    adopted?"* is separate and survives any fix to the copy path.
  - **The open product question, which is not mine to settle:** `WILL_CREATE` and `EMPTY` are
    deliberately calm (`catalog_startup.py` module docstring: *"never framed as a hard failure"*),
    because a genuine first run must not look like an error. A zero-byte file is a **third** state
    that currently reads as the second. Whether it earns its own `CatalogPresence` member, and
    what tone it gets, is a product call.
