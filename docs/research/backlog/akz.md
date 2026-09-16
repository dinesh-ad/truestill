# (akz) OPENING THE CATALOG UPGRADES IT, AND NOTHING SAID SO.

*Body of backlog entry `(akz)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Three findings from the 2026-09-16 audit, ranks 2, 3 and 5. Rank 1 waits for the licensing
server; rank 4 needs a case-insensitive filesystem.

---

## 1. THE MIGRATION WAS SILENT ON BOTH SURFACES

`Catalog.__init__` calls `_migrate` unconditionally. **There is no read-only catalog open** - a
grep for `mode=ro`, `immutable` and `read_only` in `catalog.py` returns nothing - so every command
that opens the catalog can upgrade it, including six whose names suggest they only read:
`carried`, `config`, `drives`, `rescan`, `status`, `where`.

`rescan.py`'s own promise is *"Report only. Nothing here writes to a catalog or to a drive, and no
caller of it may."* True of the module. False of the command carrying its name.

### ⚠ THE FIX IS NOT TO STOP MIGRATING, AND THE RESEARCH IS WHY

* **BoxLite has this defect verbatim**: *"a newer component migrates that database forward in
  place, and from that moment every older component stops working... no warning before the
  migration happens."*
* **FreeBSD's pkg shows the naive fix is worse.** It migrates only on read-write opens, so every
  read-only command fails on an old schema with *"no such table"* and *"the upgrade path is
  permanently wedged."*
* **OneUptime states the rule Truestill already follows**: *"use `user_version` as an explicit
  application contract and ship immutable sequential migrations... fail closed on unknown
  schemas"* - which is `catalog._refuse_if_newer`.

**So forward-migrate-on-open stays. The defect was the silence**, and that is all that changed.

### ⚠ WHERE IT IS DETECTABLE, ESTABLISHED RATHER THAN ASSUMED

Both versions are in hand at exactly one place: `catalog.py`'s `if version < CURRENT_SCHEMA_VERSION`,
the same condition the pre-upgrade copy is taken on. After the chain runs, `PRAGMA user_version`
answers `CURRENT_SCHEMA_VERSION` and nothing can recover what it was.

⚠ **AND THE MIGRATION IS NOT PERFORMED BY THE COMMAND.** `_dispatch` calls `inspect_catalog` for
every subcommand carrying `--db`, and that function opens a real `Catalog` to count files and
drives. **The startup banner is what upgrades the file**, one line before any handler runs. So the
fact rides on `CatalogStartupInfo.opening`, and `format_startup_lines` - which both surfaces
already print - is the one place it is said.

**A reporter on `catalog_session.open_catalog` was written, measured and deleted the same day.**
It would always have found `None`, because the banner had already migrated. The four subcommands
that skip the banner - `account`, `analyze`, `catalog`, `self-check` - were checked and **none
opens a catalog at all**; `analyze` was run twice against a v20 catalog and left it at v20, which
also corrects the audit's own census (it listed `analyze` among the seven, from a regex, wrongly).

### WHAT IT SAYS

```
Your library catalog was upgraded from version 23 to 24 so this version of Truestill can open
it. An older Truestill will now refuse this catalog. The catalog as it was is kept at
/home/.../catalog.pre-upgrade.sqlite.
```

⚠ **The second sentence is the one the user needs.** BoxLite's remedy asks for *"a one-line log...
naming the previous and new versions"*; naming them alone leaves a person to work out what it
costs them. What it costs is that `_refuse_if_newer` will turn an older build away - and that
refusal is the next message they meet. The remedy is named in the same breath, because the
pre-upgrade copy is the only route back to `previous`.

A failed copy gets its **own** wording rather than being softened into that one: *"there is no way
back to version 23: no space left on device"*. A sentence naming a path that does not exist would
be worse than one naming none.

**The browser gets its own host**, `#catalog-upgrade`. `#catalog-notice` is `alert`-only by a
2026-09-06 ruling - *"this may not be the catalog you expect"* - and reusing it would either
demote this to nothing or put a startup diagnostic back on the page above the h1. The value is
the **boot** reading, like `boot_catalog` beside it: `inspect_catalog` is what migrates, so a live
reading goes silent the moment the page reloads, which is when a user would look.

---

## 2. THE PRE-UPGRADE COPY WAS UNDISCOVERABLE

`cli._report_pre_upgrade_copy`'s docstring says *"a user who wants it can be told where by
`truestill catalog`"*. That command printed two lines, the catalog and the cache, and **neither
was that one**. A promise made by a docstring and kept by nothing.

```
Catalog in use   : /home/.../catalog.sqlite
Cache            : /home/.../hashes.cache.sqlite
Pre-upgrade copy : /home/.../catalog.pre-upgrade.sqlite
```

**Its state is said, not only its location.** On a library that has never been upgraded it reads
`(none kept - nothing has been upgraded)`, because a bare path with nothing at it reads as a
promise - and because that is how a user tells a **missing** copy from an **unneeded** one, which
is the distinction that matters after an upgrade whose copy failed.

**The app half is not a gap.** 0 of 46 app `open_catalog` sites pass `backup_report`, which the
audit named - but the app migrates exactly once, at boot, and every later open takes `_migrate`'s
fast path. What the app needed was the notice above, not a reporter at 46 call sites.

---

## 3. `analyze` PRINTED A COMMAND THAT DOES NOT RUN

`truestill organize <folder> --destination <folder>` - and `destination` is positional, so
argparse answers *"unrecognized arguments: --destination"*, exit 2. ⚠ **From the command the new
first screen sends a stranger to first.**

### THE CENSUS, AND WHY THE EXISTING GUARD MISSED IT

`test_a_suggested_command_can_be_run.py` existed and is scoped to **`drives --init`** by design.
Two reasons it could not see this:

1. Its subject is the literal string `drives --init`.
2. ⚠ **It must not use the parser** - `--init requires --label` is a **runtime** check in
   `cli._cmd_drives`, and `parse_args` accepts `drives --init X` happily. The tool it deliberately
   refused is exactly the tool this defect needed.

And the wider guard had been **refused with a measurement**: *"33 failures out of 36 on a clean
tree, almost all of them prose."* That measurement was taken against a bare `truestill <word>`
sweep. Three filters it did not have reduce it to nothing:

| filter | kills |
|---|---|
| the word after the name must be a real subcommand, **asked of the parser** | 23 of 60 lines - `truestill is free to use`, `truestill will not extract`, `truestill does not start a run` |
| a **quoted or backticked** command is a reference, not an instruction | 10 more - the same principle `check_product_name` rule 1 already applies |
| a suggestion **starts** at a line start or after a colon and **ends** at the end of the line or the next run of two or more spaces | the last 3 - `tell truestill where it went` (`where` IS a subcommand), and two commands with an explanatory tail |

**Result: 25 suggestions, 0 false positives, 2 real defects.** The second is `backup.py`'s
`EJECT_BEFORE_UNPLUGGING` offering a bare `truestill verify` when `path` is required - and that
one is shipped to the **browser** too, through `service/backup.py`'s `eject_note`.

Both tests stay. One asks the runtime's question, one asks the parser's, and neither can answer
the other's.

⚠ **`_build_parser` is cached, and that is a measurement**: rebuilding it per suggestion took the
file from 2 s to **60 s**, against `make check`'s 90 s ceiling for the whole suite.

---

## WHAT THE VACUITY CHECK FOUND

19 mutations, 18 caught. **Three survived first and two were fixed:**

| survivor | why |
|---|---|
| `_refused` always returning `""` | the gate passed against a check whose failure branch was unreachable. `test_the_oracle_can_say_no` now asserts both defect shapes are rejected |
| `catalog_upgrade` becoming `NotRequired[str]` | ⚠ `__required_keys__` is **vacuous** under `from __future__ import annotations` on 3.14 - `__optional_keys__` is empty, so every field reads as required. This repo records the same trap twice already. Asked of `openapi.json`'s `required` list instead, which `emit_openapi` derives with `get_type_hints(include_extras=True)` for exactly this reason |
| **`if version < CURRENT_SCHEMA_VERSION` → `if True`** | ⚠ **NAMED, NOT CLOSED.** It makes an open that migrated nothing claim *"upgraded from version 24 to 24"*. `_migrate`'s fast path returns first on every catalog a single process can construct, so the line is only reached with `previous == current` through `(afv)`'s race between concurrent openers. A defensive guard in `schema_upgrade_notice` was written to catch it and **deleted**, on this codebase's own precedent: *"a defensive `mark_clean()` here was written and then deleted, because a mutation that removed it killed no test - it could not."* |
