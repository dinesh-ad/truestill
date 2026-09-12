# (ako) THREE DELETES DIVERGE FROM THE RE-READ-BEFORE-DELETE STANDARD, AND ONE OVERWRITES ON A CATALOG ROW ALONE.

*Body of entry `(ako)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(ako)** Filed 2026-09-12, from a census of every path that removes or overwrites bytes, run
  while a real external drive was ejected. **No work attached** - this records what was found.

  ## THE STANDARD, WHICH ALMOST EVERYTHING MEETS

  Fifteen paths remove or overwrite bytes. **Every unlink of a user's file re-reads the bytes on a
  CONNECTED medium immediately before removing them.** `reclaim` is not special in this:
  `organize --move` (`organizer.py:_move_source`), the organize rollback (`organizer.py:_roll_back_unrecorded_copy`),
  `migrate-layout`'s main branch (`migrate.py:_apply_move`), `undo-migration` (`migrate.py:_reverse_one`)
  and `undo-organize` (`undo.py:_identity_check`) all re-checksum first. `recover` and `rescan` remove
  nothing at all and say so in their own module docstrings.

  ⚠ **Nothing deletes on the strength of a copy on an unreachable drive.** That question was the
  one being asked and the answer is clean. What follows is the three places that diverge from the
  standard for other reasons.

  ## 1. `_free_relative`'s `reclaimable` bypass - a catalog row authorises an overwrite

  `organizer.py:_free_relative`, call site `organizer.py:_execute_one_write`:

      if reclaimable is not None and relative == reclaimable:
          return relative, False          # collision resolution SKIPPED; the incumbent is overwritten

      reclaimable = run.catalog.copy_relative(resolution.hashes.sha256, run.drive_uuid)

  **The design is sound and `(aja)` argues it well.** When dedup decides a recorded copy is no
  longer credible - an interrupted write left a zero-byte file where the catalog records 3.5 MB -
  the repair must land **at that path**. Without this it lands beside it as `..._1.jpg`, the drive
  keeps the ruined file and gains a second one, and the row still points at the corpse. The
  docstring also anticipates the obvious objection: *"a stranger's zero-byte file at the same path
  has no such row and is still suffixed around."*

  ⚠ **THE SHARP EDGE IS WHAT ROUTES THERE, NOT THE BYPASS ITSELF.**
  `dedup.credible_copies` judges a recorded copy by **size**, and warns about it in its own words
  (`dedup.py:credible_copies`):

  > ⚠ **Size, not content.** A copy whose size matches and whose bytes are wrong survives this
  > filter - one such file was measured on each of exFAT and NTFS - and only `verify` can find it.

  Read the two together and the residual is this: **a different file that has come to occupy the
  recorded path has a different size, is therefore judged not credible, and is overwritten without
  its bytes ever being read.** The row only exists because Truestill put its own content there, so
  the population is narrow - a user or a restore replacing that file out of band. Narrow, and real.

  **This is the only place in the product where a catalog row alone authorises destroying existing
  bytes.** Everywhere else the authority is a live hash.

  ## 2. `migrate.py:_apply_move` - the resume branch deletes without a live read

      current = catalog.copy_relative(move.sha256, drive_uuid)
      ...
      if current == move.new_relative:      # catalog already flipped
          if move.old_relative != move.new_relative:
              destination.remove(move.old_relative)

  The gate is **a catalog read**. There is no `exists`, no `checksum` of `new_relative` on this
  branch. The argument is that the flip only happens after a verify earlier in the same function,
  so the row implies a past verify - but the row is what is consulted, and the main branch four
  lines down (`migrate.py:_apply_move`) does re-verify. Two branches of one function, two standards.

  ## 3. `migrate.py:_matches` - existence-only for a legacy copy, where `reclaim` refuses

      if not destination.exists(relative):
          return False
      if not expected_sha:
          return True      # legacy copy with no recorded hash: existence is the best we can check
      return destination.checksum(relative) == expected_sha

  When `file_copies.copy_sha256` is NULL the gate before removing the old copy is *"a file exists
  at the new path"* - a stat, not a read. `reclaim.py:plan_reclaim` refuses exactly this class:

  > No recorded hash means the re-verify gate cannot be satisfied, and reclaim's whole safety
  > argument is that gate. Counted as unverified, **never offered for deletion**.

  `_reverse_one` has the same weakening at `migrate.py:_reverse_one`: a falsy `expected` skips the
  comparison entirely.

  ## WHY THIS IS FILED RATHER THAN FIXED

  All three are defensible where they stand and none is a live loss. They are recorded because the
  product has ONE standard for destroying a user's bytes - read them first, on a medium you can
  reach - and these are the three places that do not meet it. A standard with three undocumented
  exceptions is how the fourth gets added.

  ## RELATED

  `(aja)` (the credibility filter and the reclaimable bypass), `(ain)` (the self-worsening shape
  the bypass exists to prevent), `(aiy)` (a copy counted as redundancy that was not one).
