# (aek) THE COPY PATH SURVIVES A FULL DISK; THE SETUP PATH CRASHES WITH A TRACEBACK.

*Body of backlog entry `(aek)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aek) THE COPY PATH SURVIVES A FULL DISK; THE SETUP PATH CRASHES WITH A TRACEBACK.** Found
  2026-08-20 by the first soak, S7. **The contrast is the finding** - the same feature handles the
  same errno impeccably a few lines later.

  ## ✅ WHAT THE COPY PATH DOES, AND IT SHOULD NOT BE DISTURBED

  Organizing 289 MB into a destination with the user's quota exhausted (real `EDQUOT`, errno 122,
  same class as `ENOSPC`):

  ```
     82  failed
     79  organized
      5  duplicate, skipped
  ```
  **exit 1. No traceback.** Each failure named the file, the destination relative path and the
  errno. And what was **left behind** was clean: **79 complete files, 79 catalog rows - exact
  agreement - 0 `.partial` files, 0 zero-byte files.** Every failed in-flight write was removed.

  This is the same `.partial` -> rename -> record discipline that survived a `kill -9` in S4, and
  it holds under space exhaustion too. **A failed copy leaves no corrupt file and no phantom row.**

  ## ⚠ WHAT THE SETUP PATH DOES

  The same command, against a destination **not yet registered**, on the same full disk:

  ```
  OSError: [Errno 122] Disk quota exceeded
    ... create_marker -> write_marker -> marker_path(root).write_text(...)
    (full Python traceback ending in pathlib/_abc.py)
  ```

  `write_marker` calls `Path.write_text` with no handling, so **the first thing organize does to a
  new destination** - write `.truestill-drive.json` - raises an unhandled `OSError`.

  ⚠ **Worse in context: this is the first run against a new drive**, when a user is least sure they
  did the right thing, and the product answers with an interpreter stack trace rather than *"there
  is not enough space on that drive"* - **which it plainly knows how to say, because the copy path
  says it 82 times in the same run.**

  ## AND A VOCABULARY LEAK IN THE MESSAGE THAT DID WORK

  Every failure line reads `FAILED: IMG_2707.JPG: cannot upload to '2013/...'`. The destination is
  a local folder; nothing is uploaded. ⚠ `IMPLEMENTATION_STANDARDS.md` §9: **no backend vocabulary
  reaches a user.** `upload` is the internal destination-adapter verb (the `record_uploaded` /
  rclone lineage) surfacing in the one message a user reads when something has gone wrong.

  ## WHAT IS NOT DECIDED

  - **Which setup writes need hardening.** `write_marker` is the one measured; the decisions-file
    write beside it and the catalog's own first write are the obvious neighbours and were **not**
    tested. ⚠ Do not assume they behave the same way - the whole finding here is that two writes in
    one feature behaved differently.
  - **What a full disk should DO at registration** - refuse cleanly, or register and let the copy
    path report per-file. The second is closer to what already works.
  - ⚠ **Not measured: a disk that fills between registration and copying**, which is the ordinary
    real case and sits between the two paths above.
