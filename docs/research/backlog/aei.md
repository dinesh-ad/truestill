# (aei) `organize` CANNOT MAKE A SECOND COPY: "ALREADY IN YOUR LIBRARY" MEANS THE CATALOG, NOT THE DRIVE.

*Body of backlog entry `(aei)`, under **Shipped**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aei) `organize` CANNOT MAKE A SECOND COPY: "ALREADY IN YOUR LIBRARY" MEANS THE CATALOG, NOT
  THE DRIVE.** Found 2026-08-20 by the **first soak**, S2/S3, against 4,111 real photos and videos.
  **The headline finding of that soak**, and it is not a wording bug.

  ## MEASURED

  `truestill organize <Input> <D2> --apply`, with **D2 not existing**:

  ```
       4111  duplicate, skipped
             4,111 already in your library
  ```
  exit **0**. On disk afterwards: D2 **created**, `.truestill-drive.json` and
  `.truestill-decisions.json` written into it, the drive **registered** - and **12K total, not one
  media file copied**. `drives` then read `D2  0  0.0  connected`.

  ⚠ **And in the same breath `status` said:** *"At risk: 4088 file(s) exist on only ONE drive
  (3-2-1 wants >=2)"* - while a registered, connected, **empty** D2 sat beside it. **The product
  named the problem, declined to fix it, and reported that as success.**

  ## THE CAUSE, AND IT IS ONE MISTAKE MADE TWICE

  `organize` deduplicates against the **catalog** - *has this content ever been seen?* - not
  against the **destination** - *is this content on THIS drive?*. `file_copies` is per-drive and
  answers the second question; the skip path does not consult it.

  **The same mistake produces the S2 finding**, which is the reader-facing half:

  ```
  img_1080x1920x24_0149142.jpg  [SKIP: exact duplicate]
      identical to : /home/dinesh/TruestillLibrary/Input/Testing-new/img_1080x1920x24_0149142.jpg
      via          : SHA-256, already in your library
  ```
  ⚠ **That path IS the file being skipped. It says X is identical to X.** The line names
  `files.source_path` - where the content was first ingested from - so on the most ordinary re-run,
  the same folder scanned twice, the explanation explains nothing. What the reader needs is where
  the existing copy lives, and the catalog has it: `file_copies.relative =
  Saved/Undated/img_1080x1920x24_0149142.jpg` on drive `cd1a1133` (D1). Fetched, and not shown.

  ## AND THE CLI HAS NO SECOND-COPY ROUTE AT ALL

  The command list is organize / ingest / drives / repoint-sources / undo-organize / restore /
  where / analyze / verify / status / self-check / catalog / config / reclaim / migrate-layout /
  clean-empty / rescan. **Nothing copies a library to another drive.** The only route is the app's
  Backups screen (`service/backup.py:backup_run`).

  ✅ **That route WORKS and was measured**: 4,105 copied, `verified: True`, 11.6 GB in 51 s, D2's
  content set byte-identical to D1's, after which custody correctly read *"All catalogued content
  has at least two drive copies. Nicely redundant."* **So the capability exists and `organize`
  cannot reach it.**

  ⚠ **Weight:** `drive.py:116-131` records that a drive *"registered and used entirely from the
  CLI"* is the **normal** state for this product. So the normal user cannot reach the one operation
  the custody claim keeps asking for, and the obvious thing to try does the above instead.

  ## ✅ RULED AND BUILT 2026-08-20 - see `SHIPPED.md` for the closure

  `organize` into a destination copies what is not on **that** destination; scope is three-valued
  (`None` = no scope, so catalog-global - rclone and direct callers; `{}` = a markerless local
  destination; populated = what `file_copies` records). The skip line names the copy's path on this
  drive, *"already in your library"* became **"already on this drive"**, `attachable_hashes` was
  considered and deliberately not widened, and the per-destination rule is now stated in
  `IMPLEMENTATION_STANDARDS.md` §2. `(ael)` carries what remains of the CLI gap.

  ## WHAT WAS NOT DECIDED, AS FILED

  - **Whether `organize` should copy to a second drive at all**, or should refuse with *"this
    content is already catalogued; use <the copy route> to put it on a second drive"*. Either is
    defensible; silently registering an empty drive and reporting success is not.
  - **Whether the CLI gains a copy command** or the refusal simply names the app screen. ⚠ Naming
    a screen a CLI-only user will not open is `(adx)` gap 2's shape and should not be chosen
    casually.
  - **What the duplicate line should name.** The organized copy's path is the obvious answer; on a
    multi-drive library there may be several, and "which one to name" is unresolved.
