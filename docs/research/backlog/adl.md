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
