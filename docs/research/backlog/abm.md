# (abm) A BACKUP THAT SKIPPED A FOLDER SAID IT WAS COMPLETE.

*Body of backlog entry `(abm)`, now in [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abm) A BACKUP THAT SKIPPED A FOLDER SAID IT WAS COMPLETE.** Recorded 2026-08-06 while fixing
  the walk that produced the third of its fields; shipped 2026-08-25 (P85).

  *Titled* **"Attach counts three things and shows none of them"** *until the ruling below. The
  fields were the symptom; the sentence was the defect.*

  ## AS FILED

  - `DriveAttachment.unreadable` (files), `.unmatched` (on the drive, unknown to the catalog) and
    now `.unreadable_dirs` (folders that could not be listed) are all computed, tested, and read
    by nobody: `service/backup.py` uses `src.linked + tgt.linked` for `will_read` and **discards
    the return value entirely on the run path**. So a drive can attach with folders skipped and
    the screen says only how many files were linked.
  - **Deliberately not fixed with the walk.** The walk fix stops the fact being *destroyed*;
    showing it is a payload key plus a render plus a browser test, and doing one of the three
    siblings would leave the other two - which is how they got here.
  - **`service/fs_browse.py:188` rides along.** Its `rglob` undercounts a locked subfolder in the
    browse dialog's media estimate. Left as `rglob` on purpose: that number is already advisory
    and already truncated by `cap` (`media_capped`), which distorts it more than a locked folder
    does, and there is nowhere on a file-picker row to name a folder. Swapping the walk without a
    surface would recreate exactly the computed-and-dropped value this entry exists to close.

  ## ⚠ THE ENTRY UNDERSTATED ITSELF. THIS IS NOT A MISSING COUNT.

  A file under a folder the attach could not list never gets a `file_copies` row.
  `_files_missing_on_target` selects from `catalog.copies_on_drive(source_uuid)`, so that photo is
  **never a candidate to copy** - and both surfaces then say so out loud:

  | surface | what it said |
  |---|---|
  | `cli.py` | *"Nothing to copy - every file is already on that drive."* |
  | `app.js` | *"Already backed up. Every photo on X is already on Y."* |

  **Both are false about a file nobody looked for.** Measured in
  `test_attach_unreadable_folder.py`: five files, three under a `chmod 000` folder, two rows
  written - and *"verify could not check them, status would not count them toward 3-2-1 and where
  could not find them."* The walk fix preserved the fact; the harm was untouched.

  ## THE RULING: THREE FIELDS, THREE ANSWERS

  Treating them as one question is how they got here, so they were ruled apart.

  | field | answer |
  |---|---|
  | `unreadable_dirs` | **surfaced** - it changes the truth of a safety claim |
  | `unreadable` | **surfaced with it** - same banner; splitting them recreates the do-one-leave-two failure this entry names |
  | `unmatched` | **pointed at `rescan`** - the fact already has a better home |

  🔑 **`unmatched`'s fact is not homeless, it is better housed.** `truestill rescan` names each
  file rather than counting them:

  > **ON THE DRIVE, NOT IN THE CATALOG** - *"files Truestill has no record of. Copied in by hand,
  > restored, or added since."*

  A second, weaker vocabulary for that fact is the drift this repo files entries about, so the
  attach keeps the field for its own use and no screen re-states it.

  **Deletion was refused on measurement, not taste.** `attach_drive(write=True)` is called for its
  **side effects** at `service/backup.py:182-183`, so the walk is paid for either way;
  `unmatched += sha is None` is an increment and `unreadable_dirs` is a tuple the walk already
  built. Removing them costs a behaviour change and buys no cycles.

  ## ⚠ THE MECHANISM: OVERTAKEN THE DAY AFTER IT WAS FILED

  `truestill rescan` shipped **2026-08-07** (`372fb22`), **one day** after this entry was recorded
  on 2026-08-06, and carried `stray`, `unreadable_files` and `unreadable_dirs` in its **first**
  commit. For eighteen days the entry said the facts reached nobody while a shipped command named
  all three, better.

  **The tenth false-when-written premise this month, and the first whose fix shipped the next
  day.**

  ⚠ **What would have caught it: nothing, and that is not a shrug.** `(ago)`'s guard checks that
  a cited FILE and LINE exist, not that a claim is still true. `test_backlog_references.py` checks
  the inverse case - a *settled* item described as pending - and `(abm)` was open. Catching this
  mechanically means knowing which user-facing surface reports which fact, which is exactly the
  route-to-payload join `(ahn)` measured as absent (**50 routes, all 50 handlers annotated
  `-> JSONResponse`**). **So this is the same blindness as condition 3, met from the other side**,
  and it is recorded rather than guarded because the guard is `(ahn)`'s work, not a new artifact
  here (`(ago)`'s own rule about when one is worth it).

  ## WHAT SHIPPED

  One wording home in `truestill_core/backup.py` (`UNREAD_FOLDERS_TITLE`, `UNREAD_FOLDERS_REASON`),
  four keys on the backup preview payload, and a banner on **both** cards - including the
  nothing-to-copy one, which is where the reassurance is most wrong. `app.js` words nothing
  itself, which `(ahc)` settled and a test pins by reading `app.js` as text.

  The CLI cannot name the folders - it deliberately does not attach - so its sentence was made
  honest about what it compared and points at `truestill rescan`, which walks.

  ## RELATED

  `(ahl)` (the census this is invisible to - `DriveAttachment` is a dataclass, not a TypedDict),
  `(ahn)` (the join that would have caught it), `(ahc)` (one wording home, and the payload-carries-
  the-words shape), `(afn)` (saying the wrong reason is worse than the silence it replaces).
