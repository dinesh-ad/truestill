# (acc) A decisions document on a drive would be found by nothing that currently looks.

*Body of backlog entry `(acc)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(acc) A decisions document on a drive would be found by nothing that currently looks.**
  Recorded 2026-08-09, from code, while building the decisions-on-drive feature
  (`truestill_core.decisions`). **Load-bearing for Stage 4** - moved out of a plan file in
  a home directory and into the repository, because a plan file does not survive a new machine
  and `docs/ui-inventory.md` was lost twice for exactly that reason. **The design itself now
  lives in [`decisions-on-drive-research.md`](../../decisions-on-drive-research.md)**; this entry is
  one finding out of it, not the design.
  - ⚠ **CORRECTED AGAIN 2026-08-22 BY A WHOLE-BACKLOG RE-READ: THE HEADLINE BELOW IS NOW FALSE,
    AND THE ENTRY IS SMALLER THAN ITS TITLE.** `write_decisions` has **two callers** today -
    `decisions.py:981` and `cli.py:1497` - and `catalog_session.open_catalog` is the standing
    trigger, writing on the first open after upgrade and on every clean exit that dirtied the
    catalog. **Documents are written to drives.** So the *"zero callers / no document has ever
    been written"* half is dead.
    **What survives is the title's own claim and it is narrower than the body reads**: nothing
    *passively* notices a document. `read_decisions` exists and is reachable only from an explicit
    CLI command; `drive.reach_of` still reads the marker and never the contents, so plugging in a
    drive that carries decisions tells nobody. That is a discovery feature, not a missing write.
    The stale text is kept below rather than edited, because a correction that deletes what it
    corrects leaves the next reader unable to tell which half moved.
  - **CORRECTED 2026-08-09: this entry said "Stages 1-3 landed" and Stage 3 is half of one.**
    `write_decisions` exists, is atomic and is tested - and has **zero callers**. Stage 3 was
    "the write trigger and the file"; only the file was built. **So no document has ever been
    written to a drive**, the ongoing trigger is unbuilt, and so is the first-run-after-upgrade
    write - the one addition aimed at the user most at risk, who has a finished library and has
    stopped naming things. Checked by grep across core, CLI and app, not assumed.
  - **The design.** A copy of the decisions a rescan cannot recompute - trip and event names,
    drive label, settings, dismissed clusters, corrected dates - written as
    `.truestill-decisions.json` beside `.truestill-drive.json` at a drive root. Lose the catalog,
    plug in any drive, the names come back.
  - **NEITHER PATH THAT TOUCHES A DRIVE WOULD NOTICE IT**, checked rather than assumed:
    - `drive.reach_of` reads only the settings path hint and the marker. **It never looks at
      drive contents**, which is exactly why it is cheap enough to run on every listing.
    - `rescan` walks the drive, but `scan_source` prunes hidden entries into a census group that
      is deliberately skipped - *"a dot-file is not a photo"* - so a dotfile at the root never
      surfaces as stray.
    So a user who has just lost their machine, plugged a drive in, and is looking at the screen
    that lists it **would be told nothing**, and the restore path would sit one command away with
    nothing pointing at it. **That is the Adobe failure one step later**: their catalog backups
    existed and users could not find them. Storage was never the problem there either.
  - **SMALLEST HONEST FIX, for Stage 4.** The drive-listing path already opens the marker at that
    root, so reading a sibling costs **one extra `stat` and no walk**. When a reached drive
    carries a decisions document and the catalog holds none for it - the lost-machine case
    exactly - the listing says so and names the restore command. No new scan, no new surface, and
    it appears on the screen someone opens first after plugging a drive in.
  - ⚠ **CORRECTED 2026-08-09: THE LISTING IS THE WRONG PLACE FOR THE CASE THIS ENTRY NAMES**, and
    the error is mine - the finding was approved without checking where the listing looks.
    `_cmd_drives` iterates `catalog.list_drives()`. **On a lost-machine catalog that is zero
    rows**, so it prints the initialise hint and touches no path at all: the sibling `stat` never
    happens for the very user this was filed for.
    - **The lost-machine path is `drives --init <root>`**, which already holds the root, already
      reads the marker there, and already has `--adopt-existing` for re-attach.
    - **The listing keeps its stat too, for the PARTIAL case** - a catalog that exists, a drive
      that is registered, and decisions on it this machine does not have. Neither place covers
      the other, which is why both are wired.
    - **BUILT 2026-08-09.** `decisions.notice_for` decides what to say; both CLI screens print
      it. Measured rather than assumed: the catalog read the listing gained is **0.10 ms** on the
      real catalog against `list_drives`' existing 1.79 ms, and **4.48 ms** on a catalog stressed
      to 501 trips, 2000 events and 2006 skipped clusters - far past any real library.
  - **Not a reason to widen `reach_of`.** Its cheapness is the feature; a listing that walked
    drives would be worse than the problem. The `stat` belongs where the marker read already is.
