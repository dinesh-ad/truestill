# (agv) A BAKE THAT DIES BETWEEN THE WRITE AND THE RECORD LEAVES AN IRREVERSIBLE CHANGE UNRECORDED.

*Body of entry `(agv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agv) A BAKE THAT DIES BETWEEN THE WRITE AND THE RECORD LEAVES AN IRREVERSIBLE CHANGE
  UNRECORDED.** Filed 2026-08-24 out of `(agm)`'s premise check - **found while verifying a
  different entry, and it may outrank the one it was found under.** Not folded into `(agm)`:
  that entry is about a run RECORD, and this is about the catalog disagreeing with the bytes.
  - **The mechanism.** `service/bake.py`'s loop writes with `write_metadata_batch`, then reads
    the file back and calls `catalog.record_bake` in one transaction. A crash, a kill or a power
    loss **between those two steps** leaves the file **baked on disk** and `date_baked_at`
    **NULL** in the catalog.
  - ⚠ **The window is not the same size as the in-place rename's, and that is the whole
    argument.** `(agk)` closed exactly this shape for `--in-place`, where the unprotected span was
    `rename -> catalog row -> journal row`. Here the span contains a **`sha256_file` of the
    file just written** - a full read of a photo, not a metadata operation - so it is orders of
    magnitude wider than a rename. Measured shape, not measured duration: measure before ranking.
  - 🔑 **AND THE ACT IS IRREVERSIBLE, WHICH IS WHY THIS IS NOT BOOKKEEPING.** `bake.py`'s own
    `IRREVERSIBLE_NOTE` states it: exiftool's `-overwrite_original` (`exif._WRITE_FLAGS`)
    replaces metadata in place and **keeps no sidecar**, so *"the date it had before is not
    kept"*. `(bbb)` owns preserving it and is unbuilt. A rename can be reversed; this cannot.
  - **What the wrong state costs.** `confirmations_to_bake` is driven by
    `file_copies.date_baked_at IS NULL`, so the file is offered again and **re-baked** - writing
    the same date over bytes that already carry it. Content-harmless, and the counts are wrong,
    the completeness sentence is wrong, and `copy_sha256` is stale for that copy until the
    re-bake lands, so **`verify` compares against a hash the file no longer has**.
  - **The fix's shape, not designed here**: `(agk)`'s own answer - record the INTENT before the
    irreversible step, and let the disk settle what an unknown outcome means. `undo.plan_undo`
    reconciles against the disk for exactly this reason.
  - ⚠ **Do not fix this together with `(agm)`.** One is a record of a run; this is the catalog
    telling the truth about a file. `(adb)`'s *"do not 'fix' these together"* is the precedent.
