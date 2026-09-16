# (alb) THE REST OF THE CASE CLASS, AND THE NORMALISATION QUESTION BESIDE IT.

*Body of backlog entry `(alb)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Recorded 2026-09-16 with no work attached.** `(ala)` fixed the rank-4 defect - `rescan`, its
CLI caller, and the app's structural twin - and censused the class while doing it. **20 sites were
reachable; 4 were fixed.** These are the other 16, plus a second problem of the same shape that
`casefold` does not touch.

> ⚠ **ITEM 1 IS CLOSED (2026-09-16, `DECISIONS`-free: `(alc)`), AND THIS ENTRY WAS WRONG ABOUT IT
> IN TWO WAYS.** Left standing as written, with the corrections here, because a record edited to
> match the present stops being one.
>
> * **"Both answers are dangerous" overstated it by leaving out a tool already in the tree.**
>   Folding *unconditionally* would authorise overwriting a different file on Linux - true. But
>   `(ala)` had already shipped `filesystem.folds_case`, which folds **only where the mount
>   folds**. With the probe, Linux is untouched and the case question has the same answer it had
>   in `(ala)`. The danger was in the option I named, not in the question.
> * **The real hazard was not case at all, and this entry did not see it.** The catalog row
>   proves *we once wrote our content at that path*; it cannot prove the bytes there now are ours.
>   A user who replaced an organized photograph was overwritten silently, **on every filesystem**.
>   `(alc)` reads the occupant and refuses when the catalog accounts for it.
>
> ⚠ **AND THE COUNT BELOW DOES NOT ADD UP, WHICH ITS OWN AUTHOR DID NOT CHECK.** The lead says
> *"the other 16"*, the next heading says *"THE OTHER FOURTEEN"*, and the table has **13 rows**.
> The 16 came from 20 − 4 on *physical lines* while the table groups them (`albums` ×3,
> `hash_cache` ×4, two organizer name checks). The re-count is **20 physical sites: 5 could decide
> by content, 9 cannot, 6 are correctly about a path** - and three of the five need **no extra I/O
> at all**. The standing rule is that a census is re-run before it is acted on; this one was not,
> one day after it was written.

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

## 4. THE CASE TESTS NEVER SAY WHICH BRANCH THEY TOOK

Every case test in `(ala)` and `(alc)` derives its expectation from the filesystem it is running
on, deliberately:

```python
folds = (tmp_path / "Saved/PHOTO.JPG").exists()
assert [p.name for p in walk.files] == ([] if folds else ["photo.jpg"])
```

That is what lets them run on every lane with no `skipif` - the shape `(ais)`'s resolution asks
for. ⚠ **And it is exactly why they cannot tell anyone what the platform did.** A green macOS lane
proves the assertions hold there; it does not show that APFS folded and the folding branch
executed. I asserted that it did, twice, before going to look and finding no evidence either way.

**The remedy is an existing mechanism, not a new one.** `conftest.pytest_report_header` already
prints one line on every run - *"One line, every run, naming where the scratch actually went"* -
and adding the scratch filesystem's answer to it would make every lane state what it measured:

```
scratch: /data/tmp/truestill
case-folding: False        # or True on a macOS or Windows runner
```

⚠ **WHAT THIS WOULD AND WOULD NOT CLOSE, because the distinction is the whole reason the gap is
recorded rather than assumed away.** It closes *"which branch did the tests take"* - the header
plus a green lane says the folding path ran for real on a folding filesystem. It does **not**
close `(ala)`'s stated gap, which is one step further out: *no run anywhere shows a folding
mount's **walk** returning the drifted spelling end to end.* That still needs a writable
case-insensitive mount, and `(ala)` records that every unprivileged route to one on this machine
is closed.

**Cost**: one line in a hook that already exists, and one probe call at session start. **Not
done here** because it is a change to the test harness rather than to the product, and because
its value is entirely in what it would let a future reader claim - which is the kind of thing
`(ago)` asks to be argued before it is built rather than after.

## WHAT IS NOT PROPOSED

- **Whether the report line belongs in the header or in a test's own output.** The header is
  the cheapest place and the one that costs nothing when nobody is looking; a `record_property`
  into the JUnit XML would be queryable instead of readable. Not decided.
- **Whether these are one entry or fourteen.** They share a comparison, not a fix: three want
  `folds_case`, one wants `COLLATE NOCASE`, one wants `samefile`, and one is only an
  inconsistency. Bundling them would make the ranking meaningless.
- **A guard.** An AST rule that flagged every path comparison would fire on the 40 NOT-REACHABLE
  sites too, which is the cry-wolf shape `(ago)`'s bar refuses - and the 41 already-handled sites
  show the codebase does not need telling in general, only in particular.
