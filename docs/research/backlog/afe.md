# (afe) A CATALOG THAT GOES UNWRITABLE MID-RUN ABORTS WITH A TRACEBACK AND LEAVES A FILE IT DID NOT RECORD.

*Body of backlog entry `(afe)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afe) THE WORST OF SOAK THREE.** Found 2026-08-21 by **step R5**. Three separate rules broken
  by one unhandled exception.

  ## MEASURED

  120 files, `chmod 555` on the directory holding `catalog.sqlite` once five had landed - SQLite
  must create `-wal` and `-journal` **beside** the database, so this refuses writes without
  touching the file:

  ```
  exit=1
  files on disk : 48
  catalog rows  : 47
  EXECUTED block: NOT PRINTED
  last line the user sees:
      sqlite3.OperationalError: attempt to write a readonly database
  ```

  ## THREE RULES, ONE CAUSE

  **1. §1's partial-failure policy is broken.** *"One bad file never aborts a batch - it is
  logged, counted, and reported at the end."* The batch **aborted**. 72 of 120 files were never
  attempted, and nothing says so.

  **2. §9 is broken in the most basic way: a raw Python traceback is the product's final output**,
  ending in `sqlite3.OperationalError`, with our own file paths and line numbers
  (`catalog.py:2738`, `record_uploaded`). `catalog_busy.py` exists precisely to turn a SQLite
  condition into a sentence; this condition reaches none of it.

  **3. A file is on the destination that the catalog does not know about.**
  `20140805_014501_Kodak PIXPRO FZ201.jpg` was copied and not recorded. That is the state `rescan`
  exists to repair, **reached silently** - because the traceback replaced the report that would
  have said so.

  ⚠ **The 48/47 gap is the copy-then-record ordering doing its job**, and that is worth saying:
  the copy lands *before* the row is written, so a crash between them leaves a file with no row -
  which is the safe direction. A row with no file would be the dangerous one, and it did not
  happen. The defect is that nothing **reports** the gap.

  ## WHY THE DESTINATION SURVIVED THE SAME TEST AND THE CATALOG DID NOT

  R3 refused the **destination** mid-run and every safety property held: catalog matched disk
  exactly, `.partial` was used, a re-run resumed, §1's accounting was complete. The difference is
  where the failure is caught. A destination write is inside the per-file `try` that §1's policy
  is built on; a catalog write is not inside anything.

  ## NOT DECIDED

  - **Whether a catalog write failure should be per-file or fatal.** Continuing to copy files that
    cannot be recorded may be worse than stopping - but stopping must then be a *reported* stop
    with a count, not a traceback.
  - **Whether `catalog_busy`'s vocabulary extends to `readonly database`**, which is a different
    condition from a lock: waiting will never clear it.
  - **Whether the run should re-check the catalog's writability at all**, or whether preflight
    checking it once is the same mistake R3 was written about - *checked at the start, refused in
    the middle.*
  - **What `rescan` should be told.** The repair exists; nothing points the user at it.
