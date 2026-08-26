# (ahq) FLAT PHOTOGRAPHS ARE ALL NEAR-DUPLICATES OF EACH OTHER.

*Body of entry `(ahq)`, **shipped 2026-08-26** - the closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(ahq) FLAT PHOTOGRAPHS ARE ALL NEAR-DUPLICATES OF EACH OTHER.** Filed 2026-08-25 (P95, the
  full-library soak). Measured on **10,138** files carrying a perceptual hash, on ext4.

  ## THE MEASUREMENT

  **89 files sit within the default threshold (5) of the all-zero hash `0000000000000000`**, across
  16 distinct hashes. Every one is a near-duplicate of every other **by construction**. Ten of the
  89 are **real photographs from the user's own library**, not corpus material:

  ```
  0000040840400002  Input/IV Bangalore/DSC05501.JPG      (Sony)
  8080000100000000  Input/IV Bangalore/DSCN0407.JPG      (Nikon)
  0000000000000000  Input/Photos-1-001-2019/IMG_20190719_153609.jpg
  ```

  Two different cameras, unrelated frames, reported as near-duplicates of one another.

  ## ⚠ IT IS NOT A BUG IN THE HASHING, AND THAT WAS CHECKED BY LOOKING

  `IMG_20190719_153609.jpg` is 1.36 MB and 3264x2448. **It was opened and viewed**: it is a
  near-black frame - a lens-covered or dark-room shot. So its all-zero dHash is **honest**. dHash
  compares adjacent pixels; on a surface with no gradient every comparison is equal and the hash is
  all zeros *correctly*. Every flat image lands on the same value regardless of what it is a
  photograph of.

  🔑 **So this is dHash's inherent behaviour meeting a real library, not a defect in
  `hashing.py`.** Filing it as a hashing bug would send someone to fix code that is right.

  ## THE NULL, AND ITS CHECK

  ⚠ **Nothing in the product or the documents addresses low-variance images.**
  `grep -rn "flat\|variance\|all-zero\|uniform\|blank"` over `hashing.py` returns **one** line, and
  it is about *flatbed scans* - a different sense of the word. `grep -rln "flat image\|low
  variance\|all-zero hash"` over `packages/*/src` and `docs/*.md` returns **nothing**.
  `PERFORMANCE.md` documents the O(n²) cost of this comparison and says nothing about what it
  returns.

  ## ⚠ FOUR CORRECTIONS AND THE SHAPE, 2026-08-26 (P115/P116)

  **1. THERE IS NO REVIEW QUEUE, and this entry says there is.** *"That queue is where these land"*
  is wrong: there is a count, an uncapped CLI printout, and a 200-item browser `<details>`
  disclosure with **no buttons and no actions**. At 827 flagged, **627 are never named in the
  browser at all**. That does not soften the harm - it sharpens it. **A wrong pair is shown and
  cannot be dismissed.**

  **2. BOTH POLES. The all-ONE hash is equally degenerate** - dHash compares each pixel with its
  right neighbour, so a gradient-free image gives all zeros and a monotonic left-to-right gradient
  gives all ones. Measured: **8 more files within 5 of all-one** (7 distinct), and the real
  photograph count is **13**, not 10. A floor written against zero alone would have left the mirror
  case open.

  **3. NOTHING DESTRUCTIVE CONSUMES THIS SIGNAL, and that caps the entry.** Seven delete paths,
  every one keyed on SHA-256 or a filename; eleven `DELETE FROM` statements, **zero** keyed on
  `perceptual`; `should_upload` is `exact_duplicate is None` and structurally cannot see the field;
  `reclaim` has no app route. **A flat-frame false positive cannot cost a photograph.** The harm is
  trust, and it was ranked as trust.

  **4. TWO DEFINITIONS OF "NEAR-DUPLICATE", one word, neither citing the other.** The run's count is
  a Hamming distance within the threshold; the browser headline is `GROUP BY perceptual` - **exact
  string equality, no threshold**. Different populations. 🔑 **Fourth instance in a week of one
  concept defined twice**, after `(ahu)`'s two setter spellings, `(ahw)`'s three definitions of
  "Camera" and `(ahz)`'s two trip keyings. ⚠ **Recorded, and deliberately NOT resolved**: unifying
  them changes what the headline counts on every library, and needs its own before/after
  measurement.

  ## THE SHAPE THAT SHIPPED - DERIVED, NOT PICKED

  🔑 **The Hamming distance from a hash to all-zero IS that hash's bit population.** So *"within the
  matching threshold of all-zero"* is exactly `bit_count(h) <= threshold` - **the floor is the
  threshold**, whatever the caller sets, including a user-supplied `--phash-threshold`. No constant
  was invented. Symmetric: `min(popcount, 64 - popcount)`.

  **Measured on this library**: 97 of 10,138 excluded (0.96%) - 89 on the zero side plus 8 on the
  one side, reconciling exactly. Headline **415 -> 336**, five groups, **19%**.

  **Cost, stated rather than assumed away.** 13 real photographs are excluded, and
  `IMG_20150901_123909` and `IMG_20150901_123912` - three seconds apart - **pair today at distance
  3**. ⚠ **That is not lost evidence; it was never evidence.** Both hashes carry **four set bits**,
  so a distance of 3 means agreement on one or two bits of sixty-four. The pair is right for a
  reason the hash cannot see, and the hash should not take the credit.

  ⚠ **Applied at BOTH sites**, because fixing only the index would have left the headline - where
  the defect was most visible - unchanged.

  ## ⚠ THE THRESHOLD'S OWN RATIONALE WAS VOID

  `hashing.py` justified the number 5 by an asymmetry that **cannot happen**: *"a false positive
  means a real, distinct photo is treated as a duplicate and never backed up (silent data loss)"*.
  A perceptual match does not suppress the copy - `models.Resolution` says so as policy. The
  asymmetry is **inverted** here: a false positive costs a wrong row in a list nobody can act on, a
  false negative costs a redundant kept copy, and neither is data loss.

  🔑 **So the number rests on nothing. That is not the same as being wrong** - 5 may well be right,
  but the reasoning that produced it was about a different failure, and **nobody has re-derived it
  against the harm that actually applies.** Recorded rather than changed.

  ## ⚠ AND THE GUARD'S OWN COMMENT NAMED THE DEFECT IT MISSED

  `dedup.py`'s `None` guard warns of *"the whole library collapsing into one match, silently"* - a
  description of exactly what was measured here. It tested **provenance** (`is None`) and never
  **value**, so the synthetic route was closed and the photographic one was open. A photograph of a
  flat surface produces an *honest* all-zero hash and walked straight past it.

  ## ⚠ SIX TEST FILES, AND THREE OF THEM DID NOT KNOW

  Three already constructed noise deliberately and said why. **Three more tripped over it while
  this shipped**: two synthetic fixtures generating low-population hashes, and - the sharpest of
  them - `conftest._gradient`, the repo's canonical *"the perceptual-duplicate case the near-dup
  tier exists to catch"* fixture, which was a **monotonic left-to-right ramp** hashing to
  `ffffffffffffffff`. **It paired only because two copies of nothing are equal.** Given structure,
  it now hashes at popcount 35 and 34 and still pairs at distance 1.

  ## THE HARM, STATED CONCRETELY

  A user shown two unrelated photographs side by side as duplicates **stops trusting every pair the
  product reports, including the true ones**. Near-duplicate review is a feature whose entire value
  is the user's willingness to act on it; a single obviously-wrong pair costs more than the 88
  correct ones earn. The organize run flagged **827** files as near-duplicates *kept and flagged for
  review* - that queue is where these land.

  ## WHAT THIS ENTRY DOES NOT DECIDE

  Whether the answer is a variance floor below which no perceptual hash is recorded, a distinct
  sentinel for "too flat to compare" (the shape `unreadable` already uses - **476** files were
  excluded from near-duplicate comparison in the same run and *reported as excluded*), or leaving
  it and saying so in the review copy. **The third is a legitimate answer** and is why this is a
  letter rather than a fix.

  ## RELATED

  `(adp)` (the precedent: a third of a real corpus wrong, found only by rendering real
  photographs), [`soak-five-record.md`](../../soak-five-record.md) (the run that found it),
  `PERFORMANCE.md` §3 (the cost of this comparison, not its correctness).
