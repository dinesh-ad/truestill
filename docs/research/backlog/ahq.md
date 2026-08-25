# (ahq) FLAT PHOTOGRAPHS ARE ALL NEAR-DUPLICATES OF EACH OTHER.

*Body of backlog entry `(ahq)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
