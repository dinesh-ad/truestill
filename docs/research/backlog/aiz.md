# (aiz) AN INTERRUPTED BACKUP IS NOW RECOVERABLE: THE SECOND RUN ASKS THE TARGET.

*Body of entry `(aiz)`, **partly shipped 2026-08-31** - the closure is in
[`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with
[`BACKLOG.md`](../../BACKLOG.md).*

> ⚠ **RETITLED ON CLOSURE.** It was filed as *"success is reported before the medium has the
> bytes, and both instruments that would catch it read the page cache"* - which is what was
> measured and is still true. **WHAT SHIPPED IS THE CONSEQUENCE, NOT THE WINDOW**, and the wording
> question left over is `(ajf)`. The row is still written before the bytes
> are durable, and the summary still says *"Copied 356 file(s)"* while they are in RAM - **that
> wording is a product call and was deliberately not made here.** What shipped is that the false
> row **no longer defends itself**: the next `backup` asks the target and re-copies. The window
> remains; its permanence does not.

Filed 2026-08-31 (P165, soak ten), measured on **real removable media**: exFAT on a SanDisk Cruzer
Blade, kernel driver, **write 1.34 MiB/s, read 19.7-23.3 MiB/s**. The run is
[`soak-ten-record.md`](../../soak-ten-record.md).

## ⚠ WHAT THIS ENTRY DOES NOT CLAIM, FIRST, BECAUSE IT IS EASY TO MISREAD

**Nothing was lost.** Every one of 712 copies verified byte-identical off the medium, cold, after
an unclean physical removal. The window below is real; the loss is **conditional on a pull inside
it**, and **that pull is unmeasured** - see the record's §7. This is not a report of data loss.

**And it is not an argument for `fsync`.** `safe_copy.py` refuses one in its own module docstring,
with reasons:

> **No `fsync`, deliberately - do not add one as an obvious improvement.** … `fsync` addresses
> whether *content* survives power loss, which `copy_sha256` and `verify` already own.

That ruling is left standing. **What is filed here is that the two mechanisms it nominates cannot
see into the window it creates.**

## MEASURED

```
From 'Damon exFAT' to 'Damon Backup': 356 file(s) to copy, 717 MB.
Copied 356 file(s), 717 MB.                                        <- 4.74 s wall
```

At the instant that printed: **570 MiB still dirty in RAM**, device needing ~7 more minutes at its
measured rate. `organize --apply` is the same shape - 4.08 s, 649 MB outstanding.

**This is `backup`** - the 3-2-1 command, whose only job is that a second copy exists somewhere
else - reporting the copy made roughly ninety seconds of device time into a nine-minute write.

## 🔑 THE TWO INSTRUMENTS, AND THE TIMING THAT PROVES EACH IS BLIND

| instrument | what it does | why it cannot see |
|---|---|---|
| `backup`'s destination check (`backup.py`'s `_copy_verified`) | `written = sha256_file(staged.temp)` before the staged file takes its real name - correct, and it is what `(abu)`/`(acj)` built | **717 MB hashed inside 4.74 s is 151 MB/s on a stick that reads at 19.7.** It never touched the device: it compared the kernel's copy of the bytes against the source's copy, both in RAM |
| `verify` | reads every byte and re-hashes | **1.45 s warm against 35.18 s cold** over the identical 356 files - a 24x tell. Asked soonest after a write, which is when a user asks, it answers from the page cache |

**The read rate is the instrument here**, not an assertion about caching: 151 MB/s and 19.7 MiB/s
cannot both be the same device, and the cold runs (29-36 s) are what reading this medium costs.

## WHY IT IS THE REMEDY AND NOT THE RULING

The no-`fsync` decision is a trade the product is entitled to make, and it names its replacement:
*"`copy_sha256` and `verify` already own"* content survival. **A remedy that is nominated has to
work when it is invoked.** Both of these are correct against a **corrupted** write - a truncated
copy, a bad byte - and neither is correct against a write the device **has not received yet**.
That is a different failure and it is the one removable media produces.

⚠ **On a fixed disk this is invisible**, which is why every soak before this one missed it: soaks
one through nine ran on ext4 or against an injected `errno`, and a 1.34 MiB/s medium is what makes
a 4.74-second lie visible at all.

## THE FIELD SETTLED THIS FOR `rsync`, AND THE SAME CAVEAT APPLIES

**Not a novel problem.** Ted Ts'o argued on LKML that `rsync` should call **`sync()` before
exiting** - *"not a big deal, and not all that costly"* - and **Chris Mason stated this entry's
case exactly, in 2009**:

> *"If we crash just after the rsync, the backup logs won't know."*

**A backup log that does not know is a `file_copies` row for bytes the medium never received.**
Seventeen years earlier, in someone else's words, about someone else's tool.

⚠ **AND THE CAVEAT IS AS LOAD-BEARING AS THE REMEDY - fsyncgate.** `sync()` makes the **timing**
honest and **cannot make the outcome certain**: a writeback failure can leave pages **neither
written nor marked dirty**, so a later `sync()` returns success over data that is already gone.
So `sync()` answers *"has the device been given a chance to take this?"* and **does not answer**
*"did it take it?"*. **The second question is `verify`'s**, which is why this entry is filed
against the instruments rather than against the write path: a `sync()` at the end of a run would
fix the sentence the user reads, and would still leave `verify` reading RAM.

## WHAT IS NOT ESTABLISHED

- **What the fix is.** Candidates, none ruled: `verify` opening with `O_DIRECT` or advising
  `POSIX_FADV_DONTNEED` before reading; a durability step at the end of a run rather than per file
  (one `syncfs` is not a per-file write-through and the docstring's cost argument does not reach
  it); or saying plainly in the summary that the copy is not yet on the medium. **The cheapest
  honest option may be wording rather than machinery**, and that is not obviously right.
- **Whether the catalog row should wait.** A `file_copies` row is a custody claim, written before
  the medium has the bytes. That is `(ain)`'s false-custody shape arriving from durability rather
  than from an errno - **and `(ain)`'s own ruling, *"keep the file and record it, never roll it
  back"*, was decided for a case where the bytes had committed.** Whether it extends to a case
  where they have not is a real question and this entry does not answer it.
- **Every other destination.** Measured on one exFAT stick. rclone remotes, SMB and NFS have their
  own write-completion semantics and none were touched.

## RELATED

`(ain)` (false custody, from the errno side), `(aie)`, `(abu)` and `(acj)` (the
verify-before-naming design this entry says is right and mis-scoped),
[`soak-ten-record.md`](../../soak-ten-record.md) §5.
