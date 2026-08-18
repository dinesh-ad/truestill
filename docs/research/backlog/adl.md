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

  ### What is NOT proposed

  No route is recommended here. Three exist - wrap the chain (needs the `executescript` change and
  accepts a longer hold), a lock table (EF Core's, with the abandoned-lock problem), or make each
  migration concurrency-safe rather than merely idempotent (tolerate the duplicate-column error,
  the weakest) - and choosing between them is a decision this entry does not make.
