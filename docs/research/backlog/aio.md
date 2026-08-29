# (aio) RELEASING THE BAKED TEMPORARY SITS BETWEEN THE COMMITTED COPY AND ITS CATALOG ROW.

*Body of backlog entry `(aio)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aio) RELEASING THE BAKED TEMPORARY SITS BETWEEN THE COMMITTED COPY AND ITS CATALOG ROW.**
  Filed 2026-08-29 (P143), from the census `(ain)` asked for. **`(ain)`'s shape on the bake path,
  and the only other live instance of it** - narrower, unmeasured, and filed rather than fixed
  because an unmeasured fix is what this whole arc has been correcting.

  ## THE WINDOW

  `organizer._upload_with_metadata_write` ends:

  ```
  warning = destination.upload(staged, final_relative)   # commits by rename
  staged.unlink(missing_ok=True)                          # <- unguarded
  return copy_sha, warning
  ```

  The catalog row is written by `_execute_one_write` **after** this returns. So an `OSError` from
  `unlink` - anything other than the `FileNotFoundError` that `missing_ok` absorbs - propagates
  past a file that is already committed on the drive, and the row is never written. That is
  exactly `(ain)`: an orphan the catalog has never heard of, which the next run duplicates around
  because `_free_relative` cannot recognise it.

  ## WHY IT IS NARROWER, STATED RATHER THAN GLOSSED

  `staged` lives inside a `tempfile.TemporaryDirectory` on **this computer**, not on the user's
  drive - so the mount conditions that make `(ain)` ordinary (SMB, NFS root-squash, FUSE) are not
  in play. What is left:

  * **Windows, and it is the realistic one.** `unlink` raises `PermissionError` while another
    process holds the file open - an antivirus scanner reading a JPEG that exiftool has just
    rewritten is the ordinary case, not an exotic one. ⚠ **And Windows is the platform nothing
    here can test locally**; the three-OS `check` matrix is the only detector.
  * `EIO` on a failing local disk, or `EACCES` from a hardened `TMPDIR`.

  ⚠ **The bake path is not the common path** - it needs `ingest`, so today it is Takeout only.
  That bounds who can meet this and is not a reason to leave it.

  ## WHAT IS NOT ESTABLISHED

  - **Not reproduced.** `(ain)` was a source reading that proved true and `(aie)` before it; that
    is precedent for taking a reading seriously, **not** evidence that this one holds.
  - **The fix looks like two characters and may not be.** Suppressing the `OSError` leaks a staged
    file per failure, and `_MetadataBaker.close()` removes the whole `TemporaryDirectory` at the
    end of each chunk - so the leak may already be collected. That is a claim to check, not to
    assume.

  ## THE REST OF THE CENSUS, RECORDED SO IT IS NOT RE-RUN

  Five sites were read for *"a commit precedes a catalog write and something between them can
  raise"*. **Four are already closed, each by a different mechanism**, which is why `(ain)` and
  this were the only live ones:

  | site | what closes it |
  |---|---|
  | organize's relocation / `adopt` | `(agk)` - `_record_the_intent` writes the journal row **before** the rename |
  | `migrate._apply_one_move` | the migration journal, replayed by `resume_migration`, which handles *"catalog still points at the old path"* explicitly |
  | `migrate._undo_one` | the same journal row, cleared only by `forget_migration_move` at the end |
  | the bake's exiftool read-back | `(agv)` - the `bake_started_at` column, an in-flight marker |
  | `backup._copy_and_verify` | nothing that can raise sits between `commit()` and `record_copy` |

  🔑 **So the shape is well known here and has been closed three different ways.** What `(ain)`
  showed is that a *new* call added after a commit does not inherit any of them.

  ## RELATED

  `(ain)` (the same shape, shipped), `(agk)` (intent before the irreversible step), `(agv)` (the
  in-flight column), `(afe)` (what an orphan becomes).
