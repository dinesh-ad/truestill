# (aht) THE ARCHIVE STAGING TREE IS NEVER REMOVED.

*Body of backlog entry `(aht)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aht) THE ARCHIVE STAGING TREE IS NEVER REMOVED.** Filed 2026-08-25 (P98, soak six), found
  while reading `(ahp)`'s artifact rather than by reasoning about it.

  ## MEASURED, AND THE MEASUREMENT CHANGES THE RANK

  Ingesting the real **1.61 GB / 534-entry** archive leaves `.truestill-staging/` under the
  destination holding **535 files, 1.6 GB** - beside the 1.6 GB organized copy. **Nothing removes
  it**: `grep -iE "rmtree|unlink|clean"` against `archive_ingest.py` returns nothing.

  ⚠ **A second ingest of the same archive does NOT stage again.** Measured: still **535 files,
  1.6 GB**, one directory, same path re-used. **So N ingests of one archive cost 1x, not Nx** -
  this is untidiness, not a disk a user runs out of, and it is ranked accordingly.

  ⚠ **But the work IS repeated**: the second run unpacked all 534 files again (2.85 s of it). The
  staging tree is neither cleaned up nor treated as a cache.

  **The cost is per distinct archive**, not per ingest: two different archives leave two trees.

  ## WHY IT IS DEFENSIBLE AS IT STANDS

  Organize ran in **copy** mode, and copy mode never deletes a source. The staging tree *is* the
  source for that run, so leaving it is consistent with the rule that protects a user's files. The
  question is whether a product-created intermediate deserves the same protection as a user's own
  folder.

  ## WHAT THIS ENTRY DOES NOT DECIDE

  Delete after a verified organize, keep and re-use it as a cache (which would make the second
  ingest fast rather than merely idempotent), or keep and **say so** so the space is expected.

  ## RELATED

  `(ahp)` (the crash whose artifact this was found in), `(ags)` (staging under the destination),
  [`soak-six-record.md`](../../soak-six-record.md).
