# (abs) The ghost-drive rule refuses REGISTRATION and warns nobody else.

*Body of entry `(abs)`. **CLOSED 2026-08-23** - the closing shape it asked for was built by `(afc)` (`5345500`, 2026-08-21) without naming this letter; instance six of the fixed-under-another-name family. The index is now [`SHIPPED.md`](../../SHIPPED.md).*

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

---

## ✅ CLOSED 2026-08-23 - built by `(afc)` under another name, instance six

**The exact closing shape this entry specified exists**: *"the read-only surfaces do not refuse,
they lead with it"*. `_drive_or_explain` - the shared door `verify` AND `rescan` pass - gained a
ghost branch in `5345500 fix(afc)` (2026-08-21), and both commands now print, verbatim:

> *"...is where Truestill recorded the drive 'Backup HDD', but that drive's marker file is not
> there. The drive is probably not plugged in or not mounted. Anything written here now would go
> onto THIS computer's disk, and would DISAPPEAR from view the moment the drive comes back..."*

Reproduced on scratch, both commands. The listings already spoke the reach vocabulary: CLI
`drives` says `offline`; the app payload carries `"reach": "offline"`, rendered *"(not plugged
in)"* (`app.js:2624`); `where` answers normally while unplugged.

⚠ **AND THIS ENTRY WAS ITSELF A SIXTY-NINTH-MEMBER INSTANCE.** It states *"the two places that
MINT an identity"* - there were **three** when it was written: `attach_drive` (`drives.py:345`)
predates it and mints with no ghost check, reachable `write=True` from `backup_run`. Finishing
this entry's own verification found it, demonstrated it minting a phantom identity at an
unplugged drive's recorded path, and filed it as **`(agr)`**, ranked at the top of the engine
list - the door this entry existed to describe, open on the surface it did not count.
