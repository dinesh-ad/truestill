# (ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.

*Body of backlog entry `(ads)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.** Recorded
  2026-08-15, out of `(adb)`'s investigation. **This records a state and what rests on it; it
  proposes no answer.**
  - **Measured:** a freshly opened catalog reports `journal_mode=delete`, `locking_mode=normal`,
    `synchronous=2` (FULL), SQLite 3.50.4. **`PRAGMA journal_mode` appears nowhere in
    `packages/*/src`** - `Catalog.__init__` sets `foreign_keys` and pins transaction control, and
    says nothing about the journal. `delete` is SQLite's default, so the mode is **inherited rather
    than chosen**, and nothing in the tree records anyone weighing it.
  - **What rests on it.** Three things now depend on a model nobody picked:
    - **The lock arc** (`PERFORMANCE.md` §5.4) fixed the schema race with `BEGIN IMMEDIATE` and a
      startup migration, taking holder max from **20,260 ms to 7.57 ms**. Its own diagnosis names
      the mode as part of the cost - *"21 statements each, rollback journal, `synchronous=FULL`,
      all fsyncing against one another."*
    - **`(adn)`** records that nothing stops two processes holding one catalog, and that
      correctness now rests on `BEGIN IMMEDIATE` alone.
    - **`(adl)`** and **`(adm)`** are both about behaviour under that same lock.
  - **Why the mode is a product difference and not a tuning knob.** In rollback journal **a writer
    excludes all readers**; in WAL **readers proceed alongside one writer**. For a local app whose
    ordinary state is a browser window issuing several concurrent reads while a job writes, that is
    a different product under the same code. It is also what `(adb)` turns on: the rollback journal
    mutates the main file in place, so a mid-transaction file copy takes partially-applied changes
    with the originals stranded in `-journal`.
  - **THE REASON IT IS NOT A ONE-LINE PRAGMA, and this is the entry's real content.** WAL requires
    every process to share a small amount of memory through a `-shm` file, and SQLite's wording is
    unambiguous: *"All processes using a database must be on the same host computer; WAL does not
    work over a network filesystem."* `_data_dir()` honours a **`TRUESTILL_DATA_DIR`** override
    (`app_paths.py:107-111`), so a catalog **can** live somewhere that breaks.
    - **And the documented escape hatch points the wrong way for this product.** WAL works without
      shared memory only *"as long as the `locking_mode` is set to EXCLUSIVE before the first
      attempted access"* - which is single-process by construction, and `(adn)` records that this
      product is not. So the fallback for the case that needs one is the opposite of the
      concurrency the app actually has.
    - Two further documented constraints, recorded so they are not met later as surprises:
      `page_size` cannot be changed after entering WAL (including via `VACUUM` or a backup-API
      restore), and rollback journal is likely **faster** for transactions above ~100 MB.
    - So WAL would need a **detection path, a fallback, and a decision about what the product does
      when it is unavailable** - announce it, degrade silently, or refuse the location. **That
      decision is the work; the pragma is not.**
  - **Deliberately no recommendation here.** Choosing between them needs a measurement this repo
    does not have: what the app's real read/write overlap looks like during a job, on a local disk
    and on an overridden data directory. `PERFORMANCE.md` has the lock arc but no
    reader-alongside-writer figure.
  - See `(adn)` (two processes, one catalog), `(adb)` (why a file copy of this mode is torn),
    `(adr)` (the 0-byte artefact of that copy), `(adl)` / `(adm)` (behaviour under the lock), and
    `PERFORMANCE.md` §5.4 (what the lock cost and what fixing it recovered).
