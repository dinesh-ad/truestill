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
