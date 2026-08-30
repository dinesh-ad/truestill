# (aiu) TWO CORPUS SHAPES CANNOT REACH THE DEFECTS THEY WERE BUILT FOR.

*Body of backlog entry `(aiu)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P148, soak nine). `ENGINEERING_STANDARD.md` §4's silent instrument, twice - a
shape that runs, passes, and tests nothing.

## 1. THE LONG-NAME SHAPE IS SKIPPED BEFORE ITS NAME IS EVER COMPOSED

`_s13_deep_nesting` emits two long-named files, and P146 deliberately moved them to **204 B and
244 B** so they straddle the ~219-byte budget `(aid)` is about. Measured in soak nine: **neither
reaches the check.**

Both are copies of ordinary sampled photographs, so their **content appears 22x and 18x elsewhere
in the corpus** - and `organizer._organize_each` skips an exact duplicate **before** it composes a
name. Correctly: a file that is never written has no name to check. So the shape straddles the
**byte boundary** and never touches the **code path**.

🔑 **P146's change was necessary and not sufficient**, and a soak that only reported *"no
name-budget refusals"* would have been right about the number and wrong about why. `(aid)` had to
be verified with six constructed, unique-content names instead - which found the boundary exactly
where `layout.name_shortfall_bytes` computes it, but from outside the corpus.

**The fix shape**: give the long-named files **unique content** (re-encode, as the `stripped` and
`resized` shapes already do) so dedup cannot claim them first.

## 2. THE CORPUS HOLDS ZERO NON-ASCII PATHS

Measured over all 8,951 files: **none**. So the corpus cannot exercise the encoding seam at all -
`(aic)`'s exiftool door, or the filename decoding P145 hardened elsewhere.

⚠ **This is the gap `(aid)`'s own table already recorded about the suite** - *"a non-ASCII
filename **on disk**: zero in the whole suite. The one Unicode fixture is lexical - a string in a
test, never a file."* The messy corpus was the obvious place to close it and does not.

Soak nine verified the seam with five constructed names (Greek, Cyrillic, CJK, Latin-1,
astral-plane emoji); all five keyed correctly through exiftool and organized with their names
intact. **That is evidence about the product and none about the corpus.**

**The fix shape**: a shape that copies a handful of sampled photographs under non-ASCII names.
Cheap, and it makes every future soak carry the case.

## ⚠ WHY THIS IS ONE LETTER AND NOT TWO

Both are the same failure of the same file: **a shape whose subject it cannot reach**. Splitting
them would file the mechanism twice and let either be closed while the other stood.

## RELATED

`(ait)` (the sibling: the manifest's own arithmetic), `(aid)`, `(aic)`,
[`soak-nine-record.md`](../../soak-nine-record.md) §4 and §6.
