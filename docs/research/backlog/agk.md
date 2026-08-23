# (agk) AN IN-PLACE RENAME IS NOT COVERED BY ANYTHING UNTIL AFTER IT HAS HAPPENED.

*Body of entry `(agk)`. **OPEN - designed, not built.** The index is [`BACKLOG.md`](../../BACKLOG.md); the provenance index is [`SHIPPED.md`](../../SHIPPED.md).*

> ## ⛔ DESIGN ONLY. DO NOT BUILD FROM THE ONE-LINE VERSION.
>
> `(agj)` reported this as *"`record_inplace_move` is an unguarded catalog write"*. **That framing
> invites the wrong fix.** Wrapping the write in `_record_or_stop` converts a silent lost undo row
> into a loud one; the file is still moved and still unrecoverable. **Guarding is the hot patch.
> Ordering is the root cause.**

## The maintainer's addendum, verbatim

*Reproduced as written, with one exception: the em-dash in its first line is normalized to
the repo's convention, because `dash-check` is absolute and a quoted em-dash still reaches a
reader. Nothing else is changed.*

```
ADDENDUM TO (agk) - READ BEFORE BUILDING.

Guarding record_inplace_move is not the fix. Write the journal row BEFORE
the rename, not after. If the row cannot be written, no rename happens and
there is nothing to undo. Guarding after the fact makes the loss loud, not
recoverable.

This is the classic intent-log ordering and the prior art is explicit:
Microsoft's TxF states the problem exactly - after a failure you cannot know
whether the rename happened, and blindly reversing it is wrong, so the log
record is written BEFORE the operation is requested. danluu's "Files are
hard" adds the half people miss: POSIX rename is atomic in normal operation
and NOT on crash.

So the row must be written first AND the reconciliation must be idempotent -
a row whose rename never happened must be distinguishable from one whose
rename did, by looking at the disk, not by trusting the row. Undo that fires
blindly on a row is a second defect.
```

## Q55 first, because it decides how seriously to read the rest

**Reproduced on real photographs from `~/TruestillLibrary/Input`**, copied to scratch: 150 files,
377 MB, ext4. Eight `organize --in-place --apply` runs, each `SIGKILL`ed at a different point in
the write loop, each scored by **inode** - a rename preserves it, so an inode at a new path is a
file that physically moved.

```
t1: moved= 21  journal_rows= 21  ORPHANS=0
t2: moved= 20  journal_rows= 20  ORPHANS=0
t3: moved= 28  journal_rows= 27  ORPHANS=1
t4: moved= 34  journal_rows= 34  ORPHANS=0
t5: moved= 38  journal_rows= 38  ORPHANS=0
t6: moved= 48  journal_rows= 48  ORPHANS=0
t7: moved= 50  journal_rows= 50  ORPHANS=0
t8: moved= 58  journal_rows= 57  ORPHANS=1

TOTAL: moved=297  rows=295  ORPHANS=2   (2 of 8 kills, 25%)
```

**One of them, end to end:**

```
was: .../t3/lib/Testing-new/IMG_20200710_214506_Bokeh.jpg
now: .../t3/lib/2020/2020-07/2020-07 - Everyday/20200710_214508_IMG_20200710_214506_Bokeh.jpg

catalog row for it : 0
journal row for it : 0

$ truestill undo-organize --apply
  restoring: 27/27
  Restored 27 file(s) to their original locations.

still at the organized path: YES
back at its original path  : NO
```

🔑 **`undo-organize` reported success and left the photograph displaced without mentioning it.**
The run's own confirmation prompt promises *"Reversible: `truestill undo-organize` restores every
file to where it is now"*. For this file that sentence is false, and nothing anywhere says so.

⚠ **The catalog row is missing too, which widens the defect from what `(agj)` reported.** The
unprotected span is not *"the journal write"* - it is **`rename → catalog row → journal row`**, and
a crash anywhere in it leaves a moved file. `(agj)` saw only the last third.

⚠ **The busy-contention route was tried first and does NOT reach it**, and the null result is
worth recording. `_tx` has no retry, so `record_inplace_move` has only `sqlite3.connect`'s 5 s
timeout - but firing it needs the lock free for the guarded write and held for >5 s for the
journal write **microseconds later**. A second process flapping 6 s holds against a 1,200-file
real run produced 40 holds and **zero** orphans: 1,200 files moved, 1,200 rows. The defect is
real by inspection on that path and not drivable from outside it; the crash window is the
reachable one.

## Q52 - is journal-before-rename reachable, or does the row need a value only the rename produces?

**Reachable. Every value the row carries is known before the rename.**

| column | source | known before the rename? |
|---|---|---|
| `run_id` | `relocation.run_id` | ✅ made when the run opened |
| `sha256` | `source_sha` | ✅ `_execute_one_write` computes it above the write |
| `old_relative` | `relocation.old_relative(decision.source)` | ✅ pure function of the source path |
| `new_relative` | `final_relative` | ✅ `_free_relative` runs above the write |

**But the row's *existence* is conditional on something not known in advance**, and that is the
real question. `_journal_or_delete_source` writes it only `if moved_in_place`, which is an
**output** of `_adopt_or_copy` - and that function records a deliberate ruling:

> *"The kernel decides, not `st_dev`: a rename is attempted and its refusal is trusted."*

So hoisting the rename/copy decision above the write would overturn a recorded design decision,
and is **not** on the table here.

**This leaves a genuine fork, and it is the STOP below.** A row written before the attempt
describes an intent that may not become a rename - a cross-device fallback copies instead, and the
row then describes nothing that happened. Q54 decides whether that is tolerable.

## Q53 - `_move_source` is already correct, so this is a divergence, not a new design

**`--move`'s copy-then-delete obeys the principle exactly**, and says so in its own docstring:

> *"Ordering guarantees no window with zero copies: the copy is already written and recorded;
> here we re-hash it and delete the source only if it matches. Any failure keeps the source."*

It never needs an undo row, because the destination copy exists and is **verified** before the
source is unlinked. The irreversible step is last, after the thing that makes it survivable.

🔑 **The in-place path inverts that and nothing recorded the inversion.** Its irreversible step -
the rename - happens *first*, and the thing that makes it survivable is written afterwards. Same
product, same user action, two opposite orderings.

**So the shape to copy is the principle, not the mechanism.** `_move_source` cannot be copied
literally: in-place has no second copy to verify, because the rename *is* the operation. What
transfers is *the irreversible step goes last, after its safety net is in place* - which for a
rename means the journal row.

## Q54 - what undo does today with a row whose rename did not happen

**It skips it, twice over, and reconciles against the disk rather than the row.** `plan_undo`:

* `if not step.current.is_file()` → `MOVED_AWAY` - nothing at `new_relative`, so nothing to reverse;
* `if step.original.exists()` → `ORIGIN_OCCUPIED` - the file is still at `old_relative`;

and `run_undo` **re-checks both immediately before moving**, because *"the preview may be minutes
old"*. A row whose rename never happened trips the first check, and would trip the second too.

**So undo does not fire blindly, and the addendum's second requirement is already half-built.**
That is what makes the reorder viable rather than a two-phase row with a `confirmed` column.

⚠ **But it verifies POSITION, never IDENTITY, and that becomes load-bearing the moment rows are
written first.** The row carries `sha256` and `run_undo` uses it only for `forget_organized` -
never to check that the file at `current` is the file the row describes. Today that is safe
because a row exists only after a confirmed rename. Once rows can describe renames that did not
happen, this sequence is reachable:

1. file A's intent row is written for `new_relative = X`; its rename falls back to a cross-device copy;
2. the row survives, describing a rename that never happened;
3. a later file B legitimately takes `X`, because `_free_relative` finds it free;
4. A's original path is emptied by something else, so `ORIGIN_OCCUPIED` no longer fires;
5. undo moves **B** to **A's** original path.

**Narrow, and it is exactly the class of thing this journal exists to prevent**, so it is named
rather than left for later. Verifying `sha256` before the move closes it - and closes it against
*any* stale row, not only this new source of them.

## The design

**Two parts, and the second is not optional.**

1. **Write the journal row immediately before `_adopt_or_copy`, not after.** Every value is
   available (Q52). If the row cannot be written, no rename is attempted and there is nothing to
   undo - which is the whole point, and the reason guarding the current call site is not the fix.
2. **Make undo verify the recorded `sha256` before it moves anything.** The reconciliation must
   tell *"this rename happened"* from *"this row describes an intent that did not"* **by looking
   at the disk** (Q54). Position is not identity.

**And a third question that the design raises rather than answers:** what clears an intent row
whose operation ended as a copy? Leaving it is safe once (2) lands, but it makes the journal a
record of intentions rather than of moves, and `inplace_runs.moves` counts rows. Deleting it costs
a second write on the fallback path, which is rare.

## ⛔ STOP - three rulings needed before any code

1. **Does the journal become a record of INTENTIONS or stay a record of MOVES?** The reorder makes
   it the former by construction. Either the fallback path deletes its row (a second write, on a
   rare path) or the semantics change and `inplace_runs.moves`, `undo`'s counts and the CLI's
   run listing are all reading a different thing than they say.
2. **Is hashing on undo acceptable?** Verifying identity means reading every file being restored.
   A size check first would reject most mismatches for free, but the honest guarantee needs the
   hash. On a large in-place run that is a real cost against a real risk, and it is a maintainer
   call, not mine.
3. **Is the widened span in scope?** The unprotected window is `rename → catalog row → journal
   row`, not the journal write alone. Moving the journal row above the rename closes all of it -
   but it means the journal row is committed before the catalog row, which reverses their current
   order and should be stated as intended rather than discovered later.

## Prior art

* **Microsoft TxF** - after a failure you cannot know whether the rename happened, and blindly
  reversing it is wrong; the log record is written **before** the operation is requested.
* **danluu, "Files are hard"** - POSIX `rename` is atomic in normal operation and **not** on
  crash. `LocalDestination.adopt`'s docstring already says this for FAT32/exFAT and names the
  journal as what covers it - **which is the claim this entry shows to be false today**, because
  the journal is written after the thing it is meant to cover.
* This repo's own `_move_source` (Q53), which is the same principle already applied correctly one
  branch away.
