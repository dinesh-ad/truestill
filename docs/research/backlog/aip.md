# (aip) MIGRATE AND BACKUP KEEP A COPY WHOSE METADATA WAS REFUSED AND NEVER SAY SO.

*Body of backlog entry `(aip)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aip) MIGRATE AND BACKUP KEEP A COPY WHOSE METADATA WAS REFUSED AND NEVER SAY SO.**
  Filed 2026-08-29 (P143). **The residue of `(aie)`, named rather than folded into it.** That fix
  reached `relocate` and `backup` for free - `relocate` through `copy_leaving_nothing`, `backup` through
  `safe_copy.py:StagedCopy.commit` directly (corrected 2026-09-02, P190; this said both went through
  `copy_leaving_nothing`), and either way the fact is on the outcome and discarded at
  `backup.py:_copy_verified`'s `return CopyVerdict(written)` - so a
  layout migration onto a mount refusing `copystat` no longer fails every file in the library, and
  a backup no longer discards a verified copy. **Only `organize` reports it.**

  ## WHY ITS OWN LETTER

  `(aie)` shipped the *keep*; this is the *telling*, and they are different work. `upload` returns
  a warning that `organize` folds into `ActionResult.detail` and `metadata_ok`; `relocate` returns
  `None` and reports through `MigrationOutcome`, and `backup` reports through `CopyVerdict`. Three
  outcome shapes, so the plumbing is three separate decisions - and `(ain)`, which shipped in the
  same arc, is about **orphans** rather than about reporting. Folding this into either would mean
  it ships when that one does or not at all.

  ## WHAT A USER SEES TODAY

  A `migrate-layout` onto SMB rewrites every byte of the library, lands every file, and says
  nothing about the timestamps it could not set. A `backup` onto FAT32 does the same. Both are
  **better than before `(aie)`**, where migrate would have failed every file - so this is a
  degradation from silence, not from correctness.

  ⚠ **How much it costs is bounded and should be said plainly**: `models.DateSource` has no
  filesystem-mtime tier and `dates.py`'s `DATE_TAGS` refuses one by name, so nothing Truestill
  decides is computed from a copy's mtime. What is lost is what a *file manager* shows, and what
  another tool syncing the folder might key on.

  ## WHAT IS ALREADY BUILT AND MUST BE REUSED

  `drive_unwritable.metadata_not_preserved_note` is the one home for the sentence, and `(ain)`
  made it the home for **two** routes rather than one. Whatever surfaces this must word it from
  there. `ActionResult.metadata_ok` is organize's selector; migrate and backup need their own
  equivalent on their own outcome objects, not a fourth string to grep for.

  ## WHAT IS NOT ESTABLISHED

  - **Whether `relocate` can even reach it in practice.** A layout migration moves files already
    on the drive, so source and destination share a filesystem - the mount either takes `copystat`
    or it does not, and if it does not, the copy being relocated never had its metadata either.
    **This may be unreachable, which is a real possible answer.** Check before building.
  - Whether `backup`'s `CopyVerdict` should carry it as a field or the loop should count it.

  ## RELATED

  `(aie)` (the keep this completes), `(ain)` (the same arc, a different half), `(aim)` (a summary
  that over-claims - a silent degradation is that class's quieter form).
