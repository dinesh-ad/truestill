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

  ---

  # CLOSED 2026-08-22. Two halves, and the entry's own constraint was respected.

  **The constraint first, because it is in the title.** `_BUSY_CODES` is **unchanged** -- still
  `SQLITE_BUSY`/`SQLITE_LOCKED` and nothing else. Nothing waits out a fault. What was added beside
  it is a **separate** family, `is_catalog_unwritable`, for the codes that mean *the catalog
  cannot be reached or stored*: `PERM`, `READONLY`, `IOERR`, `FULL`, `CANTOPEN`. Two questions,
  two predicates - and a bug of ours (`SELECT * FROM no_such_table`, `SQLITE_ERROR`) still keeps
  its traceback, because it is not a condition the user can act on.

  ## Half one - the SQLite half, closed by `(afe)`'s surface fix

  `(afe)` moved the refusal to `cli.main`'s single catalog seam, so `sqlite3.connect` failing at
  `Catalog.__init__` now reports instead of raising. Measured, catalog directory `chmod 555`:

  ```
  exit=7   traceback lines: 0   Diagnostic: SQLITE_CANTOPEN
  ```

  ## Half two - ⚠ THE HALF NEITHER ENTRY SAW: the failure is not a `sqlite3.Error` at all

  `Catalog.__init__` creates the catalog's parent **before** it connects
  (`catalog.py`, `path.parent.mkdir(parents=True, exist_ok=True)`). On a read-only or full disk
  that `mkdir` raises `PermissionError`, which **is not a `sqlite3.Error`** and so walked straight
  past both surfaces' catalog handlers - including the one `(afe)` had just added. Measured after
  half one was already fixed:

  ```
  exit=1   PermissionError: [Errno 13] Permission denied: .../ro/newdir
  ```

  Now raised as `CatalogUnwritableError` - a plain `Exception`, **deliberately not an `OSError`**,
  because the codebase has many `except OSError` blocks around filesystem work and a catalog that
  cannot be created is not one more unreadable path for them to absorb. It carries the errno, so
  the refusal keeps a diagnostic where a SQLite name would be:

  ```
  exit=7   traceback lines: 0   Diagnostic: EACCES
  ```

  ## Half three - a §9 wrinkle this fix introduced, and it was live

  `(afe)`'s backstop sentence said the command *"stopped rather than continue without recording
  what it did"* and sent the reader to `rescan`. That is reached from **any** command: on
  `truestill status`, which writes nothing, both clauses describe work that never happened. The
  backstop cannot know whether anything was written, so it may not assert that anything was.
  `rescan` is now offered against a condition the reader can check - *"if a run was interrupted
  partway"* - rather than asserted as a consequence.

  ⚠ **This is the general form worth keeping**: a message written at the site that knows the
  facts, then reused as a backstop that does not, silently becomes a claim rather than a
  description. `organizer` still builds the detailed account where it *does* know what landed.

  ## ⚠ RESIDUAL, deliberately not fixed here

  The startup banner still prints *"No catalog yet. Truestill will create catalog file `<path>` on
  first use"* immediately before the refusal - a prediction the next line falsifies. That is the
  **creatable-vs-refused conflation** `path_reach` exists for (`(aey)`), not a catalog defect, and
  fixing it means deciding whether the banner probes writability at all - which `(afc)` ruled
  against in favour of refusal against a recorded expectation. Left open and named rather than
  patched at this one call site.
