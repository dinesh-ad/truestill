# (ael) NO CLI ROUTE COPIES A LIBRARY TO A SECOND DRIVE WITHOUT A SOURCE FOLDER.

*Body of backlog entry `(ael)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ael) NO CLI ROUTE COPIES A LIBRARY TO A SECOND DRIVE WITHOUT A SOURCE FOLDER.** Filed
  2026-08-20 alongside `(aei)`'s fix, which closed most of this gap. **Filed now, built later** -
  what remains is smaller and differently shaped than it looked.

  ## WHAT `(aei)` ALREADY CLOSED

  Before it, the CLI had **no way at all** to put a library on a second drive: `organize` into a
  fresh destination copied nothing, and `backup_run` has no CLI caller - `POST /api/backup/run` is
  the only route, and `truestill-cli` cannot import `truestill_app` (`IMPLEMENTATION_STANDARDS`
  §2). ⚠ That mattered because `drive.py:116-131` records a drive *"registered and used entirely
  from the CLI"* as the **normal** state for this product.

  Since `(aei)`, `truestill organize <source> <second-drive> --apply` **is** the CLI's second-copy
  route for the ordinary case, and it is measured: 4,105 files onto a fresh second drive, after
  which `status` reads *"All catalogued content has at least two drive copies."*

  ## WHAT REMAINS

  **Drive-to-drive, with no source folder in hand.** The app's Backups screen copies drive A to
  drive B; the CLI can only re-organize from the original import folder. Those differ whenever:

  - the source folder is **gone** - deleted after the first organize, which is the normal end state
    for an import;
  - the source folder is **not what is on the drive** - the drive holds an organized layout that
    later runs, renames or trip-naming have changed, so re-organizing the source reproduces a
    *similar* library rather than **that** one;
  - the user wants to copy **a drive**, which is how the operation is actually thought about.

  ## WHAT IS NOT DECIDED

  - **Whether it is a new command or a flag.** `truestill backup <from> <to>` reads plainly;
    `truestill drives --copy-to` keeps drive operations in one place. Not ruled.
  - **Where the logic lives.** `service/backup.py:backup_run` is app-side and the CLI cannot import
    it, so this is a **move to core** with two callers, not a new implementation. ⚠ Doing it as a
    second implementation would recreate exactly the split `(aei)` was about - one surface right,
    another quietly wrong - which is `ENGINEERING_STANDARD.md` §4's fifty-sixth member.
  - **Progress and cancellation on the CLI**, which the app gets from its job runner.
