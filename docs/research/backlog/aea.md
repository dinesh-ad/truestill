# (aea) TWO INTACT CATALOGS FOR ONE INSTALL, AND NOTHING RECONCILES THEM.

*Body of entry `(aea)`. **CLOSED 2026-08-23 by investigation - one live catalog, one fossil, data-identical; `(abd)` owns the general case.** The index is now [`SHIPPED.md`](../../SHIPPED.md).*

- **(aea) TWO INTACT CATALOGS FOR ONE INSTALL, AND NOTHING RECONCILES THEM.** Recorded 2026-08-19,
  split out of `(adb)` where it surfaced as a refusal rather than as a finding. **Not `(adb)`:**
  that entry is about a copy being *torn*. This is about two **intact** catalogs coexisting, which
  is a different failure with a different remedy - `VACUUM INTO` would not touch it.
  - **The state.** A user can hold `reports/catalog.sqlite` and the standard
    `<data dir>/catalog.sqlite` at once, both valid, both openable, describing different libraries
    or the same one at different moments. Nothing compares them, nothing reports the pair, and
    nothing chooses between them beyond `default_catalog_path` silently preferring one.
  - 🔬 **THIS MACHINE IS THE EVIDENCE.** After `(adw)`'s migration on 2026-08-19 the maintainer
    holds both, byte-identical at 6,365,184 bytes. That is the *benign* version of the state - the
    dangerous one is the same shape after either file has moved on.
  - ⚠ **`(adw)` CLOSED THE ONLY DISCOVERABILITY PATH, AND `DESTINATION_EXISTS` IS NOW A DEAD END
    RATHER THAN A SAFEGUARD.** Before, `default_catalog_path` preferred the legacy file, so
    `truestill catalog` named it and offered `--move`. Now:
    - `default_catalog_path()` never returns it - the legacy constant appears once in
      `app_paths.py`, its own definition;
    - `truestill catalog --move` hits `destination.exists()` (`catalog_move.py:117`) and returns
      `DESTINATION_EXISTS`, exit 2;
    - and **no other code in `packages/*/src` names the file at all.**

    **The refusal is correct. The absence of any next step is not.** A refusal is a safeguard when
    something else can be done instead; when it is the only surface that mentions the file and it
    always says no, it is a dead end. The message tells the user to *"keep the one you want, move
    the other out of the way, and try again"* - which is a hand-edit of their own data directory,
    with no command behind it and nothing to tell them which one to keep.
  - **What `_describe` already gives, and why it is not enough.** The refusal prints each file's
    size and mtime (`catalog_move.py`), which distinguishes two catalogs by *when they were
    written* - not by what is in them. A user staring at two 6 MB files a day apart has no way to
    ask which one holds the trip names they typed, or which one knows about the drive they just
    plugged in. **Truestill can answer that and does not.**
  - **Not settled here, deliberately:** whether the remedy is a comparison (files, drives,
    decisions, last write - shown side by side), a merge, an adoption of one with the other
    renamed, or simply a better refusal that names what differs. Each is a different product
    promise about whose data is authoritative, and this entry does not choose.
  - 🔬 **The pair has moved on - measured 2026-08-23 by `(agr)` part 3's census.** Logically
    identical (2,695 files, 4,933 copies, identical settings, same three drives) but no longer
    the same file: `user_version` **20** in the data-dir catalog against **19** in `reports/`,
    md5 different, mtimes a week apart (08-22 against 08-15). Something opened one and migrated
    its schema; nothing touched the other. The benign byte-identical state recorded above has
    become exactly the *"after either file has moved on"* shape this entry warned about -
    silently, with no user action, and still with no surface that reports the pair.
  - **Related.** `(adb)` - the torn copy, where this surfaced. `(adr)` - a **0-byte** file at the
    destination, which is the same collision with a worthless second file and is already shipped.
    `(adw)` - what removed the discoverability, and why that was right at a population of one.
    `(adn)` / `(adh)` - two **processes** on one catalog, which is the opposite problem and not
    this one.

## ✅ CLOSED 2026-08-23 - what it actually was

**Not two live records. One live record and one fossil, proven data-identical.** All sixteen
shared tables hash equal between the pair (`SELECT * ORDER BY 1,2` | md5, immutable reads);
the whole divergence is `user_version` 20 vs 19 and the **empty** `organize_runs` table v20
added (`ac9cedf`, 2026-08-20). Both are frozen at the 2026-08-15 state: max `drives.last_seen`
is 2026-08-08, every soak used its own scratch catalog, no `(afw)` `runs/` directory exists in
the data dir, and `reports/catalog.sqlite`'s mtime predates the `(adw)` copy. The feared
"both being updated" was not happening; the data-dir catalog's 2026-08-22 mtime is one
v20-era default launch writing schema and nothing else.

**The trap that stays armed, named**: an explicit `--db reports/catalog.sqlite` starts true
divergence with no surface reporting it - and the v19 fossil is one `Catalog` open away from
silent schema migration - while `catalog --move`'s `DESTINATION_EXISTS` refusal
(`catalog_move.py:117`) remains the dead end this entry recorded: correct, and the only
surface that names the file, and it always says no. **`(abd)` owns the general case** - one
catalog or many is the live product question, the prior-art research moved there, and the
`CatalogChoice.note` pipe is the seam its ruling would use.

**A per-boot detector was DECLINED, with the reason recorded**: it would detect a state no
user can reach (`LEGACY_CATALOG_PATH` is consulted by nothing since `(adw)`; no tag has ever
been cut, so no install outside this machine ever held the legacy path), and detecting it
needs the cwd probe `(adw)` deliberately removed - the disclosure itself would be
cwd-dependent, present from one directory and absent from another. A warning that comes and
goes is worse than none.

**The fossil is Ad's record, and archiving it is proposed, not done.** The exact command,
using `(adw)`'s own set-aside precedent (`catalog.empty-superseded-20260819-112320.sqlite`):

    mv reports/catalog.sqlite reports/catalog.superseded-20260823.sqlite

Safe in one line: the data is proven identical table-by-table to the live catalog, so the
rename loses nothing and keeps the file findable under the name the product already uses for
"set aside, not deleted". `reports/catalog.sqlite.before-deb-install` (a manual 08-13 backup,
same counts) and `reports/catalog.cache.sqlite` (cache) are the same decision at Ad's
discretion.
