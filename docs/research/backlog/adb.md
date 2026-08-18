# (adb) TWO COPY PATHS STILL WRITE THE REAL NAME FIRST, AND ONE OF THEM IS THE CATALOG.

*Body of backlog entry `(adb)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adb) TWO COPY PATHS STILL WRITE THE REAL NAME FIRST, AND ONE OF THEM IS THE CATALOG.** Named
  in `(acj)`'s closure 2026-08-11 as out of its scope, and filed here because a line in
  `SHIPPED.md` records what was *not* done without tracking it. `(acj)` staged every copy that goes
  through `safe_copy`; these two never did.
  - **`catalog_move.py:131` is the one that matters, and it is `(abu)`'s exact shape on a database.**
    A bare `shutil.copy2(source, destination)`. A failure part-way leaves a **truncated SQLite file
    at the destination path**, wearing the name the user was told to point at. The function's own
    contract makes it worse: it never removes the source and tells the user to *"check the copy,
    then delete the old one"* - so the failure mode is a person deleting a good catalog after
    glancing at a partial one. ~~`copy_leaving_nothing` is a two-argument drop-in; the reason this
    is not a one-line fix is the surrounding `CatalogMove` result, which reports outcomes rather
    than raising, so the leftover-naming half of `CopyOutcome` has to be threaded into the
    message.~~ **The named remedy is the wrong category of tool - see the amendment below.**
    *(Also inaccurate as written: `CatalogMove` reports outcomes for its five **guards**, but the
    copy itself has no `try`, so an `OSError` at `:131` propagates and no `CatalogMove` is built.)*

  - ⚠ **AMENDED 2026-08-15: `copy_leaving_nothing` IS A FILESYSTEM ANSWER TO A DATABASE
    QUESTION.** Staging and renaming guarantees no partial wears the real name; it does not
    guarantee the bytes are a **coherent database**. Measured: the catalog runs
    `journal_mode=delete` (no `PRAGMA journal_mode` anywhere in `packages/*/src`), so the main file
    is **mutated in place** while the original pages sit in `catalog.sqlite-journal`. A copy of the
    main file alone therefore takes **partially-applied changes with no journal beside them to roll
    back** - and staging copies that torn state more reliably, not less. **This is worse than WAL,
    not better:** under WAL the main file would at least be a consistent older snapshot with the
    recent changes in `-wal`. The rollback journal has no such property.
    - **The blessed answers, from SQLite's own documentation:** `sqlite3.Connection.backup()`
      (stdlib, wraps the C online-backup API - present, and used **nowhere** in this repo) and
      **`VACUUM INTO`**. `VACUUM` appears only inside `_drop_redundant_sha256_index`
      (`catalog.py:817`); `VACUUM INTO` is unused. A third official tool, **`sqlite3_rsync`**,
      exists for copying a live database over SSH and is noted here only so it is not rediscovered
      as news.
    - **`VACUUM INTO` is the better fit, and one property decides it: it REFUSES a destination that
      exists or is non-empty.** That is exactly this module's never-overwrite invariant, enforced
      **by SQLite** instead of by our own `destination.exists()` check - and it **cannot produce
      `(adr)`'s 0-byte artefact at all**, because it never creates a file it does not go on to
      fill. `Connection.backup()` overwrites, so it would need the existing guard kept and would
      still **create** `(adr)`'s artefact. ⚠ **Half of that sentence expired on 2026-08-18**, and
      the surviving half is the one that decides this: `(adr)` shipped, so a 0-byte file is no
      longer silently *adopted* by the next launch - the app refuses it. What `VACUUM INTO` still
      buys is that the artefact is never **created**, which is a smaller advantage than this
      paragraph was written to claim and still a real one. The trade is stated rather than hidden: `VACUUM INTO` takes a write
      lock for its duration and rewrites every page, while `backup()` is incremental and restarts
      if an external writer commits mid-copy.
    - **Why a file copy is not merely riskier but differently broken:** SQLite documents that
      copying a live database can yield *"some old and some new content"*, and that the final
      `close()` on your own descriptor **drops the POSIX advisory locks SQLite holds through a
      different descriptor** - leaving SQLite believing it holds a read lock it does not.

  - ⚠ **AMENDED 2026-08-15: THE TORN COPY IS REACHABLE BY ORDINARY USE, NOT BY MISUSE.** The entry
    described the hazard without saying anyone could reach it. Three verified facts say they can:
    `move_catalog_to_standard` **never opens the catalog** (`catalog_move.py:24` - *"no catalog is
    opened; this moves a file"*), so nothing in the copy path can detect or exclude a concurrent
    writer; the `catalog` subcommand declares no `--db` (`cli.py:536-540`), so `_dispatch`'s
    `hasattr(args, "db")` guard (`cli.py:3389`) is False and the startup `inspect_catalog` never
    runs - **the CLI does not open the catalog it is about to copy**; and `(adn)` records that
    nothing stops two processes sharing one catalog, naming three routes, including
    `truestill organize` beside an open window. See `(adn)`.

  - ⚠ **AMENDED 2026-08-15: the destination is not necessarily a local disk.** `_data_dir()`
    honours a `TRUESTILL_DATA_DIR` override (`app_paths.py:107-111`), so `standard_catalog_path()`
    can name a network path. SQLite's guidance is that locking on network filesystems *"has been
    known to operate incorrectly"* and that `fsync` there is less robust - so whichever remedy is
    chosen, it is writing a database through a layer SQLite declines to vouch for. Reading a local
    source and writing a remote destination is the milder direction; it is not a non-issue.
  - **`organizer._MetadataBaker` (`organizer.py:924`) is a different, smaller problem wearing the
    same clothes.** It stages into the **system** temp directory - not beside the target - so
    `safe_copy` would not help even if applied: the write to the real destination is the *upload*,
    a filesystem away. Its own partial is inside a temp tree that is torn down, and a copy that
    dies never enters `self._ready`, so nothing incomplete is uploaded. **The cost here is not
    safety, it is a full second write of every file that needs metadata baked**, on whatever
    filesystem `TMPDIR` names - which on a small root partition is a place a photo library does not
    fit. Measure before changing anything: `PERFORMANCE.md` has no figure for the bake path.
  - **Do not "fix" these together.** They share a `shutil.copy2` and nothing else - one is a
    correctness hole with a known remedy, the other is a placement question with no measurement
    behind it.
