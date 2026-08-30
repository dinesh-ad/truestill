# (air) A `--move` THAT COULD NOT REMOVE THE SOURCE EXITS 0.

*Body of backlog entry `(air)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P145), from `(aim)`'s route census. ⚠ **FILED RATHER THAN DECIDED** - the
counter-argument is strong enough that ruling it inside a summary-wording commit would have been
deciding it by momentum.

## THE FACT

`ActionStatus.MOVE_KEPT` means: the copy is in the library, it **re-verified at the destination**,
and the source was then deliberately kept - `organizer._move_source` produces it on three
branches (checksum unreadable, re-verify mismatch, `unlink` failed) and *"never deletes on doubt"*,
which is right and is not in question.

`cli._print_execution` selects failures as `r.status is ActionStatus.FAILED` **alone**, so the run
returns **0**. The status is not silent - it prints as `kept, move not completed` and gets its own
capped `MOVE KEPT` list - but a script sees success.

## THE ARGUMENT FOR 1

- `1` is already this CLI's *"finished, but something is wrong with the library"*, used by
  `organize`, `verify` and `reclaim`.
- The precedent is exact and already written down: a preview that found an unreadable file exits
  `1` **because** *"predicting with `0` a run that will exit `1` makes `organize && next_step`
  chain past a library Truestill could not fully account for"* (`IMPLEMENTATION_STANDARDS.md`).
  A `--move` that left every source in place is the same chain hazard - the next step may be the
  user deleting the source folder.
- The user asked for a move. They did not get one.

## ⚠ THE ARGUMENT AGAINST, WHICH IS WHY THIS IS A QUESTION

**Nothing was lost and the library is correct.** The photograph is organized, recorded and
verified; only the tidy-up did not happen. A non-zero exit for a run whose every copy succeeded is
a cry-wolf of the kind `(aie)` and `(ain)` were just fixed *to stop* - both deliberately exit `0`
with a warning, and their tests assert it, because the file is safe. `MOVE_KEPT` may be that same
shape, one step further along.

**The distinguishing question, and whoever rules should answer it rather than reason from
symmetry**: does the user's next action depend on it? For a metadata warning, no. For a kept
source, arguably yes - they are about to look at a folder they expected to be empty.

## SCOPE - do not fold this in

⚠ **It changes an exit code, which is a contract a script reads**, and the repo allocates those on
a stated rule: *"one per failure family that a caller would act on differently."* Moving
`MOVE_KEPT` from `0` to `1` is not a new family - it is a reclassification into an existing one -
so it needs its own commit, its own test, and a line in the CLI's exit-code documentation.

⚠ **The app half is worse and belongs to `(aiq)`**: `MOVE_KEPT` is in neither
`_ORGANIZED_STATUSES` nor `failed`, so it falls out of both tallies and its label reaches no
pixel. **Fixing the exit code without that leaves a file that is invisible on one surface and
newly loud on the other.**

## RELATED

`(aim)` (the census that found it), `(aiq)` (the app half), `(aie)` / `(ain)` (the exit-0
precedent that cuts the other way).
