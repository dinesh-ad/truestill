# (aem) A COPY-MODE ORGANIZE LEAVES NO RECORD THAT IT STARTED, SO AN INTERRUPTED LIBRARY READS AS A COMPLETE ONE.

*Body of backlog entry `(aem)`, under **Shipped**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aem) A COPY-MODE ORGANIZE LEAVES NO RECORD THAT IT STARTED, SO AN INTERRUPTED LIBRARY READS AS
  A COMPLETE ONE.** Split out of `(aej)` on 2026-08-20 at the moment `(aej)`'s other three surfaces
  were fixed. **The split is the finding**: those three were renderings of facts the catalog already
  held. This one is a **missing fact**, and no wording repairs it.

  ## MEASURED, BY THE FIRST SOAK

  `kill -9` mid-organize left **340 of 4,105** files on the destination. Between the kill and the
  restart:

  ```
  D3   340   611.4   connected   2026-08-20T09:03:48   never
  ```

  and `status` reported normally. **Nothing anywhere said a run had been interrupted**, that 3,765
  files were missing, or that this was half a library. ⚠ **The catalog was internally consistent and
  therefore serene**: 340 rows, 340 complete files on disk, agreeing exactly. `340 files, connected`
  is indistinguishable from a small library that is finished.

  ✅ **What the soak also proved, and it is why this is a reporting gap rather than a data-loss
  one:** the write path is sound. Copy-to-`.partial` -> rename -> record survived a `SIGKILL` with
  **no truncated file, no phantom row**, and the restart resumed at exactly 3,765 = 4,105 - 340.

  ## WHY NO WORDING FIXES IT

  `(aej)`'s other three surfaces each had the answer in hand - `missing_count` on the drive row, a
  scope label on a summary block - and printed something else. **Here there is nothing to print.**

  - **No table records a copy-mode run.** The catalog's sixteen tables include `migration_runs`
    (`started_at`/`completed_at`), `reclaim_journal`, and `inplace_runs` - whose columns are
    *exactly* right: `started_at`, `completed_at`, `status TEXT NOT NULL -- in_progress | completed
    | undone`, with a comment reading *"an interrupted run keeps `in_progress` and is still
    undoable."*
  - ⚠ **But `inplace_runs` is written only when `relocation is not None`.** Its own comment scopes
    it: *"The journal attaches to the MECHANISM, not to a flag: any rename-based relocation is
    recorded."* A plain copy has no relocation, so **no row is ever opened**.
  - **The app's job state is in-memory only** and dies with the process - `JobManager._jobs`, with
    the module docstring saying so: *"The lock is process-local and in-memory: a server restart
    clears it."*
  - **The `.partial` evidence is destroyed by the very run that could have reported it.** On
    restart, `shutil.copy2` opens the leftover with `"wb"` and truncates it. Nothing counts it,
    nothing returns it, nothing prints it. `rescan` *would* have named it under *"LEFT BEHIND BY
    TRUESTILL"* - but only in the window before the restart, and only if the user happened to run
    `rescan`.

  ## THE PRECEDENT FOR WHAT "SAY WHAT YOU KNOW" COSTS

  `migrate-layout` already does this properly and is the shape to copy: it opens a run, resumes
  from it, and **says so** - `"Recovered {outcome.resumed} move(s) from an interrupted run."`,
  backed by a `resumed` count on its result. Copy-mode organize has no journal to replay, no
  `resumed` count, and no sentence.

  ⚠ **`(adx)` gap 1 is the other precedent, and the more sobering one**: disclosing something the
  product genuinely knows took a probe with a timeout, a per-process memo for wedged mounts, a
  three-valued reach model and a bounded thread that can only be abandoned. Saying what you know is
  rarely one line.

  ## ✅ BUILT 2026-08-20 - see `SHIPPED.md` for the closure

  Schema **v20**, `organize_runs`, one row per drive, superseding on start. Written before the
  first byte from both front ends; `intended_total` is the drive's **target holdings**; and
  "interrupted" is derived rather than read from a flag, so a crash between the last file and the
  close reads as complete. `.partial` detection was considered and left out, with the argument
  recorded. `rescan`'s heading reframed.

  ## WHAT WAS OPEN WHEN THIS WAS FILED

  - **Whether a copy-mode run should be journalled at all.** It buys the disclosure and it costs a
    write per run plus a table; `inplace_runs` exists because relocation is *undoable*, and a copy
    is not, so the justification has to be reporting rather than recovery.
  - **What an unfinished run should DO on the next open** - report and continue, or offer to
    resume. ⚠ Note the restart already resumes correctly today; only the *silence* is the defect.
  - **How long an `in_progress` row stays believable.** A row from a run killed six months ago is
    itself a stale claim - `(abg)`'s whole subject, one level out.
  - **Whether `drives` should distinguish "this drive was mid-write" from "this drive is small"**,
    which is where the user's question actually lands.
