# (adl) THE MIGRATION CHAIN IS NOT TRANSACTIONAL AND HALF-LIFTS ON FAILURE.

*Body of backlog entry `(adl)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adl) THE MIGRATION CHAIN IS NOT TRANSACTIONAL AND HALF-LIFTS ON FAILURE.** Recorded
  2026-08-14, unchanged by the schema-race fix that sits directly above it in the same method.
  `Catalog._migrate` now takes `BEGIN IMMEDIATE` before its check, so the fresh-catalog path is
  atomic and cross-process safe. **The `_MIGRATIONS` chain deliberately runs OUTSIDE that
  transaction**, and it is a constraint that was measured, not a preference:
  - **12 of the 18 migrations call `executescript`**, which Python documents as issuing an
    implicit `COMMIT` first. Verified rather than read: `in_transaction` goes `False` and the
    lock is gone. Wrapping the chain would have **silently released the lock at the first
    migration while looking correct**.
  - **`_drop_redundant_sha256_index` (v18) runs `VACUUM`**, which SQLite refuses inside a
    transaction outright: `cannot VACUUM from within a transaction`.

  So today's behaviour is preserved exactly: each ALTER autocommits, and a chain that fails
  part-way leaves the schema **half-lifted with `user_version` unchanged**, so the next open
  re-runs from the old version and re-applies the steps that already succeeded. That is where
  the `duplicate column` errors came from historically; they are gone now only because the
  transaction stops the chain being *entered* on a catalog that is already current, not because
  the chain became safe.
  **Needs its own design and is not a bug fix**: making it transactional means rewriting twelve
  migration functions off `executescript` and moving the `VACUUM` outside, which changes the
  upgrade path for every existing catalog. Do not attempt it as a follow-on to the lock work.

  - ⚠ **MEASURED 2026-08-18, FROM `(adu)`'s RIG: THE CHAIN IS NOT SERIALISED EITHER, AND THAT WAS
    ASSUMED RATHER THAN CHECKED.** This entry records that the chain is not *transactional* - it
    half-lifts on failure. It is also not *exclusive*: `_migrate` commits its transaction and the
    `for target, migrate in _MIGRATIONS` loop runs **after** that commit, outside any lock. So two
    openers can run the same migration at the same time.
    - **Measured** on a catalog stepped back one version, openers released together, 150 trials
      per row, rig on ext4 with a 256x `fsync` control:

      | openers | ran the v19 migration once | twice | three times |
      |---:|---:|---:|---:|
      | 2 | 149 | 1 | - |
      | 6 | 130 | **18** | **2** |

    - **One in seven six-way opens ran one migration more than once**, today, with `BEGIN
      IMMEDIATE` in place. **No errors** - the migrations in the chain happen to be idempotent, so
      nothing has ever failed because of this. That is luck holding rather than a design, and a
      future migration that is not idempotent would meet it.
    - ⚠ **This does not change `(adu)`'s answer and `(adu)` does not fix this.** They are separate:
      `(adu)` is about the lock being taken when nothing will be written; this is about the chain
      running outside the lock that is taken.

  ## ⚠ RESEARCHED 2026-08-18, AND IT IS A LIVE DEFECT RATHER THAN A LATENT ONE

  ⚠ **THE FRAMING ABOVE - *"no errors only because the migrations happen to be idempotent, which
  is luck holding rather than a design"* - IS WRONG IN BOTH DIRECTIONS**, and the correction is
  the finding. All 18 were read, one at a time.

  ### The idempotence is a DESIGN, applied 18 times out of 18

  Not luck. Every migration is guarded, by one of exactly two patterns:

  | pattern | count | examples |
  |---|---:|---|
  | `CREATE TABLE/INDEX IF NOT EXISTS`, `DROP INDEX IF EXISTS` | 10 | `_add_event_tables`, `_add_drive_tables`, `_drop_redundant_sha256_index` |
  | an explicit column check before `ALTER TABLE` | 8 | `_add_size_column`, `_add_capture_columns`, `_add_copy_missing_at` |

  Two of them (`_add_copy_date_baked_at`, `_add_copy_missing_at`) additionally return early on a
  missing table, with the reasoning written down. **Re-running any of them sequentially is safe,
  and that was engineered.**

  ### 🔑 BUT IDEMPOTENT IS NOT CONCURRENCY-SAFE, AND THAT IS THE DEFECT

  Every guard is a **check-then-act** - `if "missing_at" not in columns: ALTER TABLE ...` - and
  the chain runs outside any lock. Two openers can both pass the check and both `ALTER`. The
  second gets **`OperationalError: duplicate column name`** and **the catalog open FAILS**. This
  is not a silent double-apply; it is a hard error reaching the caller.

  **It is also not new.** `PERFORMANCE.md` §5.4 records `duplicate column` failures in run
  `31810809571` - *"an opener that read `version = 0`, then found `files` already built by the
  winner"*. **Same error class, still reachable.**

  **Measured 2026-08-18** on a catalog stepped back to the v18 shape (the column actually dropped,
  so the migration does real work), rig on ext4:

  | | openers | opens | failed | rate |
  |---|---:|---:|---:|---:|
  | natural timing, N=2 | 2 | 120 | 0 | 0% |
  | natural timing, N=6 | 6 | 900 | **72** | **8.0%** |
  | natural timing, N=12 | 12 | 720 | 87 | 12.1% |
  | **forced** (all openers check before any acts) | 2-12 | every trial | **all but one** | 100% |

  **One open in twelve fails at six concurrent openers, with no forcing at all** - and a page load
  fires six requests. ⚠ **The earlier measurement in this entry counted the wrong thing**: it
  stepped back only `user_version`, so the migration found its column already present and returned
  early. It measured **entry into the chain** and could not have seen an error. The rig above drops
  the column, which is why it does.

  ### Does `(adu)` change the exposure? Measured, and the honest answer is "roughly halves it"

  | | opens | failed | rate |
  |---|---:|---:|---:|
  | landed (`(adu)` present) | 900 | 72 | **8.0%** |
  | `(adu)` mutated out | 900 | 125 | **13.9%** |

  ⚠ **The mechanism for that reduction is NOT established, and attributing it would be exactly the
  retro-fitting this repo criticises.** It is not an effect `(adu)` was designed for. What is
  established is the half that matters: **`(adu)` does not remove this.** The earlier claim in this
  entry that the figures were *"statistically unchanged"* came from the rig that measured a no-op
  migration; it is withdrawn as measuring the wrong quantity, not as a wrong number.

  ### What it would take to serialise the chain - and HALF THE STATED BLOCKER DOES NOT EXIST

  `Catalog._migrate`'s docstring gives two reasons the chain cannot be wrapped. **One is false
  about the current code and the other is a Python driver behaviour rather than a SQLite one.**

  - ❌ **"`_drop_redundant_sha256_index` runs `VACUUM`, which SQLite refuses inside a
    transaction."** **`VACUUM` appears nowhere in any migration.** `grep -n VACUUM catalog.py`
    returns exactly two lines, and **both are prose** - one in a measurement note, one in the claim
    itself. The v18 migration is a single `DROP INDEX IF EXISTS`. The statement may have been true
    of a draft; it is not true of the code it documents.
  - ✅ **`executescript` issues an implicit `COMMIT` first.** Verified on this runtime (Python
    **3.13.13**, SQLite **3.50.4**): `in_transaction` goes `True -> False` across an
    `executescript`. **But it is a `sqlite3` module behaviour, not a database constraint**, and
    **10** migrations use it - not the *"12 of the 18"* the docstring claims.
  - ✅ **DDL itself is fully transactional in SQLite**, which the docstring never says and which is
    what reopens the question. Verified: `CREATE TABLE` and `ALTER TABLE` inside `BEGIN IMMEDIATE`
    leave `in_transaction` `True`, and `rollback()` **removes the created table**.

  **So what is left is a real route, not a closed door:** replace `executescript` with
  per-statement `execute` in those 10 functions - the repo already has `_split_schema`, used for
  exactly this on `_SCHEMA_STATEMENTS` - and the chain can run inside the transaction `_migrate`
  already opens. ⚠ **The cost is `(adu)`'s in reverse**: the write lock would be held for a whole
  migration rather than a check, which on a behind-by-several-versions catalog is the multi-second
  hold §5.4 measured. That is a trade to decide, not a detail.

  **The industry alternative, named rather than invented.** EF Core hit this exact problem and
  documents the remedy: *"Unlike SQL Server, which uses a session-level application lock
  (`sp_getapplock`)… SQLite doesn't have built-in application locks. EF Core instead creates a
  `__EFMigrationsLock` table and inserts a row to acquire the lock."* ⚠ **And Microsoft documents
  its failure mode in the same breath**: if the process is killed mid-migration the lock row
  survives, *"prevents any subsequent migration from completing"*, and the remedy is a manual
  `DROP TABLE "__EFMigrationsLock"`. **For a local-first desktop app a user can force-quit, an
  abandoned lock needing manual SQL is a worse failure than the one being fixed** - recorded so
  this route is met with its cost rather than its reputation.

  ### ⚠ CORRECTION 2026-08-19: "ONLY A WHOLE-CHAIN TRANSACTION CLOSES THE HALF-LIFT" IS WRONG

  That was this entry's own claim and it is refuted. **The standard pattern is a per-migration
  transaction with the version stamp INSIDE it**, and it closes the half-lift by construction -
  because both halves roll back together.

  **Verified on this runtime** (Python 3.13.13, SQLite 3.50.4) rather than reasoned:

  | inside one transaction | after `ROLLBACK` |
  |---|---|
  | `ALTER TABLE t ADD COLUMN y` + `PRAGMA user_version = 6` | version back to **5**, column **gone** |

  **`PRAGMA user_version` is transactional**, like the DDL beside it. So *"the migration ran but
  the version stayed old"* - the exact state this entry was opened about - **cannot occur** when
  the stamp is inside the step's transaction.

  ### 🔑 WHERE OUR STAMP SITS TODAY, WHICH IS THE WHOLE QUESTION

  ```
  for target, migrate in _MIGRATIONS:
      if version < target:
          migrate(conn)                                   # autocommits
          conn.execute(f"PRAGMA user_version = {target}")  # a SEPARATE autocommit
  ```

  **Two independent commits.** The step lands, then the stamp lands, with a real gap between them
  and no transaction around either. That gap is the half-lift, and it is one line from being
  closed - not a chain-wide redesign.

  ### What a per-step transaction leaves open, and it is a different thing

  **Only a crash BETWEEN steps** - and there the schema and the stamp **agree**: version N,
  schema exactly N. That state is **resumable, not corrupt**: the next open reads N and continues
  from N+1, which is what the chain already does. ⚠ **This distinction is the correction's
  substance.** *"Half-lifted with `user_version` unchanged"* is a schema that disagrees with its
  own version and no code can reason about; *"stopped cleanly at step 12 of 18"* is an ordinary
  resume. They are not degrees of the same problem.

  ### 🌍 THE WILD INSTANCE - this defect's user-facing shape

  Open WebUI documents exactly it, in a troubleshooting page written because users hit it:

  > `sqlite3.OperationalError: duplicate column name: message.reply_to_id`

  caused when *"a previous migration partially completed, leaving duplicate columns"*, and on
  re-run it **cascades**:

  > *"Multiple errors after a major version jump (e.g. 'duplicate column' then 'table already
  > exists' then 'no such column'): Your database is partially migrated across several
  > migrations."*

  Their stated root cause is that *"SQLite migrations lack transaction rollback capability"* -
  which is **false of SQLite and true of how the migrations were written**, the same conflation
  this entry made until today. Their remedy is hand-written table-recreation SQL, with the warning
  that *"removing columns can cause data loss"*. **That is what our duplicate-column error looks
  like from the user's side once it has happened more than once.**

  ### Two carry-alongs for whoever builds this

  - ⚠ **`PRAGMA foreign_keys` IS A NO-OP INSIDE A TRANSACTION.** Verified: set to `OFF` inside
    `BEGIN IMMEDIATE`, it still reads `1`. `Catalog.__init__` turns foreign keys **ON** for every
    connection, and SQLite's own guidance is to turn them **off** around a table rebuild, because
    a `DROP TABLE` mid-rebuild can break referential integrity. So a wrapped step **cannot**
    toggle it; the toggle would have to happen outside the transaction.
    ✅ **No migration rebuilds a table today** - checked all 18: they are `ALTER TABLE ADD COLUMN`,
    `CREATE TABLE IF NOT EXISTS`, and one `DROP INDEX IF EXISTS`. The only `DROP TABLE` in the
    module is inside `downgrade_v12_to_v11`, which is **testing-only, not in `_MIGRATIONS`, and
    called by no production path**. This is recorded as a **future** constraint, not a present
    defect.
  - ⚠ **NO TRANSACTION RECOVERS A DESTRUCTIVE MIGRATION.** A rollback restores what a *failed*
    step touched; it cannot restore what a *successful* step deliberately removed. A migration
    that drops a column and commits has destroyed that data, and every route in this entry leaves
    that untouched. **The only thing that recovers it is a copy taken before the chain runs** -
    filed separately as `(ady)`, because it is a different remedy for a different failure and
    folding it in here would let a transactional fix read as covering it.

  ### The routes, restated on the corrected understanding

  | | wrap the whole chain | **wrap each step, stamp inside** | lock table |
  |---|---|---|---|
  | holds the write lock | **~62 ms** (v1->v19 measured) | **~3-4 ms** | - |
  | closes the half-lift | yes | **yes** | no |
  | leaves | nothing | a clean resumable stop between steps | the half-lift, untouched |
  | crash mid-way | rolls back | rolls back that step | ⚠ **row survives and blocks every later migration** |

  Both transactional routes need the same prerequisite: **10 of 18 migrations call
  `executescript`**, which Python issues an implicit `COMMIT` before - so those must become
  per-statement `execute` calls or the transaction is silently released. The other 8 are already
  wrappable as they stand.

  🔑 **`(aaw)` IS THE CROSS-REFERENCE THAT MATTERS FOR THE LOCK ROUTE.** This repo has already
  designed a cross-process lock - *"Cross-process drive lock, design settled"* - and chose
  `fcntl.flock(LOCK_EX | LOCK_NB)` / `msvcrt.locking(LK_NBLCK)` for one stated reason: *"the OS
  releases these when the process dies… so 'the user is locked out of their own library' is a
  state this design cannot reach, and there is no stale lock to detect or clear."* It explicitly
  rejects a TTL and a PID liveness check, and rejects the `filelock` package because its
  `SoftFileLock` *"strands a stale lock on a dead process, the exact failure this design refuses."*
  **A migrations lock table would reintroduce precisely what `(aaw)` ruled out**, in a product
  where the user can force-quit and there is no operator to run the recovery SQL.

  ### ⚠ AND THE EXPOSURE IS MUCH NARROWER THAN THIS ENTRY IMPLIED

  The 8-12% figures above are a **synthetic worst case** - six openers released by a barrier onto a
  deliberately-behind catalog with the column actually dropped. They prove the race is real and
  reachable. **They do not describe a user's launch.**

  ✅ **The app migrates before it serves.** `server.py:126` calls `prepare_catalog` ->
  `migrate_catalog`; verified by leaving a catalog at v18, calling `create_app()` and issuing **no
  request** - `user_version` was already **19**. So the six-requests-race-the-chain story
  **cannot happen inside the app**. The chain runs once, single-threaded, at boot.

  **The real window**, measured on the real 6.37 MB / 2,695-file catalog - from the `_migrate`
  commit to the final stamp, the interval in which a second opener reads the old version:

  | upgrade | p50 | max |
  |---|---:|---:|
  | one bump (v18 -> v19) | **3.58 ms** | 5.17 ms |
  | full chain (v1 -> v19) | **62.02 ms** | 70.83 ms |

  So the live exposure is a **millisecond-wide window, once per version bump**, needing a second
  process to open inside it - a CLI command and an app launch landing within ~4 ms of each other,
  on the one launch where a migration is pending. **Real, reachable, and rare** - which is a
  ranking input, not a reason to leave a hard error on an ordinary open unfixed.

  ### What is NOT proposed

  No route is recommended here, and none has been built. What changed today is that the
  **per-step-with-the-stamp-inside** route exists at all - it was excluded by a claim of this
  entry's own that turned out to be false.
