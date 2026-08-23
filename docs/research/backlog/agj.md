# (agj) AN ABORTED ORGANIZE WROTE NO RECORD - AND THE CLI WROTE A FALSE ONE.

*Body of entry `(agj)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-23 - both surfaces, one commit
>
> `organizer.execute` hands its partial results out on the exception (`RunStoppedError`), and both
> callers write the record from them. `IMPLEMENTATION_STANDARDS.md` §1 makes the record automatic
> *"because the user who most needs it is the one who did not know to ask"* - and that user is
> exactly this one: a run stopped by a full drive is when the paperwork is worth most.

## ⚠ A REGRESSION FROM ONE COMMIT AGO, NOT A LONG-STANDING GAP

This is stated first because it changes what the defect *is*. **`(agi)` created it**, and the
proof is a census of every stop in `organizer.py`:

| line | stop | how it leaves |
|---|---|---|
| `:2014` | cancel | `break` |
| `:2048` | health watcher | `break` |
| `:2077` | `CatalogWriteError` | `break` |
| `:1912` | **`(agi)`'s persistence predicate** | **`raise`** |

Every stop before `(agi)` returned normally with partial results, so both callers recorded on
their ordinary path and no one had to think about it. `(agi)`'s raise leaves that path, and
`results` is local to `execute`'s frame - so it died with the frame.

## The two surfaces failed differently, and the CLI's half is the worse one

* **the app** (`service/organize.py:1223`) wrote **nothing**: `_write_the_record` sits below the
  `execute` call with nothing between them.
* **the CLI** (`cli.py:2882`) wrote a record saying **every file was never attempted**. Its
  handler was written for the pre-flight refusal, where `results` really is empty and
  `never_attempted = len(resolutions)` really is true. Mid-run both are false.

⚠ **A false custody record is worse than a missing one.** It is `(afa)`'s shape with the reader
actively misled rather than merely uninformed - and in a product whose promise is verified
custody, the paperwork saying *"nothing was attempted"* about files that are on the drive is the
one failure mode a record exists to prevent.

## Why an exception that carries state, and not a results sink

Both were considered; the state has to cross a package boundary either way.

**A sink parameter is opt-in, and its omission is invisible.** A caller that forgets it still gets
the return value on the happy path - so nothing is wrong until the first abort, which is this
defect reintroduced silently. A caller that ignores `RunStoppedError` gets an unhandled exception.
Neither is enforced by the type checker; **only one fails where somebody will see it.**

It also avoids a fifteenth parameter on a function that already has fourteen.

**It is not a new error.** `str()` is the cause's own sentence, so the drive-worded message a user
reads is unchanged, and the original is the direct `__cause__` - which keeps `errno` reachable
through the chain `drive_unwritable.persists_for_the_run` already walks.

## ⚠ THE WRAPPER BROKE A CLASSIFIER, AND THAT IS `(agi)`'s OWN LESSON ARRIVING AGAIN

`jobs.py` turns a worker's failure into a terminal event, and asks `is_catalog_busy(exc)` - an
`isinstance` check over `sqlite3.Error` that **does not walk the cause chain**. Behind a wrapper it
answers *"not busy"* about a catalog that is, and the user gets SQLite's *"database is locked"*
instead of the sentence written for exactly that situation.

**It is reachable, not theoretical**: `catalog.record_inplace_move` inside `_journal_or_delete_source`
is a bare catalog write in `execute`'s loop, unguarded by `_record_or_stop`, so a held catalog
raises `sqlite3.Error` straight out of the loop.

`jobs._underlying` looks through `RunStoppedError` and **nothing else** - one layer, because a
wrapper is usually the considered answer and its own class is what the surface should report.
`(agi)` learned the same thing from the other direction: *a classifier that reads only the
outermost exception is inert the moment anyone wraps one.*

## What was found alongside and NOT fixed

* 🔑 **`record_inplace_move` is an unguarded catalog write in the middle of the write path**, where
  every other catalog write goes through `_record_or_stop`. On an in-place move the rename has
  already happened, so a failed journal write means the file has moved with **no undo row** -
  which is the one thing that journal exists to provide. Reported, not fixed: it is a different
  defect with a different remedy. **Its own letter.**
* **A stopped run leaked a `TemporaryDirectory`.** `baker.close()` sat after the loop on the
  return path only, so `(agi)`'s raise skipped it - and a Takeout ingest stopped by a full drive
  left its staging directory on the drive that had just run out of room. Same exit path, so fixed
  here: the close is in a `finally`.

## What was checked and found not to be a problem

* **No partial can wear an organized name.** `copy_leaving_nothing` stages to a sibling and
  renames only on success (`destinations/local.py:165-167`). A failed copy leaves at most a
  `STAGING_SUFFIX` file, whose bytes the detail string already names and which `rescan` sweeps.
  Not its own letter.
* **No screen can stop showing something.** The only UI consumer of an error's class is
  `FRIENDLY_ERRORS` in `app.js`, whose single key is `NotABackupDriveError` - raised by
  `service/migrate.py` and `service/backup.py`, never from `organizer.execute`. The message text
  is unchanged because `RunStoppedError` reports its cause's sentence. The browser lane is
  genuinely not implicated, by CLAUDE.md's own test.

## ⚠ A CORRECTION TO `(agi)`'s ENTRY, PLACED HERE RATHER THAN IN IT

`agi.md` closes *"organize re-raises the original exception object"*. That was true on
2026-08-23 and is no longer: organize now raises `RunStoppedError`, whose direct cause is that
object. Both properties `(agi)` recorded - the user-facing sentence and the reachable `errno` -
hold unchanged, and its own test asserts them through the deeper chain. **A record is not edited
to stay correct**, so the correction lives here, dated.

## Complexity, declared rather than suppressed

Wrapping the loop in place pushed `execute` over its branch *and* statement ceilings, and the CLI
handler pushed `_run_pipeline` over its branch ceiling. Both were answered by naming a group:

* `_organize_each` - the loop, lifted out so `execute` can wrap it. It **appends to the caller's
  list rather than returning one**, which is what makes the results reachable after a raise.
* `_WriteRun` - the ten invariants one write needs, as a context object. Backup's `_CopyRun` for
  the same reason and by the same argument: they travel together, and a caller must not be able
  to pass them in the wrong order.
* `_stopped_run_exit` - the CLI's two stops, side by side, where their difference is visible
  rather than twenty lines apart.

⚠ A **nested** function would not have helped: ruff counts nested statements against the enclosing
one, which `(afw)` already recorded and which is worth not rediscovering.

## Proof

Nine mutations, all caught, against an unmutated control run of 18 tests:

| # | mutation | direction |
|---|---|---|
| 1 | `execute` stops wrapping | defect |
| 2 | the CLI records an empty results list | defect |
| 3 | the app stops recording on abort | defect |
| 4 | `baker.close()` leaves the `finally` | defect |
| 5 | `jobs._underlying` stops unwrapping | defect |
| 6 | `_underlying` unwraps **any** exception's cause | ⚠ cry-wolf |
| 7 | the wrapper widens to `BaseException` | ⚠ cry-wolf |
| 8 | the CLI hardcodes `never_attempted` again | ⚠ cry-wolf |
| 9 | `RunStoppedError` reports its own name, not the cause's sentence | ⚠ cry-wolf |

⚠ **Mutation 9's first anchor was ambiguous** (`super().__init__(str(cause))` appears twice in
`organizer.py`) and `mutate_once.py` refused with exit 2 rather than mutating the wrong class.
That refusal is the tool doing the job it was built for - a `sed -i` would have reported success.
