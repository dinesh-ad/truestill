# (aii) ONE PHOTOGRAPH FIFTY-TWO TIMES IS FIFTY-ONE SENTENCES, SCATTERED THROUGH A 24,000-LINE LIST.

*Body of backlog entry `(aii)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aii) ONE PHOTOGRAPH FIFTY-TWO TIMES IS FIFTY-ONE SENTENCES, SCATTERED THROUGH A 24,000-LINE
  LIST.** Filed 2026-08-29 (P131, soak eight), measured.

  ## MEASURED

  On a duplicate-heavy library (8,970 files, 2,530 distinct contents, ext4), `organize` preview
  produced a **45,653-line** report, of which:

  | section | lines | for |
  |---|---|---|
  | EXACT DUPLICATES | **24,628** | 6,156 duplicates |
  | NEAR-DUPLICATES | **14,898** | 1,655 |

  The largest identical group was **52 files of one photograph**. The product skipped 51 correctly
  and said so **51 separate times**, each block naming the same twin:

  ```
    IMG_0001.JPG  [SKIP: exact duplicate]
        already here : .../DriveA/Full/IMG_20190919_234224.jpg
        via          : SHA-256, earlier in this batch
  ```

  🔑 **THE COUNTS ARE RIGHT AND THE LIST IS UNREADABLE, AND THOSE ARE DIFFERENT PROPERTIES.**
  `SUMMARY` says *"skipped (exact dup): 6,156"* and *"identical copies: 6,156 file(s),
  15,005,062,610 bytes not copied"* - correct, legible, and the number a user needs to trust the
  run. What no surface can say is *"this photograph appears 52 times"*, because **there is no group
  concept anywhere**: `DedupIndex._by_sha` is `dict[str, str]`, one path per content, and every
  match is pairwise against the first-seen twin. The 52 entries are not adjacent; they are
  distributed through the section in scan order.

  ## SCOPE - WHAT THIS IS NOT

  - **Not a correctness defect.** Every skip was right; soak eight reconciled 6,436 implied skips
    against 6,440 expected.
  - **Not the app's 200-row cap.** `DUPLICATE_SAMPLE_LIMIT` truncates honestly and carries `total`
    beside it. This is the **CLI's uncapped** list, which truncates nothing and is therefore
    unreadable for the opposite reason.
  - ⚠ **Not `(aag)`, and the difference is what makes this fileable.** `(aag)` proposes a review
    surface for near-duplicate *grouping and burst review*. This is narrower: an **exact** group is
    not a judgement call - the members are byte-identical, so grouping them needs no threshold, no
    review and no user decision. It is a reporting shape, not a feature.

  ## WHAT WOULD FIX IT, NOT PROPOSED AS A BUILD

  The information is already computed - `DuplicateMatch.matched_path` is the group key by
  construction, since every member names the same first-seen twin. Collapsing on it would turn 51
  blocks into one line reading *"51 more copies of this photograph"*. Whether the CLI should do
  that, and whether `stats.py` should be able to report exact duplicates at all (today
  `"exact_duplicates_found": None`, because skips are **not stored in the catalog**), are two
  separate rulings.

  ## RELATED

  `(aag)` (near-duplicate review surface - adjacent, not this), `(ahq)` (*"there is no review
  queue"*), [`soak-eight-record.md`](../../soak-eight-record.md) §6.
