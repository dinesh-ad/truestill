# (ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.

*Body of backlog entry `(ads)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.** Recorded
  2026-08-15, out of `(adb)`'s investigation. **This records a state and what rests on it; it
  proposes no answer.**
  - **Measured:** a freshly opened catalog reports `journal_mode=delete`, `locking_mode=normal`,
    `synchronous=2` (FULL), SQLite 3.50.4. **`PRAGMA journal_mode` appears nowhere in
    `packages/*/src`** - `Catalog.__init__` sets `foreign_keys` and pins transaction control, and
    says nothing about the journal. `delete` is SQLite's default, so the mode is **inherited rather
    than chosen** in the code. ~~and nothing in the tree records anyone weighing it.~~
    ⚠ **STRUCK 2026-08-18: SOMETHING DOES.** `PERFORMANCE.md:933` §7, under *"Declined, with the
    reason, so nobody revisits them as obvious wins"*, carries **WAL - CONSIDERED AND DECLINED ON
    MEASUREMENT** - measured 2026-08-09, two writers blocking identically in both modes (301 ms
    to fail at a 0.3 s timeout), *"a reader was never blocked in either mode at this scale"*, and
    the closing line *"revisit it with a measurement, not with reputation."* **This entry and that
    paragraph did not know about each other**, which is the failure the document map exists to
    prevent, found between two canon documents rather than in a record. The half that survives is
    narrower and still true: the *pragma* is absent from `packages/*/src`, so the mode the code
    runs under is inherited. What was weighed was whether to change it.
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
  - ⚠ **THE MODE DEMONSTRATED ITSELF FOUR HOURS AFTER THIS ENTRY WAS FILED (2026-08-15).** CI run
    **`31895987230`**, red on a **docs-only** commit: a settings write and an organize preview job
    met on one catalog **inside a single process**, the job waited out its 5 s `busy_timeout` and
    was refused. Under `journal_mode=delete` that is the documented behaviour, not a defect in
    either caller - **a writer excludes everyone**, so the job could not read while the settings
    row was being written. Under WAL the job's reads proceed alongside the write and nothing
    refuses. The entry above says the concurrency model was inherited rather than chosen; this is
    what "inherited" costs, on three ordinary clicks. Filed as `(adt)`, with the trace.
    **It does not decide the question** - WAL still needs the fallback this entry describes, and
    `(adt)` carries an unanswered one of its own: why a single-row settings write took 6.5 s.
  ## ⚠ REFRAMED 2026-08-18, AND THIS IS NOW THE ENTRY'S CORE: WAL WOULD NOT HAVE PREVENTED `(adt)`

  The entry above reads as *delete versus WAL, blocked on a detection path*. It is not. **Both
  parties in `(adt)` are writers**, so the mode that lets readers proceed alongside a writer has
  nothing to act on.

  - **`Catalog.__init__` makes every open a writer.** `_migrate` executes `BEGIN IMMEDIATE`
    (`catalog.py:830`) **before** it can read `PRAGMA user_version` - it has to, because reading
    the version and acting on it is the check-then-act §5.4 closed. So an open that will change
    nothing still takes the write lock.
  - **The preview job is a reader in its body and a writer at the door.** `organize.py:804-823`
    reads only - `resolve_scheme`, `heavy_days_for_organize`, `seed_rows`, `known_sizes`,
    `_matched_drives`. It never reaches them: `open_catalog` -> `Catalog(db)` -> `BEGIN
    IMMEDIATE`.
  - **WAL does not permit two writers**, and this repo has already measured that rather than
    reasoned it: `PERFORMANCE.md` §7, *"two writers block identically in both modes."*

  **So under WAL the preview job still queues, still exhausts `busy_timeout`, and is still
  refused.** The failure `(adt)` records reproduces unchanged.

  🔑 **THE REAL QUESTION IS UPSTREAM OF `journal_mode`: can an open that will change nothing
  avoid the write lock, without giving back what §5.4 bought?** §5.4 bought that lock deliberately
  - 2,170 schema writes from 7,696 opens, one holder at 20,260 ms - and it is what makes
  check-then-act atomic across processes. Filed as **`(adu)`**, and it is what actually gates
  this entry. ⚠ **`journal_mode` is not the variable until `(adu)` is answered**: comparing the
  two modes through a bottleneck that is identical in both is a null result waiting to happen.

  ### Why §7's decline is DATABLY STALE, which is the reason to reopen rather than defer to it

  §7 measured on **2026-08-09** that *"a reader was never blocked in either mode."* `BEGIN
  IMMEDIATE` on every open landed on **2026-08-14** (§5.4). The decline is sound against the
  codebase it was measured on, where a reader was a reader; it has not been true since, and
  nothing re-ran it. **Neither document is wrong - the code moved between them.**

  ### The detection path is SOLVED and cheap, and the entry above overstates it

  SQLite: *"The journal_mode pragma returns a string which is the new journal mode. On success,
  the pragma will return the string 'wal'. If the conversion to WAL could not be completed (for
  example, if the VFS does not support the necessary shared-memory primitives) then the
  journaling mode will be unchanged and the string returned from the primitive will be the prior
  journaling mode."* Verified 2026-08-18 on a scratch file: `PRAGMA journal_mode=WAL` returned
  `'wal'`, and `-wal` / `-shm` appeared beside it.

  **You attempt rather than predict**, and that distinction is the whole content: the SQLite
  forum is explicit that no advance test exists (*"In a one-line C call, no"*; running the WAL
  test suite instead is *"brittle, detecting only your current failure case"*). ⚠ **The answer is
  true only for that location, at that moment** - which is what the next section is about.

  ### WAL IS PERSISTENT, so it stops being a setting and becomes a property of the FILE

  SQLite: *"Unlike the other journaling modes, PRAGMA journal_mode=WAL is persistent. If a process
  sets WAL mode, then closes and reopens the database, the database will come back in WAL mode."*
  Verified alongside the probe above. The entry named `locking_mode=EXCLUSIVE` as the awkward
  fallback; **persistence is the larger consequence and it was not named at all.**

  - **A WAL catalog moved to a network share arrives as a WAL file where WAL cannot work.**
    `truestill catalog --move` copies to a location the user names, and the detection that said
    *yes* ran at the source. Nothing re-asks at the destination.
  - **The `-wal` sidecar carries committed data** - a new torn-copy mechanism for `(adb)`, filed
    in that entry rather than here.
  - **Read-only media stop working**: a WAL database cannot be opened without write access to the
    `-shm` file or the directory holding it.

  ### What the missing measurement actually is, including the control §7 did not have

  | | §7, 2026-08-09 | what is missing |
  |---|---|---|
  | parties | two **writers**, one deliberately holding `BEGIN IMMEDIATE` | a **real job reading** while a real settings write commits |
  | scale | *"at this scale"*, unnamed | the real 2,695-file / 6.37 MB catalog |
  | code | opens were **not** writers | opens **are** writers, five days later |
  | location | local only | local disk **and** a `TRUESTILL_DATA_DIR` override |

  🔑 **THE CONTROL, and without it the run repeats §7's null result:** the same measurement with
  `_migrate`'s `BEGIN IMMEDIATE` made conditional. Otherwise both modes are measured through the
  same bottleneck and *of course* they agree.

  ⚠ **`df -T` FIRST.** §5.5's rig reported fsync at 0.0004 ms on tmpfs - the exact trap the
  paragraph it was citing documents.

  ⚠ **THE NETWORK ARM HAS NOWHERE TO RUN ON THIS MACHINE, and that is a blocker rather than a
  detail.** A `TRUESTILL_DATA_DIR` pointed at a local directory measures nothing about WAL: the
  whole question is a filesystem that cannot share memory. The only network filesystems on the
  maintainer's machine are **fenced mounts that are never read, walked or stat'd under any flag**
  (`IMPLEMENTATION_STANDARDS.md`, the corpus fence). So where this arm gets measured is itself
  unanswered, and a run that quietly substitutes a local directory would produce a confident
  number about the wrong thing.

  ### ⚠ THE GATING CLAIM WAS WRONG IN BOTH DIRECTIONS (corrected 2026-08-18)

  - **`(adb)`: gated MORE than stated.** WAL's `-wal` sidecar is a **new** torn-copy mechanism,
    not a property of the one `(adb)` already describes. Adopting WAL would make `(adb)` worse
    before anything fixed it.
  - **`(adn)`, `(adl)`, `(adm)`: gated LESS than stated.** All three sit behind the **per-open
    write lock**, which `journal_mode` does not change. They are `(adu)`'s dependents, not this
    entry's.

  - See `(adt)` (the demonstration, in-process), `(adn)` (two processes, one catalog), `(adb)`
    (why a file copy of this mode is torn), `(adu)` (**the question upstream of this one**),
    `(adr)` (the 0-byte artefact of that copy - **shipped 2026-08-18**, `SHIPPED.md`),
    `(adl)` / `(adm)` (behaviour under the lock), and `PERFORMANCE.md` §5.4 (what the lock cost
    and what fixing it recovered).
