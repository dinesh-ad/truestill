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
    glancing at a partial one. `copy_leaving_nothing` is a two-argument drop-in; the reason this is
    not a one-line fix is the surrounding `CatalogMove` result, which reports outcomes rather than
    raising, so the leftover-naming half of `CopyOutcome` has to be threaded into the message.
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
