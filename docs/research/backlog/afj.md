# (afj) THE TRASH PATH REMOVES A FOLDER THAT GAINED A FILE; THE PERMANENT PATH CANNOT, AND SAYS SO.

*Body of backlog entry `(afj)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afj) FOUND BY SOAK FOUR, STEP D7, 2026-08-22.** ⚠ **The safer-looking path has the weaker
  guarantee**, and the sentence the user reads immediately before confirming describes the
  stronger one.

  ## MEASURED - the same race, run twice, one on each path

  A folder listed as *"REMOVABLE - only OS junk `[.DS_Store, Thumbs.db]`"*, with a real non-junk
  file created **between the plan and the typed confirmation** (a genuine race against the prompt,
  not a monkeypatch).

  **Trash path** - `clean-empty --permanent --apply`, trash accepting, so `permanent` never
  applied:

  ```
  Removed 3 folder(s) (3 to the trash).
  folder survives?          NO
  unexpected file survives? NO
  found at: /data/.Trash-1000/files/2013-09 - Everyday 1/unexpected-photo.jpg
  ```

  **Permanent path** - same command, same race, with the trash genuinely refusing:

  ```
  Removed 2 folder(s) (2 deleted permanently).
    ! 2013/2013-09/2013-09 - Everyday: [Errno 39] Directory not empty
  folder survives?          YES
  unexpected file survives? YES
  ```

  ## THE ASYMMETRY

  `_remove_permanently` is deliberate and its docstring is explicit:

  > *Then ``rmdir`` refuses if anything else is present, so a folder that gained a file between
  > the preview and the confirm survives **by construction** rather than by a re-check that could
  > itself race. ``rmtree`` would have taken it.*

  `_to_trash(folder, backend)` hands the **whole folder** to `send2trash`, which moves it and
  everything in it. There is no equivalent guard, and the reasoning above applies just as well to
  it: the plan is stale by the time the user finishes typing.

  ⚠ **And the warning is attached to the wrong path.** The `--permanent` confirmation prints
  *"Removal uses rmdir, so a folder that is no longer empty cannot be removed even if it is listed
  above."* In the first run above, the user read that sentence and then all three folders went to
  the **trash**, where it is not true - including the one that was no longer empty.

  ## SEVERITY - stated honestly, because it is not the worst case

  **The file went to the trash and is recoverable.** This is not data loss; it is *removing
  something the preview did not name*, which is the soak's stated third column. Two things keep it
  from being minor:

  - the user is never told. The run says *"Removed 3 folder(s) (3 to the trash)"*; nothing
    mentions that one of them was no longer the folder the preview classified;
  - ⚠ **a trash refusal turns it into permanent deletion.** With `--permanent` set, a folder the
    trash rejects goes through `_remove_permanently` - protected. But the ordering means the
    *protected* path is the one that runs only when the trash says no. **The unprotected path is
    the default.**

  ## THE RACE IS ORDINARY, NOT EXOTIC

  `clean-empty` previews, then blocks on a typed word. Seconds pass. A sync client, a camera
  import, a photo app writing a sidecar, or a second Truestill window is enough. Nothing about
  this needs a hostile user or a scripted race - the test only used one to make it deterministic.

  ## OPTIONS

  **A. Give the trash path the same guard.** Re-check the folder holds nothing but the planned
  junk immediately before `_to_trash`, or unlink the named junk and let a `rmdir` prove emptiness
  before handing the (now empty) folder over. *The second keeps `_remove_permanently`'s
  "by construction rather than by a re-check" property instead of adding a racy re-check.*

  **B. Move the rmdir sentence out of the `--permanent` block** so it describes what the run will
  actually do, whichever path each folder takes. *Needed regardless of A: today it is printed by
  the branch least likely to execute.*

  **C. Report per-folder what happened**, so "removed" and "removed, and it was not what we
  classified" are different lines.

  ## NOT DECIDED

  - Whether **A** should apply to the junk-only tier alone or to every candidate.
  - Whether a folder that changed between plan and confirm should be **skipped and reported** (the
    permanent path's behaviour) or **re-planned**.

  ---

  # FIXED 2026-08-22. The contents go to the trash; the folder goes to `rmdir`.

  ## What each path actually checked, which corrects this entry's own framing

  ⚠ **Neither path re-verified.** This entry says the trash path "lacks the permanent path's race
  protection", which reads as though the permanent path re-checks. It does not. The only re-check
  either had was `folder.is_dir()`, shared by both, testing existence and not contents.
  `_remove_permanently`'s safety was never a check - it is `rmdir`'s kernel-enforced precondition.

  So "make the trash re-verify like permanent" had no referent, and a contents check before
  `send2trash` would have imported the exact check-then-act window the module was written against.

  ## The fix

  Trash the folder's **named junk individually**, then `folder.rmdir()`. `Tier.EMPTY` carries no
  contents, so for it the whole operation is that `rmdir`. `Tier.JUNK_ONLY` contents are file names
  only - a surviving subdirectory short-circuits to `OCCUPIED` - so nothing is recursive and no
  directory ever reaches `send2trash`.

  **Ordering is forced.** `rmdir` cannot be asked whether it *would* succeed, so junk goes first.
  If `rmdir` then refuses, the junk is in the trash and the folder remains - **strictly the least
  destructive of the three states this code has ever produced**:

  | | the folder that gained a file | its `.DS_Store` |
  |---|---|---|
  | trash path, before | **taken, with the file** | taken |
  | permanent path, before | survives | **destroyed silently** `(afk)` |
  | either path, after | survives | **in the trash** |

  ## ⚠ Reachable and refused, not impossible

  An earlier reading of this called folder-recoverability impossible. It is not: `rmdir` first,
  then `mkdir` an empty directory of the same name in the trash and write its `.trashinfo`, keeps
  the atomic gate and preserves the name. It is **refused** on three grounds, which is a different
  claim and the honest one:

  - it means hand-implementing the FreeDesktop trash spec - `$topdir` resolution, `.Trash-$uid`,
    `info/` files, name deduplication, percent-encoded `Path=` - on the one code path whose whole
    purpose is not being clever. `send2trash` has no API for filing an already-deleted directory,
    and `gio trash` takes a live path only;
  - three platforms, three trash implementations;
  - ⚠ **it is a fabrication.** The thing in the trash would be a new inode wearing the old name.
    Labelling that "recoverable" is the dishonesty §9 exists to forbid.

  ## The trade, stated

  The spec stores a trashed directory whole under **one** `.trashinfo` and advises restoring it in
  its entirety. After this change the trash holds the junk files individually instead, and
  `trash-restore` returns a file to its original path *only if that path still exists* - which,
  after the `rmdir`, it does not. **So the report may claim "the junk is in the trash"; it may not
  claim "you can put it back."** The wording was written to that limit.

  ## Measured, on the race that produced this entry

  ```
  Removed 2 folder(s).
    The OS junk they held is in the trash.
    ! 2013/2013-09/2013-09 - Everyday: not removed (directory not empty); its .DS_Store is in the trash

  folder survives?        YES
  raced-in file survives? YES, bytes intact
  trash contents:         .DS_Store        folder-shaped entries: 0
  ```

  ## The wording half

  The `rmdir` sentence was keyed on `--permanent`, a flag that does not select the path, so it was
  false whenever the trash worked and absent from the default run entirely. It is now printed for
  every run, with the tiers named separately so the junk sentence cannot be read as a promise about
  folders that never held anything:

  ```
  3 folder(s) will be removed.
    2 are empty - nothing in them, so nothing to recover.
    1 holds only OS junk; the junk goes to the trash first (recoverable).

  The folder itself is removed outright, not moved to the trash. Removal uses rmdir,
  so a folder that is no longer empty when the removal runs is left alone and reported.
  ```

  `--permanent` keeps only what is still its own: where the trash refuses, the **junk** is removed
  outright. The typed word stays `clean` - see `(afh)`, which is where the ceremony question lives.

  ## Three things the fix uncovered

  ⚠ **1. `test_permanent_mode_only_applies_where_trash_was_refused` was passing while testing
  nothing.** Its skeleton is all `Tier.EMPTY`, so after this change the trash is never called, no
  refusal happens, `permanent` is never consulted - and every assertion stayed green for the wrong
  reason. §4's fifty-fourth member, in the test whose entire subject is the branch it had stopped
  reaching. Two sibling refusal tests had the same hole. All three now use a junk-bearing skeleton.

  ⚠ **2. `send2trash` raises on a path that is already gone**, where `unlink(missing_ok=True)` had
  shrugged - and junk vanishing between the plan and the apply makes the `rmdir` *more* likely to
  succeed. Without restoring that tolerance the tidiest case became a reported failure. Restored by
  asking the filesystem **after** the failure, never by pre-checking.

  ⚠ **3. `folder.is_dir()` was itself check-then-act**, on the path whose defining property is that
  it does not check. It bought no atomicity, and it *skipped silently* - a preview naming six
  folders could report five with nothing explaining the sixth. Removed; `rmdir`'s own errno answers
  all three cases, and a candidate that became a file is now reported instead of swallowed.

  ## Closes `(afk)` too, and why it could not be separated

  `(afk)`'s own entry predicted this: *"`(afj)` option A would introduce an unlink-then-check step
  there and would inherit this exactly."* Shipping `(afj)` alone would give every ordinary run a
  partial state its report could not describe; fixing `(afk)` first would be fixing the reporting
  of a code path this commit replaces. The failure line above is the remedy for both.

  ## ⚠ Two soak-four acceptance criteria are superseded by this fix

  `soak-four-plan.md` D5 lists *"the removal is not recoverable from the trash"* as **untrue if**,
  and D6 *"the folder is gone and in no trash at all"*. After this change both describe the normal,
  correct outcome: the folder is gone and never was in the trash; only its junk is.

  **The plan is deliberately not edited** - it describes a run that happened, and soak plans are
  not rewritten to match the present any more than records are. This note is what resolves the
  pointer, and a soak five aimed at these commands must read it before reusing those two lines.
