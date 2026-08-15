# (abt) The unhinted-residue prompt is CLI-only, because the app cannot ask mid-job.

*Body of backlog entry `(abt)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abt) The unhinted-residue prompt is CLI-only, because the app cannot ask mid-job.**
  Recorded 2026-08-07 with the fix.
  - **What exists.** Minting a drive identity while the catalog holds drives with no recorded
    location prompts for the typed word `new` in the CLI. It cannot be reached from the app:
    `service/organize` registers inside a running job, and a job has no way to stop and ask.
  - **The app is not unprotected, and the difference is worth stating precisely.** App organize
    has always written a path hint (`service/organize.py`), so app users accumulate the
    discriminating fact with every run and `(abs)`'s refusal covers them from the second run
    onward. **The gap is the FIRST run** - a user whose drives were all registered before hints
    existed, organizing into an unmounted mountpoint, gets no prompt.
  - **What closes it is a UI decision, not a core one.** The obvious shape is a **pre-run**
    confirmation on the Organize screen - the typed-confirm component already exists and is used
    for Rearrange and the date bake - shown before the job starts, where asking is still
    possible. The rule and its wording are already in core (`drives_without_a_known_location`),
    so this is a surface, not a second mechanism.
  - **Not urgent for the maintainer specifically:** his own path now records hints on every CLI
    run, so his first-run window closes the next time he organizes with `--apply`.
