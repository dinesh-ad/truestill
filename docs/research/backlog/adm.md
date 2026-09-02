# (adm) `inspect_catalog` SKIPPED THE FIRST-RUN CASE - FIXED FOR THE APP, UNCHANGED FOR THE CLI.

*Body of backlog entry `(adm)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adm) `inspect_catalog` SKIPPED THE FIRST-RUN CASE - FIXED FOR THE APP, UNCHANGED FOR THE
  CLI.** Recorded 2026-08-14. `inspect_catalog` returns early when the catalog file does not
  exist (`catalog_startup.py`, the `WILL_CREATE` branch), so it inspects without creating. That
  is correct for its own contract and was **a live product defect at the process level**: the
  shipped app called it at launch and then served requests, so on a genuine first run nothing had
  migrated the catalog and the six requests a page load fires all reached `Catalog._migrate` at
  once. Measured before the fix, on a runner: **7828 opens reached `_migrate`** and the wait at
  `BEGIN IMMEDIATE` ran to **2832 ms**, 155 waits over a second. Every first-run user paid it on
  their own disk, with no CI to notice.

  **Closed for `truestill-app`** by `service.prepare_catalog`, which inspects and then migrates
  as one function - the order being the contract, since a migration that runs first makes
  `WILL_CREATE` unreachable and tells a first-run user they may have opened the wrong catalog.
  Pinned by `test_first_run_survives_the_startup_migration.py`.

  ⚠ **The CLI path is unchanged.** `cli.py` calls `inspect_catalog` and then opens through
  `_catalog`, so a first `truestill` command still migrates inside the command rather than ahead
  of it. It matters far less - a CLI has one opener, not six concurrent ones - which is why it is
  filed rather than fixed. Anything that makes the CLI concurrent should read this first.
