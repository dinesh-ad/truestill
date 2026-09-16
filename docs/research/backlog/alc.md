# (alc) THE ONE BRANCH THAT MAY DESTROY BYTES NOW PROVES WHAT IT IS DESTROYING.

*Body of backlog entry `(alc)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

`organizer._free_relative`'s `reclaimable` bypass is the only place in this product where a
catalog row alone authorises overwriting an existing file. `(ala)` found it and deliberately left
it, recording that **both** answers to the case question looked dangerous. Tracing it end to end
found that one of those answers was never dangerous, and that a larger hazard sat underneath.

## 1. THE CASE QUESTION WAS NOT DANGEROUS - I HAD NAMED THE WRONG RISK

`(alb)` recorded: *"folding it unconditionally authorises overwriting a genuinely different file
on Linux."* True - of **blanket** folding. `(ala)` had already shipped `filesystem.folds_case`,
which folds **only where the mount folds**. Applied here, Linux is untouched and NTFS/APFS becomes
correct. It is the same question with the same answer, and the entry that filed it overstated the
risk by leaving out the probe that was already in the tree.

Without it: the catalog says `Saved/Photo.JPG`, the mount says `Saved/photo.jpg` is the same file,
the bypass misses, `exists` answers True, and the repair lands beside the corpse as `…_1.jpg` -
`(ain)`'s measured shape, **nine files on the drive from three photographs, six of them orphans no
catalog will ever mention, exit 0**.

## 2. THE HAZARD UNDERNEATH, WHICH IS NOT ABOUT CASE

**The row proves we once wrote our content at that path. It cannot prove the bytes there now are
ours.** A user who replaces an organized photograph with their own edit leaves the row untouched;
`dedup.credible_copies` is **size-only and says so** (*"A copy whose size matches and whose bytes
are wrong survives this filter"*), so the replacement fails the size check and sends us straight
to the branch - which renamed onto it. `StagedCopy.commit` uses `Path.replace` and its docstring
says *"replacing whatever is there"*. **Nothing read the file first.**

That was true on every filesystem, today, before this.

## 3. ⚠ THE CONTENT HYPOTHESIS IS INVERTED AS POSED, AND THE INVERSE IS THE ONE THAT WORKS

*"Read the bytes, and overwrite only if they are what the catalog says"* **can never fire**: the
branch runs only when the copy is not credible, so the bytes are presumed wrong. A test requiring
them to match would turn the bypass into a no-op and restore the `_1.jpg` duplication it exists to
prevent.

And the deeper half: **content cannot prove ownership when the content is wrong.** A hash proves
the bytes differ from the record; it cannot say whether they are our corpse or a stranger's file.
The hash identifies a file only when the file is intact - exactly when overwriting is unnecessary.

**What content CAN settle is whether destroying them is a loss.** Before overwriting, hash the
occupant; if the catalog accounts for those bytes, refuse and say so. A refusal, not a permission -
the only question a hash of a wrong file can answer.

**Three outcomes**, cheapest first, in `_reclaimable_target`:

| at the recorded path | outcome |
|---|---|
| empty, absent or unreadable | **repair.** Zero bytes is not a photograph and is never read |
| already the bytes we were going to write | **leave it.** Reachable because `credible_copies` compares sizes *by path* (`(alb)` item 9) |
| a photograph the catalog knows | **refuse**, and name the file that was kept |
| anything else | **repair** - a corpse, which is what `(aja)` built this for |

## 4. WHERE THE DECISION MOVED, AND WHY

`_free_relative` decides **collisions**; the caller decides **ownership**, because that is where
the catalog is. `_free_relative` can only see strings and was being asked a question strings
cannot answer.

⚠ **`Catalog.copy_relative` is `SELECT relative FROM file_copies WHERE sha256 = ?` - it asks a
CONTENT question and returns a PATH answer**, discarding `copy_sha256` and `size` from the same
row. That one boundary is why everything downstream reasoned by path. `copy_row` returns the row.

⚠ **`content_is_accounted_for` is deliberately broader than the existing `knows_content`**, which
I nearly duplicated before a lint error caught it. That one asks whether this catalog has
*scanned* a photo - a `files` row - and its two callers in `decisions` need it narrow. This one is
asked before an irreversible overwrite, so it reads **both** `files.sha256` and
`file_copies.copy_sha256`: a Takeout bake rewrites the file by design, and asking only the first
would call a baked photograph unknown - which this branch reads as *"safe to destroy"*.

## 5. HOW OFTEN IT FIRES, AND WHAT THE READ COSTS

**Zero times in ordinary use, structurally.** The branch needs a `file_copies` row **and** that
the row failed the size check - a credible row means dedup skips the file and this code is never
reached. So it fires once per damaged or deleted copy. On the maintainer's real catalog, read-only:
**4,933 rows, 0 damaged, 0 missing, 0 open runs.**

Measured on his own photographs: `sha256_file` median **0.58 ms** (median file 0.2 MB); across the
25 largest (6.6-337 MB) median **7.8 ms**, worst **270 ms**. All 836 files of `(aja)`'s scenario:
**1-7 seconds** - and most of those are zero bytes, which are never read at all.

`reclaim._verify` is the precedent: a full re-hash per candidate, twice per run, before an
irreversible delete, because *"a stale `last_verified` is never trusted"*.

## 6. FAIL-LOUD WAS CONSIDERED AND REFUSED

NVIDIA's guidance is to fail loudly rather than silently overwrite, and this is the only
destructive branch in the product - so it was weighed properly rather than dismissed.

Refusing **everything** answers half of `(aja)`'s complaint, which was substantially about silence
(*"Every automatic path reports success"*). But it leaves damaged files with **no repair route at
all**: `recover` needs a second drive, and most users have one. It trades a rare destruction for a
common failure to repair. The content test separates the two cases, so both halves are kept: the
corpse is repaired and the stranger is refused.

⚠ **And the refusal had to be made loud in the right place.** The first version put the sentence
in `ActionResult.detail` - which on an `--apply` run goes to `last-run.json` and nowhere a person
looks. `ActionResult.overwrite_declined` is the selector and `KEPT, NOT OVERWRITTEN` the labelled
block, following `metadata_ok`'s own rule: *"Selected on the field, never by matching the prose in
`detail`."* On **stderr**, which is `_print_capped`'s ruling, citing clig.dev.

## 7. VACUITY CHECK - 12 MUTATIONS, 12 CAUGHT

Three survived first, and all three were **tests passing for the wrong reason**:

| survivor | why |
|---|---|
| reverting the fold to `==` | the stub destination was **empty**, so `exists` was False and the ordinary path returned the same tuple. The two branches were indistinguishable |
| dropping the already-correct check | the e2e test staged a *credible* copy, so dedup skipped it and the branch was never reached. Moved to a direct test of `_reclaimable_target`, where the input can be stated |
| `fold_case=False` at construction | invisible on ext4 and tmpfs, because the probe answers `False` there anyway - **every CI lane agrees with the mutant**. Closed by asserting the run *asks*, once, and not at all on a dry run |

## 8. WHAT IS NOT DONE

- **The other 15 `(alb)` sites.** Of the 20 physical by-path sites, **5 could decide by content, 9
  cannot, 6 are correctly about a path** - and three of the five need **no extra I/O at all**
  (`dedup.py:226`, `catalog.py:1882`, `catalog.py:1941`: the sha is already in scope or already a
  column). Those are plumbing, not safety.
- **`credible_copies`'s size-keyed lookup**, which is the step *before* this one and shares the
  case hazard. It errs safe by its own docstring (*"it can only cause a re-copy, never a skip"*),
  so it is a cost bug rather than a loss bug - but it is what lets a drifted library arrive here.
- **NFD normalisation** - a different fix, 0 of 13,405 files exposed, still `(alb)`.

⚠ **AND `(alb)` IS INTERNALLY INCONSISTENT, which I wrote and did not check.** It says *"the other
16"*, is headed *"THE OTHER FOURTEEN"*, and carries a **13-row table**. The 16 came from 20 − 4 on
*physical lines* while the table groups them. The standing rule is that a census is re-run before
it is acted on; this one was not, by its own author, one day later.
