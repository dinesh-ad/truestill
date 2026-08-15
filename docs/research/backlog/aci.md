# (aci) A DELETED DECISION BLOCKS DRIVE SAVES UNTIL A RESTORE RECONCILES THEM.

*Body of backlog entry `(aci)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aci) A DELETED DECISION BLOCKS DRIVE SAVES UNTIL A RESTORE RECONCILES THEM.**
  Recorded 2026-08-09 while building the decisions save, as the known false positive of its
  loss guard. Closed by restore; recorded so it is not rediscovered as a bug.
  - The save refuses to write a document that would lose decisions the drive already holds, which
    is what protects a re-attached drive from a rebuilt catalog. **A decision the user deleted
    locally looks identical**: the drive still carries it, so every later save reports
    `WOULD_LOSE` and the drive's copy stops being updated.
  - **Reported, never silently resolved.** Guessing which side is intentional is how the other
    direction loses data, and the other direction is unrecoverable.
  - **Restore closes it**: once the two can be reconciled, the user resolves it once and saves
    resume. Until then the drive keeps the older, larger set - the safe direction.
