# (aih) A PHOTOGRAPH WHOSE EXIF WAS STRIPPED IS FILED A YEAR FROM ITS OWN TWIN, AND THE PRODUCT ALREADY KNOWS THEY ARE THE SAME.

*Body of backlog entry `(aih)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aih) A PHOTOGRAPH WHOSE EXIF WAS STRIPPED IS FILED A YEAR FROM ITS OWN TWIN, AND THE PRODUCT
  ALREADY KNOWS THEY ARE THE SAME.** Filed 2026-08-29 (P131, soak eight), **measured on 500 pairs**.

  ## MEASURED

  Corpus: `make_messy_corpus.py`, seed 20260829, 8,970 files / 18.7 GB, ext4. Of 500 EXIF-stripped
  copies placed beside their dated originals, **500 landed in a different folder. Zero landed
  together.**

  ```
  original: 2019/2019-09/2019-09-19 - Everyday/20190919_234225_IMG_20190919_234224.jpg   [exif]
  stripped: WhatsApp/Undated/IMG-20190712-WA0000.jpg                                     [none]
  ```

  🔑 **AND THE PAIRING ALREADY EXISTS.** The same run's perceptual tier matched **499 of those 500
  at Hamming distance ≤ 5, and 427 at distance 0** - the pixels are untouched, so the dHash is
  usually bit-identical. The product holds, at the same moment, a file it cannot date and a file it
  has proved is the same photograph. **Nothing consumes the link**: `dates.resolve_capture_datetime`
  never reads `near_duplicate`, so the tier that knows is not the tier that asks.

  ## WHY THIS IS THE OPENING RATHER THAN A COMPLAINT

  Every incumbent gets this wrong and none of them has the pair:
  - **Immich #8661** files an EXIF-less photo at its **upload** date, and web and mobile disagree.
  - **PhotoPrism #1102** puts every WhatsApp photo on the **1st of the month**.
  - An Immich maintainer answers that bad WhatsApp metadata *"is to be expected"*.
  - **LibrePhotos** alone has a real answer - configurable date rules with priorities, which is our
    `models.DateSource` ladder made user-editable.
  - `whatsapp-media-tools` exists as a **separate repository** solely to restore dates from
    filenames and delete duplicates: a gap the whole field left to a third-party script.

  **Nobody propagates a date from a duplicate that has one.** Truestill is one step from it.

  ## WHAT IS NOT ESTABLISHED, AND MUST BE BEFORE ANYTHING IS BUILT

  - **What tier a propagated date would occupy.** It is not `EXIF` - the file has none - and it is
    not a guess either. `models.DateSource`'s ladder is ordered by *what the evidence is*, so a new
    member has to say what it is evidence OF, and `date_source`/`date_tag` must record which twin
    it came from or the provenance strip lies.
  - **Which direction, when both have dates and they disagree.** Undecided; the safe first cut is
    to propagate only into `DateSource.NONE`.
  - **The false-pair risk, which soak eight measured at ZERO** - no perceptual hash was shared by
    two genuinely different photographs across 1,860 derived pairs and 2,519 organized files (the
    only shared hashes are the degenerate poles `(ahq)`'s floor already refuses). That measurement
    is what makes propagation arguable at all; without it, inheriting a date from a look-alike
    would be a way to date a photograph from a different one.
  - ⚠ **A near-duplicate is NOT the same photograph, and soak eight has the measured instances.**
    An all-pairs sweep at threshold 5 over 2,491 organized files found **two burst pairs**:
    `IMG_20200714_213432_Bokeh.jpg` ↔ `..._213435_Bokeh.jpg` at distance 2-3, and
    `DSC_2141.JPG` ↔ `DSC_2142.JPG` at distance 4-5. **Different photographs, seconds apart,
    inside the threshold.** So propagation must be scoped so a burst member cannot lend its
    identity to its neighbour - propagating only into `DateSource.NONE` still holds, since a burst
    member has EXIF. Distance ≤ 5 is a resemblance, and `hashing.DEFAULT_PHASH_THRESHOLD`'s own
    docstring says the number *"rests on nothing"* and is inherited rather than chosen.

  ## RELATED

  `(aac)` (a unique-size file gets no sha256, so the exact tier never sees it), `(ahq)` (the
  no-signal floor and the unre-derived threshold), `(abf)` (dates the user can see are wrong),
  [`soak-eight-record.md`](../../soak-eight-record.md) §4, [`takeout-format.md`](../../takeout-format.md).
