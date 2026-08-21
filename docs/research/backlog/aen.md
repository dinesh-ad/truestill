# (aen) THE CATALOG'S FIRST WRITE CRASHES ON A FULL DISK, AND `catalog_busy` MUST NOT WIDEN TO COVER IT.

*Body of backlog entry `(aen)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aen) THE CATALOG'S FIRST WRITE CRASHES ON A FULL DISK.** Split out of `(aek)` on 2026-08-21,
  which named it as an untested neighbour and left it out of scope deliberately.

  ## WHAT HAPPENS

  `Catalog.__init__` does `path.parent.mkdir(parents=True, exist_ok=True)` (`catalog.py:888`) and
  `sqlite3.connect` (`catalog.py:902`), then migrates - none of it guarded. Reproduced 2026-08-21
  with the catalog directory unwritable:

  ```
  File ".../truestill_core/catalog.py", line 902, in __init__
    self._conn = sqlite3.connect(...)
  sqlite3.OperationalError: unable to open database file
  ```

  A traceback, from the same class of condition `(aek)` fixed one layer out. On a full disk the
  code is `SQLITE_FULL` rather than an `OSError`.

  ## ⚠ WHY IT IS NOT A `catalog_busy` CHANGE, AND THIS IS THE POINT OF THE ENTRY

  `cli.main` catches `sqlite3.Error` and re-raises anything that is not `is_catalog_busy`
  (`cli.py:3618-3622`); `_BUSY_CODES` is `SQLITE_BUSY`/`SQLITE_LOCKED` only
  (`catalog_busy.py:32`). **That is correct and must not be widened.** Its own docstring gives the
  reason: `OperationalError` also covers a disk I/O error, a malformed schema and a read-only
  database, and answering those with *"wait for the other operation to finish"* sends a user to
  wait out a fault that will never clear.

  So the remedy is a **second** recognition with its own wording, not a wider net on the first.
  `drive_unwritable.explain_unwritable_drive` is the shape and probably the home - it already
  words `ENOSPC`, `EDQUOT`, `EROFS` and a vanished drive for the two writes that reach a user's
  disk - but a SQLite error is not an `OSError` and does not carry an `errno`, so the mapping is
  from `sqlite_errorcode` and has to be written.

  ## NOT DECIDED

  - **Where the refusal lands.** The catalog is opened before almost everything, including inside
    `catalog_startup.inspect_catalog`, which `(adr)` already uses to stop the process before it
    binds a socket. That may be the natural home, or it may be too early.
  - **What the CLI exits with.** `5` is taken by a busy catalog, `4` by an unusable destination.
    A full disk under the catalog is neither.
  - **Whether the hash cache is in scope.** `HashCache` already degrades to a miss on any
    `sqlite3.Error` or `OSError` (`hash_cache.py:157`), so it is the one sidecar that is already
    right; it is named here so nobody re-derives that.
