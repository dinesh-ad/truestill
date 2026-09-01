# (ajg) `backup` STILL CRASHES ON A VANISHED DRIVE: `(ajd)` CAUGHT ONE EXCEPTION AND THERE ARE TWO

*Body of backlog entry `(ajg)`, under **Approved - still to build**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

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

## FIX

Catch `DestinationError` beside `BackupStoppedError` in `_cmd_backup` and print the same shape:
what landed first, then the sentence, then a next step. ⚠ **`DestinationError` carries no counts**,
which is why this is not a one-line addition - either it gains them the way `BackupStoppedError`
did, or the handler reports what it can and says the rest is unknown. **Do not print a count the
type cannot supply.**

## WHAT IS NOT ESTABLISHED

- **Whether any other `raise` on this path is also uncaught.** Two classes were found by trying
  one condition. Nothing has enumerated every `raise` reachable from `copy_to_drive`.
- **Whether `migrate` and `undo` have the same hole.** Both call the same device guard.
- **Whether a test can pin this without a loop device.** The condition is a mid-run device
  change; `DestinationDevice` latches `st_dev`, so a fake destination may reach it more cheaply.

## RELATED

`(ajd)` (the first arm), `(aiq)` (the app half of the same comparison - **inverted here**),
`(agi)` (the persistence classifier), [`soak-twelve-record.md`](../../soak-twelve-record.md) 12b.
