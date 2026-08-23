# (agk) AN IN-PLACE RENAME IS NOT COVERED BY ANYTHING UNTIL AFTER IT HAS HAPPENED.

*Body of entry `(agk)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-23 - all three rulings, one commit
>
> Order is now **journal intent → rename → catalog row → journal outcome**, undo verifies
> identity, and the readers say `intended` / `renamed` / `unknown`. **The eight-kill harness that
> found this scores zero orphans**, against 2 of 8 before.
>
> ## ⛔ THE DESIGN GATE THIS ENTRY WENT THROUGH, KEPT
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

## Why this was a release blocker rather than a backlog item

**The in-place cohort has no options, and that is the whole argument.** Someone choosing in-place
is choosing it *because they have no room for a second copy*. So they also cannot take a backup
before running it, they have the least room for any safety net, and they are the most likely to hit
a full destination - `(agi)`'s condition. **The mode that most needs a working undo is the mode
whose users are least able to recover without one.**

Alongside it, the closest real-world match to this defect: a Lightroom Classic user whose folder
move stalled, who pressed cancel, and whose photographs were then unreachable - catalog thumbnails
present, disk empty, every option greyed out. That is what our 2-in-8 looks like to the person it
happens to, and they did nothing wrong. `user-evidence-log.md` §1 and §6.

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

## What shipped, and the three rulings as built

**Ruling 1 - an intent log, and no `confirmed` column as a trust anchor.** `inplace_moves` gains
`outcome` (NULL | `'renamed'` | `'copied'`) and `size`; `moved_at` is **renamed** to
`recorded_at`, because a column called *moved_at* on a row that may describe a rename which never
happened is the reader asserting what it no longer knows. `inplace_runs()` returns `intended`,
`renamed` and `unknown` in place of one `moves`, and the CLI listing prints all three with a line
saying what `unknown` means. ⚠ **NULL is UNKNOWN, never "did not happen"** - and that is the
cry-wolf the mutation matrix pins hardest.

⚠ **THE MIGRATION CARRIES NO BACKFILL, AND THE FIRST DRAFT DID.** Every pre-v21 row was written
after a completed rename, so `'renamed'` would have been true - and
`test_migration_safety.py`'s guard refused it, correctly: DDL autocommits and DML does not, so a
crash between them commits the column, rolls back the data, and the retry **skips** the backfill
because the column already exists. Leaving old rows NULL turned out to be the better rule rather
than a concession: **the journal never asserts an outcome it did not observe**, including for rows
that predate the field. A `DEFAULT 'renamed'` was rejected for the mirror reason - it would make
any future insert that omits the column claim a rename happened.

**Ruling 2 - undo verifies identity.** `size` rejects for free, the SHA-256 confirms, and
unreadable is a **refusal** rather than a pass. Q59's five-step sequence is built as a test rather
than described.

**Ruling 3 - the whole span, one commit.** `journal intent → rename → catalog row → journal
outcome`. The journal is the recovery record and the catalog is derivable by `rescan`, so the
journal row committing before the catalog row is correct rather than merely tolerable.

## Q56 - undo's message, and the lie did not stand one level up

⚠ **Undo's honesty machinery was already complete; the defect starved it of input.** It prints
`cannot restore: <name> -- <detail>`, then `N file(s) could not be restored; the run stays open`,
and exits 1. The reproduction printed a clean *"Restored 27 file(s)"* because **there was no row
at all** - nothing to skip. With the intent row present, the same crash now reports:

```
run id                            when          intended  renamed  unknown  status
7710a02eb17a44e5a988def2c3e37845  ...                  16       15        1  in_progress

  'unknown' means the outcome was never recorded - which is NOT the same as nothing having happened.

$ truestill undo-organize --apply
  cannot restore: IMG_20200629_212650.jpg -- no longer at the path this run left it
  Restored 15 file(s) to their original locations.
  1 file(s) could not be restored; the run stays open ...
```

**All 15 moved files restored; 0 left displaced.**

⚠ **One wording defect this exposed, and fixed.** A row whose rename never happened was reported
as `MOVED_AWAY` - *"no longer at the path this run left it"* - which is false about a file the run
never moved, and it spent the exit code on it. The disk distinguishes them (nothing at the new
path **and** the file still at the old one), so it is now `NEVER_MOVED`, excluded from the failure
count and from the exit code. **A file that was never moved is not one that could not be
restored.**

## Q57 - the second write, measured against a real run

| | |
|---|---|
| `record_inplace_outcome` | median **0.060 ms**, p95 0.071 ms (n=2,000, real catalog) |
| a real in-place run | **13.7 ms/file** (150 real photographs, 2.05 s) |
| share of per-file cost | **0.44%** |
| extrapolated to 33,000 files | **~2.1 s** |

**Not material**, declared before choosing as asked.

## Q58 - replay is idempotent against the disk, not the row

`_execute_one_write`'s `_already_at_target` check runs **before** the intent is recorded, so a
second in-place run over an organized folder writes no new intent and moves nothing. A guard keyed
on the journal would be wrong in both directions: a row exists for renames that did not happen,
and no row exists for a folder organized by an earlier install.

## Proof

Twelve tests, **9 of 10 failing against pre-change source** (the tenth is a cry-wolf half, which
must pass in both directions). Ten mutations, all caught, against an unmutated control:

| # | mutation | direction |
|---|---|---|
| 1 | nothing is recorded before the rename | defect |
| 2 | the outcome is never written back | defect |
| 3 | undo checks position only | defect |
| 4 | never-moved collapses into moved-away | defect |
| 5 | absence of an outcome read as "did not happen" | ⚠ cry-wolf |
| 6 | undo hashes and refuses every legitimate restore | ⚠ cry-wolf |
| 7 | the size pre-filter rejects on a match | ⚠ cry-wolf |
| 8 | a `copied` row is treated as a rename | defect |
| 9 | a `stat` failure fails open | defect |
| 10 | a hash-read failure fails open | defect |

⚠ **Mutation 1 SURVIVED first, and the MUTANT was the problem** - a two-step edit left the
original call in place, so the property was never removed (`ENGINEERING_STANDARD.md` §4's
sixty-sixth member, third time it has paid). ⚠ **Mutation 9 survived first and the mutant was
VALID** - a real gap: `chmod 000` does not stop `stat`, so the unreadable test reached the hash
and left the `stat` guard unproven. It has its own test now.

## Acceptance

The harness that found the defect, re-run against the fix - same 150 real photographs, same eight
`SIGKILL`s:

```
k1: moved= 15  intents= 16  unknown= 1  ORPHANS=0     <- the crash window, caught
k2..k8:                                  ORPHANS=0

TOTAL over 8 kills: moved=296  intents=297  ORPHANS=0      (was 2 of 8)
```

k1 is the design working: the intent was written, the process died before the rename completed,
and the row is `unknown` rather than absent - so undo could ask the disk and put every moved file
back.

---

## ⚠ CORRECTION, 2026-08-23 - two regressions this entry introduced

Found by the design pass for `(afw)`'s undo stage, and fixed before it. **A record is not edited
to stay correct**, so this is written beside what is above rather than into it.

`(agk)` added two skip reasons that **no second undo can ever resolve** - `NEVER_MOVED` and
`WAS_A_COPY` - and left two decisions keyed on the old assumption that every skip was a real
problem:

1. **`run_undo` never closed the run.** `if not skipped: finish_inplace_run(..., "undone")` meant a
   **fully reversed** run whose journal held one `copied` row stayed open forever,
   `latest_undoable_run()` kept returning it, and the app's `still_armed` stayed true. Measured at
   the commit: status `'completed'` instead of `'undone'`, armed `True`.
2. **The CLI spent the exit code on `WAS_A_COPY`**, printing *"could not be restored"* about a row
   that describes no rename. Measured: exit **1** on a clean undo.

🔑 **The discriminator was wrong, not just the list.** It is not *"is this a failure"* - it is
**can re-running undo do any more?** `run_undo`'s own comment already said so: a partial reversal
stays open so *"a second `undo` finishes the job"*. A run held open on something that can never
clear is a promise the product cannot keep, on the one path where a wrong state costs most.

`undo.SkipClass` / `classify` / `outstanding` now hold that in one place, exhaustively, and both
the close condition and the exit code read it rather than each deciding for itself.
