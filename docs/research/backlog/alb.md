# (alb) THE REST OF THE CASE CLASS, AND THE NORMALISATION QUESTION BESIDE IT.

*Body of backlog entry `(alb)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Recorded 2026-09-16 with no work attached.** `(ala)` fixed the rank-4 defect - `rescan`, its
CLI caller, and the app's structural twin - and censused the class while doing it. **20 sites were
reachable; 4 were fixed.** These are the other 16, plus a second problem of the same shape that
`casefold` does not touch.

## 1. ⚠ `organizer.py:_free_relative` - THE ONE THAT CAN DESTROY DATA, EITHER WAY

```python
if reclaimable is not None and relative == reclaimable:
    return relative, False
```

`reclaimable` is the catalog's `file_copies.relative`; `relative` is freshly rendered by the
layout engine. **This is the one path in the product permitted to overwrite an existing file** -
`(aja)`'s repair for an interrupted write, so a zero-byte corpse is replaced rather than joined by
a `…_1.jpg`.

**Unfixed, and the reason is that BOTH answers are dangerous:**

* **Leave it exact**: on a folding filesystem a case drift makes the guard miss,
  `destination.exists(relative)` then answers True, and the repair lands as `…_1.jpg` - the drive
  keeps the corpse, gains a duplicate, and the catalog row still points at the corpse. That is
  `(ain)`'s self-worsening shape arriving from the dedup side, which this branch exists to prevent.
* **Fold it unconditionally**: on Linux `A.jpg` and `a.jpg` are two genuinely different files, so
  the guard authorises overwriting **the wrong one**. This is the counter-example that decided
  `(ala)` against blanket folding.

So it needs `folds_case` like the others - and changing *when the single sanctioned overwrite
fires* is a decision about data loss, not a comparison tidy-up. ⚠ Note the asymmetry already in
that function: line 1099 compares strings while line 1101 asks the filesystem, so the two
adjacent lines already disagree about who decides identity.

**Reachable through `(akw)`**: `verify` relocates a drifted row to the on-disk spelling, after
which a later organize renders the original spelling and the two differ. The defects compose.

## 2. THE OTHER FOURTEEN, WITH WHAT EACH COSTS

| site | harm |
|---|---|
| `dedup.py:credible_copies` (`sizes.get(relative) == want`) | every copy whose case drifted drops out silently; `backup` re-uploads instead of skipping. Safe direction, wrong cost |
| `cleanup.py` (`f"{relative}/{e.name}" in removed`) | a folder scored OCCUPIED when it is empty, or the reverse - **the only directory-removal path in the product** |
| `dedup.py` (`path in self._catalog_paths`) | a duplicate reported as *"earlier in this batch"* rather than *"already in your library"* - the vocabulary distinction `left_behind.py` says must not blur |
| `app/service/backup.py` (`source.resolve() == target.resolve()`) | ⚠ `Path.resolve()` does **not** normalise case on any platform, so a backup onto itself can pass the guard when both folders are unregistered |
| `destinations/rclone.py` (`relative_path in self._listing`) | an existing remote file reads as absent on any remote whose backing store folds case - re-upload, or `upload()` clobbers |
| `catalog.py` `SELECT id FROM albums WHERE name = ?` (×3) | typing `Goa` when `goa` exists mints a second album. **One `COLLATE NOCASE` on one column**; there is not one anywhere in the schema today |
| `hash_cache.py` (`key = str(path)`, ×4) | performance only - but `:374` then **prunes** the "orphan" rows, so the miss becomes permanent |
| `exif.py` (`by_name.get(source)`) | a miss does not raise; it creates a second entry under a different `Path`, so metadata attaches to a path nobody organizes |
| `drive.py` (`other == here`) | the same-place short-circuit misses, producing a spurious *"this drive is in two places"* |
| `catalog.py` `DELETE FROM reclaim_journal WHERE source_path = ?` | a stale journal row survives. ⚠ Reachability **not** established - only the immediate caller was traced |
| `catalog.py` `UPDATE inplace_moves ... old_relative = ?` | a zero-row UPDATE leaves an undo step unmarked. Weakest of the set |
| `organizer.py` marker-name and `_original` suffix checks | only a case-mangling restore tool reaches them |
| `app/service/trips.py` (`seen[name] += 1`) | ⚠ **an inconsistency rather than a proven defect**: its sibling `folder_hint.py` casefolds the same data and this does not |

## 3. NFD versus NFC - A DIFFERENT FIX OF THE SAME SHAPE

macOS HFS+ stores filenames **decomposed**, so `café.jpg` written there is `café.jpg` while
the same name written on Linux is `café.jpg`. Different bytes, identical case.

⚠ **`casefold` does not fix this** - `'café'.casefold() == 'café'.casefold()` is **False**.
`unicodedata.normalize("NFC", ...)` does, and it is a **separate** normalisation with a separate
decision behind it.

**Exposure, measured 2026-09-16** rather than assumed:

```
  /data/TruestillLibrary/Input      2,587 files,  0 non-ASCII,  0 decomposed
  exif-samples                        115 files,  1 non-ASCII,  0 decomposed
  metadata-extractor-images        10,703 files,  3 non-ASCII,  0 decomposed
```

Zero decomposed names anywhere, because every corpus this project owns was written on Linux or
Windows. **The exposure is real and currently untestable here** - it needs a macOS-written tree.

**And the decision is not obvious**, which is why it is filed rather than done: on Linux the two
forms are two genuinely different files, so unconditional normalisation carries the same
silent-loss risk that `(ala)` refused for case. Whether a probe can even answer it is open - a
filesystem that *preserves* NFD (APFS) behaves differently from one that *imposes* it (HFS+), and
the probe `(ala)` uses cannot distinguish them.

**The shape accommodates it**: `rescan.compare_key` is the one place a second normalisation would
go, and it already carries the rule that the derived form is never stored.

## WHAT IS NOT PROPOSED

- **Whether these are one entry or fourteen.** They share a comparison, not a fix: three want
  `folds_case`, one wants `COLLATE NOCASE`, one wants `samefile`, and one is only an
  inconsistency. Bundling them would make the ranking meaningless.
- **A guard.** An AST rule that flagged every path comparison would fire on the 40 NOT-REACHABLE
  sites too, which is the cry-wolf shape `(ago)`'s bar refuses - and the 41 already-handled sites
  show the codebase does not need telling in general, only in particular.
