# (ady) NOTHING COPIES THE CATALOG BEFORE A MIGRATION CHAIN RUNS.

*Body of backlog entry `(ady)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ady) NOTHING COPIES THE CATALOG BEFORE A MIGRATION CHAIN RUNS.** Recorded 2026-08-19, split
  out of `(adl)` while correcting that entry. **Split rather than folded in, because a
  transactional fix would otherwise read as covering this and it does not.**
  - 🔑 **THE DISTINCTION, and it is the whole entry.** A transaction restores what a **failed**
    step touched. It cannot restore what a **successful** step deliberately removed. A migration
    that drops a column, or rewrites a value, and then commits, has destroyed that data
    *correctly* - and no rollback, no per-step transaction and no lock brings it back. `(adl)`'s
    routes all close *interruption*; none of them closes *intent*. ✅ **`(adl)` shipped 2026-08-19**
    with the per-step transaction, and this is exactly what it did not touch.
  - **What exists today.** Nothing. `Catalog._migrate` runs the chain against the user's live
    file. There is no copy, no snapshot, and no way back to the pre-upgrade schema except a
    backup the user happens to have made themselves.
  - ⚠ **The figure below is the 2026-08-19 reading; re-checked 2026-08-22 and the CLAIM HOLDS.**
    The chain is now **19 forward steps to schema v20**. The two that landed since -
    `_add_copy_missing_at` (v19) and `_add_organize_runs` (v20) - are both additive. The only
    `DROP TABLE` in `catalog.py` is `downgrade_v12_to_v11`, which is **not in the forward chain**
    and is called from one test. So the safety argument is unchanged and only the number moved.
  - **Why it has not bitten.** Checked all 18 migrations: every one is additive - `ALTER TABLE
    ADD COLUMN`, `CREATE TABLE IF NOT EXISTS` - plus one `DROP INDEX IF EXISTS` (v18), which
    removes a redundant index and no data. **So no shipped migration has ever destroyed
    anything.** That is a property of the migrations written so far, not a property of the
    mechanism, and the mechanism is what this entry is about.
  - ⚠ **The first destructive migration is the one that finds this**, and by then the evidence is
    gone. That is the asymmetry worth acting on before rather than after: the cost of a copy is
    paid on every upgrade, and the cost of not having one is paid once, unrecoverably.
  - **What the copy would have to be, stated so the obvious answer is met with its own problem.**
    Not a `shutil.copy2` of the live file: `(adb)` records that copying a live SQLite database can
    yield *"some old and some new content"*, and `(adr)` records that a copy that fails part-way
    leaves a 0-byte file wearing the catalog's name. The blessed routes are the ones `(adb)`
    already found - `VACUUM INTO` or the backup API - so **this entry inherits `(adb)`'s
    conclusions rather than re-deriving them.**
  - **Unanswered, and not answered here:** when the copy is taken (every open that migrates, or
    only when the chain is non-empty), where it goes, how many are kept, when they are removed,
    and what a user is told about them. A copy nobody prunes is a disk-filling feature; a copy
    nobody is told about is a file they delete.
  - **Related, and deliberately not merged.** `(adl)` - interruption and concurrency in the same
    chain, **shipped 2026-08-19** (`SHIPPED.md`), whose remedy does **not** cover this. `(adb)` - how to copy a live catalog safely, and
    the only part of this problem already solved. `(adr)` - what a failed copy leaves behind,
    which is the failure mode a pre-migration copy must not introduce.
