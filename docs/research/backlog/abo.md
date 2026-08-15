# (abo) The hash cache cannot say "I computed one hash and not the other".

*Body of backlog entry `(abo)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abo) The hash cache cannot say "I computed one hash and not the other".** Recorded
  2026-08-07 when that ambiguity produced a live defect: `attach_drive` wrote `perceptual=NULL`
  rows and a later organize preview took them as hits, silently losing near-duplicate detection
  (measured `near_dup=1` -> `0`). **Fixed at the caller** - attach now opens the cache read-only,
  enforced by SQLite - so this entry is the **general** fix, not the outstanding half of that one.
  - **The shape.** `perceptual` is nullable and carries two meanings: *not an image* and *not
    computed*. `HashCache.get` has `need_sha` for exactly this ambiguity on `sha256` and **no
    `need_perceptual` counterpart**. §8 already names this and defers it as a cache **schema**
    change; it is filed here so it has a letter rather than living in a parenthesis.
  - **A third state is the fix**, not a `need_perceptual` alone: without one, a legitimately
    NULL perceptual (a video, a file Pillow cannot decode, an image over
    `MAX_PERCEPTUAL_PIXELS`) misses forever and is re-attempted on every run.
  - **BLAST RADIUS, by code path rather than by any one cache.** Poisoned rows are exactly the
    files an attach HASHED - `linked + unmatched + unreadable`, i.e. every file on the drive not
    already at a recorded `file_copies.relative`. **Measured 1:1**: a 200-file drive in that
    state produced 200 poisoned rows. The app attaches **both** source and target inside every
    backup **run** (`service/backup.py`; the preview is `write=False` and returns before
    hashing, so previews are clean). Whole-drive poisoning is the ordinary case, not the edge:
    a drive organized by the CLI before it registered destinations (`(abe)`), a first-time
    registration of a folder that already holds a library, or any re-attach after copy rows were
    lost. Attaching a 2,000-file drive poisons 2,000 rows, and look-alike detection is off for
    all 2,000 on any later organize that reads those paths.
  - **DETECTION: yes, and nothing runs it today.** `sha256 IS NOT NULL AND perceptual IS NULL`
    on a path with an image extension. Not exact - that ambiguity *is* this entry, and a
    genuinely undecodable image looks the same - but precise enough to act on. Without it a user
    whose cache is poisoned has no way to learn their look-alike detection is off: no error, no
    count, no degraded-mode notice.
  - **REPAIR: targeted, not a `SCHEMA_VERSION` bump.** The bump works - a version mismatch runs
    `DROP TABLE IF EXISTS hash_cache` - and it is the wrong tool, because it drops **every** row
    for **every** user including the exiftool `metadata_json`, which is ~74% of a cold preview
    (measured 0.168 s warm against 12.27 s cold on 2,224 files, 73x). On a cloud mount at the
    measured 3.9 MB/s a full re-hash of a 196 GiB library is **~15 hours**: a repair that
    silently becomes an overnight job. The targeted delete - the detector query above, as a
    `DELETE` - keeps every clean row and its metadata, keeps non-image rows whose NULL is
    correct, and re-hashes only what was damaged.
  - **The zero measured on the maintainer's own cache (1,836 rows, none in that state) says
    nothing about how common this is** and is recorded only so nobody re-derives it. He wrote
    the product and has not exercised the path; attaching a drive is a normal first-day action
    for a real user.
