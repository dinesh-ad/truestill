# Soak three - what the product does when the filesystem says no. RAN 2026-08-21.

**A record. Never rewritten to match the present; corrections go beside it, dated.**
The plan is [`soak-three-plan.md`](soak-three-plan.md). Run in the order the maintainer set: **R4
first**, because it was the only row with a destructive consequence and no signal, then R3,
then R1, R2, R5, R6.

## The result in one line

**Six steps, four findings, and the two most dangerous properties held.** No automatic path keys
off a "gone" verdict, and a destination that refuses mid-run corrupts nothing. What failed is what
the product **says**, and in one case that it stops saying anything at all.

| step | verdict |
|---|---|
| **R4** drive unmounts under a job | ⚠ **`(afc)`** - and the central question answered: **no** |
| **R3** destination refuses mid-run | ⚠ **`(afd)`** - every safety property held |
| **R1** unreadable source files | ⚠ folded into `(afd)`: the remedy exists only on the preview |
| **R2** unreadable source **parent** | ✅ correct. One asymmetry, folded into `(afd)` |
| **R5** catalog goes unwritable mid-run | ⚠ **`(afe)`** - the worst of the soak |
| **R6** read-only media as a source | ✅ correct, both halves |

## R4 - the question it was run first to answer

**Does any path that deletes, moves, or updates the catalog key off a verdict that would read
"gone" for a drive that is merely unmounted?** Read, then run. **No.**

- `undo.forget_organized` (`undo.py:215`) is gated on `step.current.is_file()` **and** a successful
  `rename`; on an unmounted drive the step is skipped, not forgotten.
- `migrate.forget_migration_move` (`migrate.py:786`) is gated on a successful `relocate` **and** a
  re-hash.
- `reclaim`'s two gates fail safe, now pinned by `(aez)`.
- `drives` reported **`offline`, 40 files, NOT FOUND `-`** - exactly right.

**The destructive step is the one the user is told to take.** `verify` on the unmounted mountpoint
says *"isn't a Truestill drive yet - register it with `drives --init`"*; following it mints a second
identity and writes a marker **into the mountpoint**, after which the real drive cannot mount there
again. `(afc)`. ⚠ **The correct wording already exists and fires on the unclean case** - kill the
daemon instead and the same command warns *"Do NOT register the folder again while the drive is
disconnected"*. The case with no errno takes the wrong branch.

## R3 - what the plan existed for, and it mostly holds

Destination flipped to `EACCES` after ten of 244 files had landed. **Catalog matched disk exactly
(10/10), `.partial` was used throughout, the one left behind was cleaned up by the next run, a
re-run resumed rather than re-copied, and §1's accounting was complete** - the single unrecorded
source was a byte-identical duplicate, **named** as `[SKIP: exact duplicate]`.

What failed is volume and wording: **233 uncapped `FAILED` lines, 2,004 lines of output**, each
carrying raw `[Errno 13]` text and two absolute paths. `(afd)`.

## R5 - the worst, and the only step that broke a safety rule

`chmod 555` on the catalog's directory mid-run: **the batch aborted**, no `EXECUTED` block printed,
the last line the user sees is `sqlite3.OperationalError: attempt to write a readonly database`
with our own line numbers, and **48 files are on disk against 47 rows**. `(afe)`.

⚠ **The gap is in the safe direction** - the copy lands before the row is written, so a crash
leaves a file with no row, never a row with no file. The defect is that nothing reports it.

**Why the destination survived the same test and the catalog did not**: a destination write is
inside the per-file `try` that §1's policy is built on. A catalog write is not inside anything.

## Two harness notes, recorded because each cost a step

- ⚠ **`pkill -f refusefs.py` killed my own shell** - the pattern matched the command line running
  it. Soak two recorded this exact trap (`pgrep -f` matching its own shell) and it was hit again.
  **Launch with a PID file; never pattern-match a process by a string your own command contains.**
- **The first R3 attempt flipped the destination four seconds in, and the run had already
  finished** - 40 small files organize faster than a sleep. The fix was to trigger on the *fifth
  landed file* rather than on a clock. A timing harness that misses its window reports a green
  that means nothing.

## What was NOT tested, stated rather than implied

- **S11, a genuinely full block device.** No `sudo`, no `unshare -Ur`, so no loopback. R3's
  `ENOSPC` variant reaches the same errno but not the same condition - no short writes, no
  metadata exhaustion. **Unrun.**
- **S6, interrupt-and-resume.** Kept in the plan, not reached in this session.
- **Windows and macOS.** Every step is Linux-only: `chmod 000` does not deny the owner on Windows,
  and neither `EROFS` nor `ENOTCONN` arrives by the same route.
- **The app's screens.** Every step read the CLI. The Backups screen's wording under R4 is
  untested.

## The thesis held

The stock-take predicted the defects are in *"paths that only execute when something is wrong"*.
Four findings in six steps, all of them there, and **none reachable by organizing a healthy
library**. The two properties most worth protecting - no automatic destruction on a false "gone",
and no catalog corruption from a mid-run refusal - **both held**, which is worth as much as the
findings.
