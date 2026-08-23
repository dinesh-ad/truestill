# (aea) TWO INTACT CATALOGS FOR ONE INSTALL, AND NOTHING RECONCILES THEM.

*Body of backlog entry `(aea)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
