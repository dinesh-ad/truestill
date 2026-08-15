# (aba) Nothing reconciles the catalog's recorded location with where a file actually is.

*Body of backlog entry `(aba)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aba) Nothing reconciles the catalog's recorded location with where a file actually is.**
  Found 2026-08-03 by tracing what happens when a user tidies by hand - the maintainer moved a
  file out of `Saved/` into its trip folder after an organize. **Three symptoms, one root
  cause**, filed together because they share it and would otherwise be fixed three times; each
  is separately actionable and separately ranked below.
  - **The good news first, so nobody "fixes" it into a regression.** With the catalog that
    recorded the run, **no organize path undoes a hand-move**. `DedupIndex.from_catalog_rows`
    seeds from `(source_path, sha256, perceptual)` - **content, not location** - so a re-run
    matches the unchanged source and `execute` skips it before any write path:
    `if resolution.exact_duplicate is not None: ... continue`. The destination is never
    examined. Confirmed on a real 2,109-file re-preview: 2,108 exact duplicates.
  - **SYMPTOM 1 - `verify` reports a hand-moved file as MISSING. A real defect, and the one to
    fix.** It re-hashes each recorded copy, finds nothing at `files.relative`, and returns
    `CopyStatus.MISSING` - *"the file is gone from the drive"* - while being entirely blind to
    the same bytes sitting safely at the new path. **This is the worst possible place for a
    false alarm**: `verify` is the feature whose whole value is being trustworthy, and a user
    who tidies one folder and is then told twelve files are missing learns to ignore the report
    - including the run where something really is gone. The likely fix is cheap: on a miss,
    look for the content elsewhere on the drive before saying "gone", and distinguish *"not at
    the recorded path"* from *"not on this drive"*. **Do not simply reword it** - a file that
    genuinely vanished must still be loud.
  - **SYMPTOM 2 - `--in-place` on a FRESH catalog silently reverts the move.** Narrow, but it
    is literally "Truestill undid my tidying". `_already_at_target` is the only thing that
    would move a file back, and it sits *downstream* of the duplicate skip, so a live catalog
    never reaches it - its own docstring says so: *"With a live catalog dedup catches this
    first; on a fresh catalog this is the only thing that does."* With a different `--db`, a
    lost catalog or a re-clone, dedup is empty, the check compares the file's current path
    against the **rule-derived** target, finds they differ, and moves it back. Journalled, so
    `undo-organize` reverses it - but silent at the time.
  - **SYMPTOM 3 - a changed-layout migration halts on a path that no longer exists.**
    `plan_migration` plans from the catalog, so it computes `old -> new` from the recorded
    `relative`. With the layout unchanged the file falls into `plan.unchanged` and nothing
    happens; with the layout changed it plans the move, `relocate` finds `old` absent and
    raises `cannot relocate missing copy: <old>`, **halting the whole migration**. Loud, which
    is right, but it names a path and not the cause - a user who tidied three weeks ago cannot
    connect the two.
  - **`ALREADY_PLACED` never covered this**, checked rather than assumed: set in exactly one
    place, gated on `relocation is not None` (in-place only), and it asks
    `(dest_root / computed_relative).samefile(source)` - *"is this file where the rules say"*.
    A hand-moved file is by definition not, so it reads as "needs moving". It recognises a file
    **Truestill** placed, never one the user did.
  - **Why one entry and not three, stated because three were asked for.** The three share one
    cause - a recorded location that nothing ever re-checks - and the fix for symptom 1 (find
    the content elsewhere before declaring it gone) is most of the fix for the other two. Three
    entries would fragment one design question and invite three partial repairs. All three are
    named, ranked and separately actionable above.
