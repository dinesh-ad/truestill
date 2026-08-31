# (ajd) `backup` LETS SOME `OSError`s ESCAPE AS A PYTHON TRACEBACK, WHERE `organize` WRITES A SENTENCE.

> ⚠ **Filed the same day as *"`backup` LETS `OSError` ESCAPE TO THE USER AS A PYTHON TRACEBACK,
> WHERE `organize` WRITES A SENTENCE"*, and narrowed within the hour.** The original said `OSError`
> unqualified; measurement then showed `backup` handling the FAT32 size ceiling **correctly** -
> clean message, exit 1, the 4 GiB `.partial` removed. **SOME** errnos are classified and some
> escape, which is a more useful claim than the one first written and a narrower one.

*Body of backlog entry `(ajd)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-31 (P166, soak eleven, pass 2), measured twice on real removable media. The run is
[`soak-eleven-record.md`](../../soak-eleven-record.md).

## MEASURED - TWICE, ON TWO DIFFERENT CODE PATHS

**(1) The drive vanishes mid-copy** (`backup.py:490` -> `_stop_the_run` at `:338`):

```
OSError: [Errno 5] copying 2014/…/20140815_155529_2014815155529.jpg failed:
  [Errno 5] Input/output error: '/run/media/…/drive/…' -> '/run/media/…/backup/….partial'
  File ".../backup.py", line 490, in _copy_missing
    _stop_the_run(verdict)
  File ".../backup.py", line 338, in _stop_the_run
    raise OSError(verdict.error.errno, verdict.detail) from verdict.error
```

**(2) The recovery run, against a repaired-but-damaged volume** (`backup.py:478`):

```
OSError: [Errno 22] Invalid argument:
  '/run/media/…/backup/2014/2014-08/2014-08-14 - Wayanad Monsoon 2014/2014-08-15'
  File ".../backup.py", line 478, in _copy_missing
    dst.parent.mkdir(parents=True, exist_ok=True)
```

**Raw tracebacks with source paths and line numbers, straight to the terminal.**

## 🔑 THE COMPARISON THAT MAKES IT A DEFECT RATHER THAN A STYLE NOTE

`organize` met **the identical accident** - the same stick, physically pulled mid-write, four hours
earlier - and answered:

```
FAILED: IMG_2420.JPG: could not copy IMG_2420.JPG to '2014/…/20140816_142119_IMG_2420.JPG':
  the drive stopped responding part way through …
     2062  organized     1  failed     478  not attempted        RUN EXIT=4
```

**A named file, a cause in English, a count of what was and was not done, and a non-zero exit.**
`ENGINEERING_STANDARD.md` §4's shape, and `(aim)`'s divergence line working.

**Same product, same event, two entirely different experiences.** One command classifies a vanished
drive; the other lets the exception reach the top of the process.

## WHY IT MATTERS MORE FOR `backup` THAN IT WOULD ANYWHERE ELSE

**`backup` is the command a user runs when they are already worried.** It is the 3-2-1 step, and it
is most often pointed at removable media - the one destination that disappears. **A traceback is
the worst possible answer to *"is my second copy safe?"***: it names no file the user recognises,
gives no remedy, and does not say how much was copied before it stopped.

⚠ **And the second instance is worse than the first**, because it is on the **recovery** path. A
user whose backup was interrupted re-runs it - the obvious remedy - and gets a stack trace from
`pathlib`. `(aja)` measured the exFAT version of that moment (a false all-clear); this is the NTFS
version, and neither leaves the user anywhere to go.

## WHAT IS NOT ESTABLISHED

- **The exit code on a vanished drive is UNMEASURED.** The soak's own harness piped the command
  through `tail`, so the `0` it recorded is `tail`'s. **A harness error, named so nobody quotes the
  number**; the second instance exited **1**, which is at least non-zero but is Python's default
  for an uncaught exception rather than a chosen code.
- **Whether `_stop_the_run` should classify or the caller should catch.** `errno_table`-style
  wording exists elsewhere in the product; whether `EIO` and `EINVAL` from a disappearing device
  belong there, or whether `backup` needs the `MigrationStop` treatment `migrate` already has, is
  not decided here.
- **What a partial backup should report.** `organize` says `478 not attempted`. `backup` says
  nothing about how many of the 2,540 it had done - the user cannot tell 124 from 2,000 without
  running `verify` themselves.

## RELATED

`(aim)` (the divergence line `organize` has and this does not), `(aja)` (the same moment on exFAT,
where the failure is silent instead of loud), `(aiz)`,
[`soak-eleven-record.md`](../../soak-eleven-record.md) pass 2.
