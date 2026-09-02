# (aao) Asset pairing: several files that are one photo.

*Body of backlog entry `(aao)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aao) Asset pairing: several files that are one photo.** Recorded 2026-08-02. **Post-launch,
  record only - needs a design pass before any build.** Names the concept that `(y)`, `(p)` and
  `(aag)` have each been circling without one.
  - **The gap.** Truestill treats every file as an independent asset, and several ordinary cases
    are one capture stored as several files: an Apple Live Photo (`.HEIC` + `_HEVC.MOV`), a
    camera shooting RAW+JPEG (`ABC001.ARW` + `ABC001.JPEG`), exported edits (`ABC001-1.JPEG`),
    and bursts. **Neither dedup tier pairs them** - SHA-256 sees different bytes, and RAW or HEIC
    may yield no perceptual hash at all. Verified 2026-08-02: no pairing logic exists anywhere in
    `src`. A Live Photo pair currently survives organize only by the coincidence of a shared
    capture time.
  - **The field has proofs, not just heuristics, and that shapes the tiers.** Both halves of a
    Live Photo carry the same `ContentIdentifier` UUID, and iPhone bursts share a `BurstUUID`;
    those are identifiers, not guesses. RAW+JPEG has no such identifier and is matched on
    basename - PhotoPrism requires *same folder plus same basename* explicitly to avoid scanning
    the library for a partner per RAW, with the counter-proposal being one pass building
    `basename -> paths`. Filename matching alone is unreliable, since differing basenames cannot
    be grouped that way at all. Capture time **corroborates but cannot prove**: Lightroom is
    criticised for ignoring it, and some cameras record *different* times for the two halves of
    one RAW+JPEG pair. The framing worth keeping is that the goal is to find duplicate **images**,
    not duplicate **files**.
  - **Proposed tiers, mirroring the date-provenance design. A proposal, not a decision.**
    (1) *Exact* - shared `ContentIdentifier` / `BurstUUID`. (2) *Strong* - same folder, same
    basename, different extension, corroborated by capture time. (3) *Weak* - export-suffix
    patterns (`-1`, `~edit`). **Tier 1 has a stated cost:** neither tag is in `REQUESTED_TAGS`,
    so adopting it changes `tags_fingerprint` and forces one cold exiftool pass over the library -
    the same cost profile recorded against `GPSAltitude` in `(kk)`. Recorded, not ruled on.
  - **What matters here is custody, not display, and that is where truestill differs from the
    galleries.** Stacking as a *view* is largely irrelevant to a tool that is not a gallery. What
    matters is that an asset survives organize intact. **All three of these need verification
    before building - they are the questions, not findings:** whether both halves land in the
    same folder (the risk `(y)` warns of for a future photo/video split); whether date-based
    renaming severs the basename link when one half gets a collision suffix and the other does
    not; and whether `reclaim` can delete one half of a pair, which is the safety question,
    given `plan_reclaim` checks only that the source *exists*.
  - **Cross-references.** `(y)` calls pairing "the real work" and warns *"do not build the split
    first and pair later"*; `(p)` needs it for share-export; `(aag)` is burst review, which tier 1
    would answer with `BurstUUID` rather than a heuristic.
