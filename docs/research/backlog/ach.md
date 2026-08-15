# (ach) `ApplyReport.skipped_newer_locally` carries two meanings that need opposite words.

*Body of backlog entry `(ach)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ach) `ApplyReport.skipped_newer_locally` carries two meanings that need opposite words.**
  Recorded 2026-08-09 from code. Deferred **to Stage 4 deliberately**, where the multi-drive
  merge builds the reporting this feeds - Stage 4 widens the channel rather than inventing it.
  - `decisions.py`'s `date_confirmations` loop appends the same field from two branches: one when
    a local confirmation is **newer** (refused, correctly), one when the catalog has **never
    scanned that content**. Nothing is newer in the second case and nothing is overwritten.
  - **The user actions are opposite.** "Your machine has a later correction, the drive's was
    ignored" needs no action. "This drive holds a correction for a photo you have not scanned"
    means: scan the other drive, re-apply. `dict.fromkeys` then collapses both to one entry, so a
    restore hitting both reports one indistinguishable line.
  - The field's own docstring documents only the first meaning, which is how it stayed invisible.
    `(ack)`'s fix added two single-meaning fields rather than a third overloaded one; do the same
    here.
