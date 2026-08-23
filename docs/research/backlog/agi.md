# (agi) `ENOSPC` IS NOT A PER-FILE FACT, AND BOTH SURFACES TREAT IT AS ONE.

*Body of entry `(agi)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-23 - both surfaces, one commit
>
> `drive_unwritable.persists_for_the_run` answers one question - **will the next file hit this
> too?** - and `organizer.py` and `service/backup.py` both consult it. **The errno table is the
> implementation of that predicate, never the rule**, so every branch carries why the condition
> outlives the file, and an errno nobody has reasoned about continues.
>
> 🔑 **`ENOSPC` is persistent for a MECHANISM, not an inference, and that is the entry's best
> argument.** A full copy-on-write filesystem does not merely fail this write: btrfs needs to
> allocate metadata even to **delete**, so it can refuse the cleanup as well, and it *"will change
> your filesystem to read-only to protect itself"*. At that point every remaining file fails.
> Continuing buys N failures describing one condition.
>
> ### ⚠ TWO DEFECTS IN THE FIRST DRAFT, BOTH CAUGHT BY ITS OWN TESTS
>
> **1. It was INERT on organize, the surface that runs most.** The predicate took an `OSError` and
> the handler tested `isinstance(exc, OSError)` - but `LocalDestination.upload` raises
> `DestinationError(...) from outcome.error`, so organize never sees a bare `OSError` and the
> check never fired. Fixed at the root: the predicate walks the **cause chain**, in one place, so
> neither surface has to unwrap. **This is the "stops one step short of the property it claims"
> defect this repo is built around, committed and then caught by an end-to-end test that a unit
> test of the table could never have caught.**
>
> **2. The abort threw away the errno.** `raise OSError(verdict.detail)` carries `errno=None`, so
> nothing downstream could classify it again or word it through `drive_unwritable`. Backup now
> re-raises with the original errno and cause; organize re-raises the original exception object,
> wrapper and all, so the drive-worded sentence a user reads survives.
>
> ### What was proven, and what is assumed
>
> ✅ **Linux: a real kernel `ENOSPC`**, delivered through `shutil` from `/dev/full` on both
> surfaces. A synthesised `OSError` proves the classifier and says nothing about delivery.
> ✅ A real `EACCES` from `chmod 000`, for the continue side.
> ⚠ **Windows: the errno-to-verdict mapping is proven; the winerror-to-errno DELIVERY is assumed.**
> `ERROR_DISK_FULL` (112) and `ERROR_HANDLE_DISK_FULL` (39) reach Python as `ENOSPC` by Python's
> own translation, documented and **not exercised by any test here**. **A green Windows lane must
> not be read as evidence of it.** Costed and not built: `diskpart` can create and attach a small
> VHD and the runners do have administrator, so a real full volume is roughly 15-30 s of CI on one
> platform, for a test that cannot run locally. Worth doing only if this errno ever misbehaves.
>
> ### Q45 - the preview sees the static case and not these
>
> `backup_preview` already compares `shutil.disk_usage(target).free` against `need`, so an obvious
> shortfall is refused before a run starts. It **cannot** see the cases that reach this classifier:
> a disk filled by another process after the preview, a **quota** (invisible in `free`), or the
> **local cache** disk filling while the target has room - which is the case `RunHealth` exists
> for. So the abort message does not claim the preview knew, because usually it did not.
>

- **(agi)** Recorded 2026-08-23 by `(afw)` Stage 4, which made backup adopt organize's
  partial-failure policy and in doing so inherited organize's gap.

  ## What is true after `(afw)`

  Both surfaces now continue past a per-file failure, which is
  `ENGINEERING_STANDARD.md` §4 Errors and is right. **Neither classifies the failure**, so an
  `ENOSPC` - the destination filling - is treated exactly like an unreadable source file:

  - `organizer.py`'s `except (OSError, DestinationError)` records `FAILED` and does not break.
  - `service/backup.py`'s `_copy_verified` returns a failed verdict and the loop carries on.

  **Destination-level abort is delegated entirely to two periodic guards**:
  `run_health` (`_stop_if_ground_moved`, a tick every `TICK_SECONDS`) and `DestinationDevice.check`
  (fails closed on the first bad reading, but only for a changed device). Neither is the copy's
  own errno.

  ⚠ **Organize is the bigger instance.** It runs far more often than backup, and it has had this
  shape since long before `(afw)`.

  ## PRIOR ART, recorded so it is not argued from first principles later

  | | |
  |---|---|
  | **rsync** | gives `ENOSPC` its **own fatal exit 11**, deliberately distinct from the per-file **23** (*"partial transfer due to error"*, which is *"anything that doesn't have its own exit code"*) |
  | **restic** | a destination-write or connectivity failure is **fatal, no snapshot created**; source-read errors give exit **3** with a snapshot still made |
  | **rclone** | ⚠ **the counter-example, and the useful one**: it does **not** treat `ENOSPC` as fatal, and carries open issues asking it to - rclone#6355 *"rclone doesn't terminate when no space left on device"* and rclone#5308 |

  🔑 **rclone's behaviour is exactly ours, and its users file it as a defect.** That is stronger
  evidence than the two who got it right, because it is the same design being reported by people
  living with it.

  ## THE HARM, STATED HONESTLY - this is not data loss

  Staging means **nothing corrupt reaches the target**: `safe_copy.staged_copy` writes to a
  per-process sibling and only a verified copy is renamed into place. So the cost of continuing
  through a full disk is:

  - **N wasted attempts**, one per remaining file, each a full read of the source; and
  - **N record entries reading `failed`** when the truth is *one condition, at file 12*.

  That second one is the `(afa)` shape at run scale: a record that misdescribes its own cause.
  A user reading *"3,847 files failed"* cannot tell it from a genuinely rotten library.

  ## ⚠ WHAT `(afw)` MEASURED AND WHY IT DID NOT ACT

  The classification mechanism is narrower than it looks, and this is the part worth keeping:

  ```
  source unreadable   errno=13  filename='<src>/a.jpg'
  dest unwritable     errno=13  filename='<dst>/a.jpg.partial'
  ENOSPC mid-copy     errno=28  filename=None  filename2=None
  ```

  **`OSError.filename` identifies the side only for OPEN-time failures.** On the fast path
  (`copy_file_range`/`sendfile`, both enabled here) a mid-copy failure carries neither filename.
  So a mid-copy failure is classifiable **by errno only, never by side** - which is sufficient
  for `ENOSPC`, and is not the general source-vs-destination split it first appears to be.

  **And it must not be built for backup alone.** Classifying in one surface would make it
  stricter than the other and recreate the divergence `(afw)` Stage 4 existed to remove.

  ## DO NOT WRITE A SECOND ERRNO TABLE

  `drive_unwritable.classify_unwritable` is *"the only errno table in the product"* by `(aek)`'s
  design, and `(aep)` ruled that the remedy is to **reach** it rather than add another. It already
  carries `NO_SPACE`, `QUOTA`, `GONE`, `FAILING`, `REFUSED`, `OTHER`.

  ## ALSO CARRIED BY THIS LETTER

  Three residues from `(afw)` Stages 3 and 4, here rather than dangling:

  - **No third job state.** `jobs.py` has `done` and `error`. A backup that copied 393 of 394 is
    neither, and the app currently renders it as an ordinary success.
  - **The run record's location is never told.** `(afu)`'s lesson - a record nobody can find one
    level up.
  - **`failed` is in the payload and unrendered.** `app.js`'s `backupCompletion` reads `verified`
    and ignores `failed`, so the count exists and no one sees it.

  ## RELATED

  `(afw)` (which produced this), `(aek)` and `(aep)` (the one errno table and the rule to reach
  it), `(afa)` (one word standing for several causes), `(aft)` (the same module's other axis).
