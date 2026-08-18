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
      running outside the lock that is taken. `(adu)`'s proposed route was measured to leave these
      figures statistically unchanged, deliberately.
