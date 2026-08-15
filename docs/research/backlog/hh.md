# (hh) `truestill adopt` - bring stray media in an organized drive into the catalog.

*Body of backlog entry `(hh)`, under **Ideas / deferred**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(hh) `truestill adopt` - bring stray media in an organized drive into the catalog.** Ruled
  by the maintainer. A drive can hold media truestill does not know about: files copied in by hand, a
  restore from elsewhere, or anything added after the last run. Today they are invisible to
  `verify`, to the custody count, and to `clean-empty`'s classification.
  - **Scan an organized drive for media files not in the catalog, report them named**, and on
    confirm run them **through the full normal organize pipeline** - EXIF, category rules, dating,
    dedup all decide placement.
  - ⚠ **Never the folder they were found in.** A file sitting in `Camera/2019/` is not evidence
    that it is a 2019 camera photo; someone may have dropped it anywhere. Placement is derived
    from the file's own metadata like every other file, or truestill would be laundering a
    guess as a decision - the same mistake the `(m)` selection rules forbid.
  - **Never automatic, never silent.** Offered after `verify` or `migrate-layout` when unknowns
    are found, and available standalone. Preview names every file; a typed confirm adopts.
  - **Precedent:** Lightroom's *Synchronize Folder*, which is the same operation for the same
    reason and is well understood by the audience.
  - **Shares the walk-and-classify machinery with `clean-empty`** - both answer "what is on this
    drive that the catalog does not account for", from opposite ends.
  - **(abe) needs this too, recorded 2026-08-05.** Files organized by the CLI before it
    registered its destination are in `files` with no `file_copies` row - the same
    "content is on the drive, the catalog does not know" shape from the other side. If
    this is built, it is the repair path for those rows, and `(abe)` argues no separate
    mechanism should be written for them.
