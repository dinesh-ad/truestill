# (aff) ONE EXTRA NEAR-DUPLICATE ON 3.14, FROM THE INTERPRETER AND NOT FROM A DEPENDENCY.

*Body of backlog entry `(aff)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aff)** Found 2026-08-22 by the Python 3.14 upgrade's **step 3**, which existed to check
  `--pool process` under forkserver. That check passed; this is what it found beside it.

  ## MEASURED, on the format corpus (1,324 organizable files)

  | interpreter | pool | look-alikes |
  |---|---|---|
  | 3.13.13 (`fork`) | thread | **262** |
  | 3.13.13 (`fork`) | process | **262** |
  | 3.14.4 (`forkserver`) | thread | **263** |
  | 3.14.4 (`forkserver`) | process | **263** |

  Two runs each, stable. ✅ **The property step 3 was run for HOLDS: the two pools agree exactly,
  on both interpreters.** The cross-version delta is one file in 1,324.

  ## WHAT IT IS NOT - both ruled out by measurement, not by reasoning

  - **Not a dependency change.** The relock moved **nothing**: every package version in `uv.lock`
    is identical before and after. Diffed programmatically, not eyeballed.
  - **Not a walk-order change.** `scan_source().media` returns the same 1,324 files in the same
    order on both interpreters - compared by hashing the joined name list, identical digest
    (`807184b44810e01e`). Near-duplicate classification *is* order-dependent, since whichever
    cluster member is seen first becomes the index entry, so this was the leading hypothesis and
    it is dead.

  ⚠ **The mechanism is NOT isolated, and that is stated rather than implied.** Same Pillow, same
  numpy, same imagehash, same file order - and one more file crosses the Hamming-distance
  threshold. A boundary case flipping by one bit would explain it; nothing has been measured that
  shows which file, or why.

  ## WHY IT DID NOT BLOCK THE UPGRADE

  **A near-duplicate is kept and flagged, never removed** - `resolve`'s policy, and the reason the
  asymmetry exists: *"an original can never be silently dropped in favour of a lower-quality
  look-alike."* The user-visible effect of this defect is **one extra row in a review list**. No
  file is deleted, skipped, or misplaced by it. Exact deduplication - the half that decides
  whether bytes get copied - was **identical across all four runs** (9 identical copies, every
  time).

  ## NOT DECIDED

  - **Which file, and why.** The first step is to diff the two runs' flagged sets and hash the one
    file that differs on each interpreter. That is a morning's work and nobody has done it.
  - **Whether the threshold is the real subject.** `DEFAULT_PHASH_THRESHOLD = 5` is documented as
    deliberately conservative; a corpus where one file sits exactly on the boundary is evidence
    about the threshold's margin, not only about the interpreter.
  - **Whether it is worth a guard at all.** A test pinning "263 on 3.14" would pin a number nobody
    understands, which is the twenty-ninth member. The guard worth having is probably that the two
    POOLS agree - which is what was measured here and is not asserted anywhere.
