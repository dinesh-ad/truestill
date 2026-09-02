# (ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.

*Body of backlog entry `(ads)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
    - **`(adl)`** (shipped 2026-08-19) and **`(adm)`** are both about behaviour under that same lock.
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
    (`app_paths.py:SESSION_URL_FILENAME`), so a catalog **can** live somewhere that breaks.
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
    (`catalog.py:_split_schema`) **before** it can read `PRAGMA user_version` - it has to, because reading
    the version and acting on it is the check-then-act §5.4 closed. So an open that will change
    nothing still takes the write lock.
  - **The preview job is a reader in its body and a writer at the door.** `organize.py:_mode_mechanism`
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
  this entry. ⚠ **`journal_mode` was not the variable until `(adu)` was answered**: comparing the
  two modes through a bottleneck that is identical in both is a null result waiting to happen -
  which is the most likely explanation for §7's.
  ✅ **`(adu)` SHIPPED 2026-08-18** (`SHIPPED.md`): an open that will change nothing no longer
  takes the write lock. **This entry is therefore now measurable for the first time**, and the
  measurement it needs is the one below - with the control it names, which `(adu)` has now
  supplied by making the fast path real rather than hypothetical.

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
  same bottleneck and *of course* they agree. ✅ **No longer a control that has to be built** -
  `(adu)` shipped it, so a run against `main` is already the conditional case.

  ⚠ **`df -T` FIRST.** §5.5's rig reported fsync at 0.0004 ms on tmpfs - the exact trap the
  paragraph it was citing documents.

  ⚠ **THE NETWORK ARM HAS NOWHERE TO RUN ON THIS MACHINE, and that is a blocker rather than a
  detail.** A `TRUESTILL_DATA_DIR` pointed at a local directory measures nothing about WAL: the
  whole question is a filesystem that cannot share memory. The only network filesystems on the
  maintainer's machine are **fenced mounts that are never read, walked or stat'd under any flag**
  (`IMPLEMENTATION_STANDARDS.md`, the corpus fence). So where this arm gets measured is itself
  unanswered, and a run that quietly substitutes a local directory would produce a confident
  number about the wrong thing.

  ## ✅ MEASURED 2026-08-18, AFTER `(adu)` SHIPPED - AND THE ANSWER IS THAT `(adu)` TOOK THE WIN

  `(adu)` supplied the control this entry said had to be built, so §7's comparison was re-run
  with it. **Corpus, cited rather than described:** a copy of the real catalog
  (`reports/catalog.sqlite`, **6.37 MB, 2,695 files, 3 drives, schema v19**) and the photo tree at
  `TruestillLibrary/Input`, **11 GB / 4,112 files as of 2026-08-18T22:20:46+02:00**. ⚠ That is a
  **snapshot of a mutable scratch area on one machine** - not a fixture, and not a premise. Rig on
  ext4; the original catalog was copied and never written.

  Reader = the catalog work `organize_preview` does (`count`, `list_drives`, `seed_rows`,
  `known_sizes`, ~6 ms). Writer = what `set_organize_mode` does.

  ### 🔑 THE (adt) SHAPE, AND IT IS DECISIVE: one long-held write, a reader arriving 200 ms in

  | | `delete` | `wal` |
  |---|---:|---:|
  | **pre-`(adu)`** (every open takes `BEGIN IMMEDIATE`) | **1848.3 ms** | **1850.6 ms** |
  | **post-`(adu)`** (shipped) | **6.1 ms** | 12.4 ms |

  **Pre-`(adu)` the two modes are identical to within 2 ms** - §7's *"two writers block identically
  in both modes"*, reproduced on the real shape rather than on a synthetic holder. **Post-`(adu)`
  the reader sails through under `delete`, and WAL is SLOWER.** `(adt)`'s mechanism - a reader
  waiting out `busy_timeout` behind a long write - is **already gone**, and WAL had nothing to do
  with it.

  ### ⚠ AND THIS ENTRY'S CENTRAL MECHANISM CLAIM IS MEASURABLY FALSE

  The entry says *"in rollback journal **a writer excludes all readers**"* and, of `(adt)`, *"under
  `journal_mode=delete` a writer excludes everyone, so a settings write and a job cannot
  overlap."* **They can.** A writer holding a write transaction open for two full seconds did not
  block a reader **at all** (6.1 ms). SQLite holds **RESERVED** for the body of a write, and
  RESERVED *permits readers*; only the brief **EXCLUSIVE** window at commit locks them out. What
  starves a reader is **repeated commits**, never a long-held write. The claim was inherited from
  the shape of the documentation rather than measured, and it is the reason this entry expected
  WAL to matter here.

  ### WHERE WAL DOES WIN: sustained commit pressure, and only there. Post-`(adu)`, reader p99:

  | writer interval | `delete` p50 / p99 | `wal` p50 / p99 | p99 ratio |
  |---:|---:|---:|---:|
  | 0 ms (as fast as it can) | 632.9 / **3211.4 ms** | 6.2 / 18.5 ms | **174x** |
  | 5 ms | 58.4 / 102.8 ms | 9.5 / 19.5 ms | 5.3x |
  | 10 ms | 15.1 / 43.7 ms | 8.6 / 18.0 ms | 2.4x |
  | 20 ms | **6.0** / 23.0 ms | 6.1 / 16.2 ms | 1.4x |
  | 50 ms | **5.5** / 15.0 ms | 5.8 / 8.6 ms | 1.7x |

  **The crossover is at roughly one write per 10-20 ms, and the app sits on the far side of it.**
  The only sustained writer this product has is an organize run, which writes once **per file,
  after each copy** (`catalog_busy.py`'s own docstring). Measured on the corpus above: mean file
  **2.82 MB**, and hashing alone costs **3.6 ms/file at 778 MB/s** - warm cache, so a floor - on
  top of which a real run copies those bytes and runs exiftool (**2.2 ms/file**, `PERFORMANCE.md`
  §4). Per-file intervals land at or beyond 20 ms, where `delete`'s p50 is **better** and its p99
  is within 1.4x. ⚠ **And the warm-cache bias runs in the safe direction**: a cold run is slower
  per file, which moves the app further from WAL's advantage, not closer.

  ### THE NETWORK ARM STILL HAS NOWHERE TO RUN, and it was not substituted

  The only network filesystems on this machine are fenced mounts that are never read, walked or
  stat'd. A `TRUESTILL_DATA_DIR` pointed at a local directory measures nothing about WAL, whose
  whole constraint is shared memory, so **the arm was left unrun rather than faked.**

  ⚠ **A trap found while checking the arm is even ready, recorded so it does not produce a
  confident number about the wrong file.** `TRUESTILL_DATA_DIR` is **silently shadowed by the
  legacy catalog**: `default_catalog_path` checks `reports/catalog.sqlite` relative to the CWD
  first, so run from the repo root the override is ignored and the repo's own catalog is measured.
  Verified both ways - from a directory without `reports/` the override resolves correctly.

  ### 🔑 THE ANSWER

  **`(adu)` already took the win, and `journal_mode` remains a lever with no measured problem to
  fix** - which is where §7 left it on 2026-08-09, now reached by measurement against the real
  workload instead of a synthetic two-writer case, and with the control that comparison lacked.

  **What adopting WAL would buy:** 1.4-2.4x on a p99 of 16-44 ms, at write rates the app does not
  reach. **What it would cost:** the `-wal` sidecar as a new torn-copy mechanism (`(adb)`),
  persistence into the file so a catalog carries the mode to wherever it is moved, read-only media,
  and a detection-and-fallback path for locations where it cannot work. **The cost is not close.**

  ⚠ **This entry is NOT closed and should not be**, because what changed is the evidence, not the
  question: the numbers above are a snapshot of one machine's scratch area and one library. What
  is settled is that **nothing measured today justifies the change**, and that the next person
  should re-run the sweep rather than re-derive the argument.

  ### ⚠ AND A CORRECTION TO THIS ENTRY'S OWN REFRAMING OF 2026-08-18

  The reframing above argued *"WAL would not have prevented `(adt)`"* on the grounds that both
  parties are writers **and** that §7 measured two writers blocking identically. **The conclusion
  holds and the second half of the reasoning does not**: under sustained commits the two modes are
  nowhere near identical - `delete` degrades to a 3.2 s p99 where WAL stays at 18 ms. §7's finding
  is true of its own synthetic case, not of writers generally. What actually establishes the
  conclusion is the long-hold table at the top of this section, which was not run until today.

  ### ⚠ THE GATING CLAIM WAS WRONG IN BOTH DIRECTIONS (corrected 2026-08-18)

  - **`(adb)`: gated MORE than stated.** WAL's `-wal` sidecar is a **new** torn-copy mechanism,
    not a property of the one `(adb)` already describes. Adopting WAL would make `(adb)` worse
    before anything fixed it.
  - **`(adn)`, `(adl)`, `(adm)`: gated LESS than stated.** All three sit behind the **per-open
    write lock**, which `journal_mode` does not change. They are `(adu)`'s dependents, not this
    entry's.

  - See `(adt)` (the demonstration, in-process), `(adn)` (two processes, one catalog), `(adb)`
    (why a file copy of this mode is torn), `(adu)` (the question upstream of this one - **shipped**),
    `(adr)` (the 0-byte artefact of that copy - **shipped 2026-08-18**, `SHIPPED.md`),
    `(adl)` / `(adm)` (behaviour under the lock), and `PERFORMANCE.md` §5.4 (what the lock cost
    and what fixing it recovered).
