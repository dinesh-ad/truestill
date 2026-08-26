# (aib) THE PERCEPTUAL PIXEL CEILING IS 600 MP, NOT THE 300 MP THE CONSTANT NAMES.

*Body of backlog entry `(aib)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aib) THE PERCEPTUAL PIXEL CEILING IS 600 MP, NOT THE 300 MP THE CONSTANT NAMES.** Filed
  2026-08-26 (P116), split out of `(ahq)`'s comment audit. **A ruling, not a fix** - the comment
  is corrected; the number is not.

  ## WHAT IS TRUE

  `hashing.py` sets `MAX_PERCEPTUAL_PIXELS = 300_000_000` and assigns it to
  `Image.MAX_IMAGE_PIXELS`, then says an image above it "is *skipped* for perceptual hashing
  rather than risking an OOM".

  **Pillow's `_decompression_bomb_check` is TWO tiers.** It *warns* above `MAX_IMAGE_PIXELS` and
  only *raises* above **2x** it. So the constant sets the **suspicion** line and the refusal is at
  **600 MP**: an image between 300 and 600 MP is warned about and hashed anyway.

  ⚠ **The test already knew and the comment did not.** `test_hashing.py` monkeypatches the limit to
  100 and uses a 144-pixel image annotated `# 144 px -> warn band (100..200)`. The doubling is
  explicit in the test that exercises it and absent from the constant it tests.

  ## Q699 - WHICH IS THE INTENT? NEITHER IS ESTABLISHED, AND THAT IS THE RULING

  Two readings, and the entry refuses to prefer the rounder number:

  1. **The constant means what it says** and the doubling is a Pillow implementation detail nobody
     meant to inherit - in which case the fix is `Image.MAX_IMAGE_PIXELS = MAX_PERCEPTUAL_PIXELS // 2`
     and the effective ceiling becomes the documented one.
  2. **The constant is the suspicion line** and 600 MP was always the intended refusal - in which
     case it is **misnamed**, and `MAX_PERCEPTUAL_PIXELS` should say so.

  **Nothing in the repo decides between them**, checked: no entry, no research document and no test
  states an intended ceiling in megapixels.

  ## Q700 - WHAT THE CEILING IS FOR, read rather than assumed

  Pillow's own code names it: a **decompression-bomb DoS guard**, deliberately two-tier - suspect,
  then refuse. **It is not memory sizing.** So *"300 MP is too low on a 30 GiB machine and too high
  on a small one"* is the wrong frame: this is a fixed policy about untrusted input, and
  `hashing.py`'s own opening sentence already argues the local-library case for raising it.

  ⚠ **The stated purpose in `hashing.py` is OOM ("rather than risking an OOM"), and Pillow's is a
  bomb guard.** Those are different reasons for the same number, and whichever survives decides
  whether the value should track available memory or stay fixed. **That is the ruling this entry
  owes.**

  ## Q701 - IS IT EVER REACHED? YES, AND ONLY BY WHAT IT EXISTS FOR

  Measured 2026-08-26 across the real library and both format corpora:

  | | |
  |---|---|
  | largest **real photograph** | **39.5 MP** (a Pentax file) |
  | files claiming **> 300 MP** | **5**, all in `metadata-extractor-images/tif/ImageTestSuite` |
  | of those, claiming **> 600 MP** | **5** - every one is *raised*, none is merely *warned* |

  The extreme case is `m1-108af7a96a2efa82a0cee0f200e6b9a2.tif`: **1.4 MB on disk claiming
  800 x 3,036,676,696 pixels**. A textbook decompression bomb, in the deliberately-fuzzed corner of
  a corpus that carries 1,461 fuzzed files.

  🔑 **So the 300-600 MP band is EMPTY in practice**, and the false comment has had no observed
  consequence. The ceiling is reached only by fuzzed input, which is exactly what a bomb guard is
  for. **Rank it accordingly** - this is a correctness-of-record problem, not a live hazard.

  ## RELATED

  `(ahq)` (whose comment audit found it), `(aev)` (the other hashing-path hazard).
