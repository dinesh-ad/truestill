# (akw) VERIFY SAW A MOVE, WROTE NOTHING, AND FROZE A VERIFICATION DATE FOR EVER.

*Body of backlog entry `(akw)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT, MEASURED ON THE INSTALLED BUILD

`verify` had three write branches - VERIFIED, MISSING, MISMATCH - and **none for MOVED**. A
renamed or re-foldered file kept its old `relative` *and* whatever `last_verified` it happened to
carry. Because every later verify reports MOVED again and writes nothing again, **that stamp could
never update**.

Three verifies against `/usr/bin/truestill`, one file renamed between the first and the second:

```
ord_0090 (intact)   verified 21:21:59   <- moved with each run
ord_0082 (renamed)  verified 21:20:52   <- frozen, for the life of the library
ord_0085 (corrupt)  not yet verified    <- correctly cleared by mark_copy_damaged
```

So `truestill where` named a path that does not exist **and attached a verification date to it**.
⚠ **A confident, wrong answer with a freshness guarantee is worse than an obviously stale one**,
because nothing in the output invites a reader to doubt it. A missing file at least said *"not yet
verified"*.

## WHAT THIS IS WORTH: THE CASE THAT DEFEATS LIGHTROOM IS THE EASY ONE HERE

Lightroom relinks **by path**, so renaming outside it is the documented catastrophe - *"just about
the worst mistake you can make, because now you do indeed have to relink each image
individually"*; 2,600 missing photos and *"not totally automatically"*; one forum workaround was
generating dummy files with the old names so the match would succeed.

Truestill's identity is the **content hash**. `_locate_moved` already narrowed by size and decided
by sha256, and already produced the right answer. **The matching was never the hard part. Only the
write was missing.**

## `relocate_copy`: WHAT IT ASSUMES, AND WHY VERIFY MAY CALL IT

```python
UPDATE file_copies SET relative = ? WHERE sha256 = ? AND drive_uuid = ?
```

`file_copies` is `PRIMARY KEY (sha256, drive_uuid)`, so that UPDATE reaches **exactly one row**.
It assumes nothing a truestill-made move guarantees; both existing callers sit in `migrate.py`
only because migrate is the only thing that *moved* files until now.

This satisfies `(abn)`'s corrective class on its own terms - *"safe because its evidence is a
content hash and not a path"* - because the evidence here is `expected_hash`, not a name and not a
size. It never calls `forget_organized`, and no row is dropped.

**It is an observation, not a repair.** The same class of write as the three branches beside it:
the drive is untouched, and the catalog is corrected to match what the drive already says.

## WHAT CHANGED

- `VerifyResult.moved_to`, a **field rather than a sentence**. The location already existed inside
  `detail` as *"found at X"*, so recording it would have meant parsing prose written for a human -
  which breaks the moment anyone rewords it. Same trap `FRIENDLY_ERRORS` avoids by matching an
  exception name.
- A `MOVED` branch on **both surfaces in one commit**, which is `(aku)`'s precedent: a write branch
  on one surface only is a catalog that means different things depending on which window was open.
- `MOVES_RECORDED`, said whenever a rewrite happened: *"N moved file(s): the catalog now points
  where they actually are. Nothing on the drive was touched."* ⚠ **A catalog rewrite the user did
  not ask for must be named**, and *"verify"* does not sound like a command that writes.
- ⚠ **The closing line was made false by this change and had to move.** It read *"(read-only:
  Truestill never repairs...)"*. The promise about a user's FILES is unchanged and still absolute;
  the blanket claim is what went, because an untrue sentence in a report is the class of defect
  this arc keeps finding.

**`rescan` is untouched.** Its rule - *"nothing here writes to a catalog or to a drive, and no
caller of it may"* - is not overturned. The fix went where the writes already were.

## THE FOUR EDGES, ESTABLISHED

| edge | what happens |
|---|---|
| moved **outside** the drive root | **MISSING**, never relocated. The search is `os.walk(root)`, so a drive cannot testify about somewhere else - and `relative` must stay drive-relative |
| two identical files, the recorded one deleted | relocates to **one** of them; both are byte-identical so either is a true answer, and the PK allows only one row per (content, drive) |
| file moved onto another catalogued file's old path | both correct: the mover is **verified** at that path, the file whose bytes are gone is **MISMATCH**. Two rows share a `relative`, which violates nothing - the PK is (sha256, drive_uuid) - and `a_place()` excludes the damaged one |
| move on a **read-only** drive | recorded. The catalog is not on the drive, so *"Nothing on the drive was touched"* is literally true rather than merely intended |

## AND THE NAMES THAT LED NOWHERE

`scan_source` called `path.is_file()`, which **follows** a symlink, so a dangling link and a
symlink loop both answered False and hit a bare `continue`: not media, not a document, not
unrecognized, not hidden, not an unreadable folder.

Measured on a hostile corpus: **287 paths existed; 282 media + 4 unrecognized + 1 hidden = 287
were accounted for; three were never mentioned.** ⚠ **A count that is internally consistent and
incomplete is worse than one that is obviously short** - nothing invites a second look.

They now land in `SourceScan.broken_links` and in `skipped_extension_counts`, the one home all
three surfaces render. Counted by **name**, like `hidden`: an extension census of a broken link
reports the extension of a file that is not there. The row reads **"leads nowhere"** rather than
"broken" - a loop, a deleted target and a link into an unmounted drive are three problems with one
appearance, and a user who unplugged a disk has not broken anything.

## WHAT PROVES IT

Eight mutations, eight caught - **two only after the vacuity check found real gaps in the tests**:

| mutation | caught by |
|---|---|
| MOVED seen and not recorded (the defect) | 5 of 10 in the CLI suite |
| path fixed, `mark_copy_verified` skipped | `test_the_verification_date_moves_again...` ⚠ **survived at first** |
| the rewrite happens silently | `test_the_rewrite_is_named_in_the_output` |
| the untrue blanket "read-only" returns | `test_the_closing_line_no_longer_claims...` |
| broken links dropped again | 3 of 6 in the core suite |
| every non-file called a broken link | `test_something_that_is_not_a_link...` ⚠ **survived at first** |
| the app stops recording moves | all 3 app tests |
| `moved_to` never carried | 8 across both suites |

⚠ **The first survivor is the instructive one.** The original stamp test compared only the second
and third dates - and a mutant that relocated the path but skipped the stamp still passed, because
by the third run the file sits at the recorded path and is stamped as an ordinary VERIFIED. The
date would have been stale for exactly one run, and no test could see it. The assertion now pins
**the verify that observed the move** as the one that dates it.

⚠ **The second needed a FIFO.** The corpus held only symlinks, so widening the guard to `if True`
swept every non-file into the bucket and nothing noticed.
