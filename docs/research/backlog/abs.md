# (abs) The ghost-drive rule refuses REGISTRATION and warns nobody else.

*Body of backlog entry `(abs)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abs) The ghost-drive rule refuses REGISTRATION and warns nobody else.** Recorded
  2026-08-07 with the fix, and **chosen deliberately rather than discovered** - which is the
  point of writing it down. `ghost_drive_at` is called by `_register_destination` (CLI) and
  `service/organize._identity_for` (app), the two places that MINT an identity. `rescan`,
  `verify` and `backup` read markers and never mint, so the data-loss path does not run through
  them and none of them needs the refusal.
  - **But "refuses to register" and "warns you this is a ghost" are different promises**, and
    only the first exists. Point `verify` at a drive whose recorded path is now an empty folder
    and it reports every copy MISSING - true of the record, and it never says the likely reason
    is that the drive is not mounted. `rescan` would call the whole library UNACCOUNTED for the
    same reason. Both are honest and both bury the one fact that explains them.
  - **The shape is the one-site-of-many again** - `(aak)`, `(abq)`, `(abr)`, the nine cancel
    buttons - so it is recorded as a decision with its reason instead of being found later by
    someone wondering why only two callers know the rule. The reason: minting is irreversible
    custody damage, reporting is not.
  - **What closing it looks like:** the read-only surfaces do not refuse, they *lead with it* -
    "this is where drive X was recorded and its marker is gone" before the counts, so the number
    is explained rather than alarming. That is a wording change on three surfaces, not a rule
    change, and it wants `(aba)`'s reconciliation vocabulary rather than its own.
