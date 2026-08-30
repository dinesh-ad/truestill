# (ait) THE MESSY-CORPUS MANIFEST OVERSTATES ITSELF, AND 20 ROWS DESCRIBE FILES THAT ARE GONE.

*Body of backlog entry `(ait)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P148, soak nine). **An instrument defect, and it is in soak eight's published
evidence too.**

## THE MECHANISM

`scripts/make_messy_corpus.py` builds every destination path from the **basename** of its source -
`f"DriveA/Full/{source.name}"` and fourteen more like it. `/data/TruestillLibrary/Input` holds two
pairs of **different photographs that share a basename**:

| basename | the two distinct sources |
|---|---|
| `IMG_0386.JPG` | `Input/A 6/` and `Input/Mom/kasi/` |
| `Photo0268.jpg` | `Input/A 3/` and `Input/A 11/` |

Each pair therefore collides at **ten** destination paths. The second write overwrites the first,
`CorpusWriter` appends a row for both, and the manifest ends up with **8,971 rows for 8,951
files**. Measured: **all 20 orphaned rows carry a `sha256` that no longer matches the bytes on
disk.**

## WHY IT MATTERS MORE THAN A COUNT

**The manifest is the answer key.** A soak computes *"expected exact-duplicate skips"* from it and
then scores the product against that number. Twenty rows describing files that do not exist, with
hashes that are not there, move the expected figure - so the product can be scored against a total
it could never have produced, in either direction.

⚠ **Soak eight ran the same seed against the same source**, so its recorded **8,970 files** and
the answer key derived from it carry this error. Soak nine worked around it by **hashing the
corpus** and using the manifest only for provenance, keyed by path with the surviving row - which
is a workaround in the analysis, not a fix in the instrument.

## THE FIX SHAPE, NOT RULED

Two candidates, and the choice is a real one:

1. **Make the destination unique** - qualify the path with a short digest of the source, or with
   its parent folder. Keeps every sampled photograph, changes every path in the corpus.
2. **Refuse the collision** - have `CorpusWriter` raise when a path is written twice. Loudest,
   smallest, and turns a silent 20-row lie into a build failure someone must decide about.

⚠ **(2) alone would have failed this build**, which is the argument for it: the generator already
knows enough to notice, and chose to keep writing. `test_the_corpus_grows_with_the_sample` guards
the scale half of this file; nothing guards path uniqueness.

## RELATED

`(aiu)` (the sibling: shapes that cannot reach their subject),
[`soak-nine-record.md`](../../soak-nine-record.md) §1 and §6,
[`soak-eight-record.md`](../../soak-eight-record.md) §1-2 (the evidence this corrects).
