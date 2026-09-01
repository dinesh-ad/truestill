# (ajg) `backup` STILL CRASHES ON A VANISHED DRIVE: `(ajd)` CAUGHT ONE EXCEPTION AND THERE ARE TWO

*Body of entry `(ajg)`, **SHIPPED 2026-09-01**. The closure is in [`SHIPPED.md`](../../SHIPPED.md);
the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-09-01 from [`soak-twelve-record.md`](../../soak-twelve-record.md) 12b, **measured on a
loop device unmounted mid-copy**. One day after `(ajd)` shipped.

## MEASURED

`truestill backup ./lib <target> --apply`, target unmounted once 47 files had landed:

```
Traceback (most recent call last):
  File ".../cli.py", line 4296, in _cmd_backup
    outcome = copy_to_drive(
  File ".../backup.py", line 696, in copy_to_drive
    copied, copied_names, copied_bytes, failures = _copy_missing(
  File ".../backup.py", line 541, in _copy_missing
    run.device.check(run.target)
  File ".../destinations/base.py", line 88, in check
    raise DestinationError(message)
truestill_core.destinations.base.DestinationError: ... is no longer the drive this run started on
```

**Eight frames, source paths, exit 1, and no count of what landed.** The app, on the identical
condition, shows the sentence and nothing else - `jobs.py` wraps any exception.

## ROOT CAUSE, AND WHY `(ajd)` DID NOT COVER IT

`_cmd_backup` has exactly one handler: `except BackupStoppedError`. Two different classes reach
it from `_copy_missing`:

| raised by | class | caught? |
|---|---|---|
| the stop path `(ajd)` fixed | `BackupStoppedError` (an `OSError`) | ✅ |
| `run.device.check(run.target)`, `backup.py:541` | **`DestinationError`** | ❌ **walks straight past** |

`DestinationError` is neither `BackupStoppedError` nor an `OSError`, so the arm `(ajd)` added
cannot see it. `organize` catches it in **two** places (`cli.py:3267`, `:3808`); `backup` in
**none** - of six `DestinationError` hits in `cli.py`, not one is on the backup path.

🔑 **`(ajd)`'s own comment describes this outcome as the thing it closed**: *"a drive that vanished
mid-copy reached the user as a Python traceback while `organize` answered the identical accident
with a sentence and a count."* **Still true, for the other class, one day later.**

## THE CLASS, WHICH IS THE TRANSFERABLE PART

The 2026-08-31 handoff's **class C** - *"a guard defeated by the surface, not by the raise"* - with
its own DO applied one level too shallow. That DO says *"enumerate the surfaces and check each
one"*. It was enumerated **per exception**: `(ajd)` found the class that was escaping, caught it,
and stopped. **The unit that would have caught this is per (surface x raising call site)** - every
`raise` reachable from `_cmd_backup`, against every `except` it has.

## ✅ FIXED 2026-09-01 (P170) - ONE BOUNDARY, AND THE ENUMERATION WRITTEN DOWN

**Not another arm.** `_cmd_backup` now has a single handler over `cli._BACKUP_STOPS`, the shape
`organize` already uses (`_stopped_run_exit`, `except (RunStoppedError, DestinationError)`).

🔑 **THE ENUMERATION WAS DERIVED BY READING `_copy_missing`'s HANDLER, NOT BY COLLECTING
DEFECTS** - which is the whole correction. That handler catches `Exception`, writes the run record,
then wraps the cause in `BackupStoppedError` **only when it is an `OSError`** and bare-re-raises
everything else. So exactly four classes leave it:

| class | raised by | before P170 |
|---|---|---|
| `BackupStoppedError` | `_copy_missing`, wrapping an `OSError` cause | ✅ caught (`(ajd)`) |
| `ValueError` | `_stop_if_ground_moved`, the health watcher | ✅ caught |
| **`DestinationError`** | `device.check`, the vanished-drive guard - **a `RuntimeError`** | ❌ **traceback** |
| **`sqlite3.Error`** | `record_copy` / `mark_copy_verified` inside the loop | ❌ **traceback** |

⚠ **The fourth was found by READING, never by measurement**, and is named rather than omitted: no
soak has produced a catalog write failing mid-backup. Listing it costs one word; omitting it costs
this entry a third time.

**The count is not invented for the three that cannot supply one.** Only `BackupStoppedError`
carries `copied`. `DestinationError` comes from a guard that runs **before** each copy, so the run
may have copied many or none - printing `0 copied` would be the false custody record
`_stopped_run_exit` names as worse than no record. The run record is written for every abort
regardless, so nothing is lost.

⚠ **What was deliberately NOT done: core still attaches counts to one class only.**
`_copy_missing`'s handler holds `copied` and `failures` for **every** abort and gives them to the
`OSError` path alone. Widening that is a change to the raise, and this was scoped to the surface.
It is the obvious next move and it is not this entry.

## PROOF

`test_every_backup_stop_reaches_the_user_as_a_sentence.py` drives **every** member of
`_BACKUP_STOPS` through the real `main(["backup", ...])` boundary and asserts exit 4, a sentence,
and no traceback - so a fifth class added to core with no arm fails here, which a tuple alone could
never notice. Control green, then two mutations, **both caught and both restored**:

* reverting `_BACKUP_STOPS` to `(ajd)`'s two arms -> **5 failed**
* making the handler print `0 copied` for a type carrying no count -> **3 failed**

⚠ **The drift test caught its own author.** Its first form asserted `issubclass(OSError,
_BACKUP_STOPS)`, which is backwards - an `OSError` does not *arrive* as `OSError`, core wraps it
into `BackupStoppedError`. The test now states that mapping instead of assuming it.

## WHAT IS NOT ESTABLISHED

- **Whether any other `raise` on this path is also uncaught.** Two classes were found by trying
  one condition. Nothing has enumerated every `raise` reachable from `copy_to_drive`.
- **Whether `migrate` and `undo` have the same hole.** Both call the same device guard.
- **Whether a test can pin this without a loop device.** The condition is a mid-run device
  change; `DestinationDevice` latches `st_dev`, so a fake destination may reach it more cheaply.

## RELATED

`(ajd)` (the first arm), `(aiq)` (the app half of the same comparison - **inverted here**),
`(agi)` (the persistence classifier), [`soak-twelve-record.md`](../../soak-twelve-record.md) 12b.
