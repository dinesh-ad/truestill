# `(afw)` Stage 3 - a backup that stops still writes down what it did

*Design and closure record for `(afw)` Stage 3. The entry is [`afw.md`](afw.md); the index is [`BACKLOG.md`](../../BACKLOG.md).*

## The ruling this implements

**A run that stops still writes down what it did.** `IMPLEMENTATION_STANDARDS.md` §1's
run-record invariant is not conditional on the run finishing.

Before this, backup's summary was built at the `return`, so a raise part-way through left
**nothing**: the copies already made had `file_copies` rows, and no artefact anywhere said which
file stopped the run, why, or how many were never attempted.

⚠ **Out of scope, deliberately: the continue-vs-abort policy.** Whether one bad file should stop
the batch is `ENGINEERING_STANDARD.md` §4 Errors' *"one bad file never aborts a batch"* and is
Stage 4. **This stage lands green under today's fail-fast**, and the exception is re-raised
unchanged.

## What Stage 1 found, and what it changed about the design

`build_run_record` could not simply be called. Its signature took `list[Resolution]`, and
`Resolution` wraps a `Decision` - `category`, `captured_at`, `date_source`, `date_tag`,
`needs_review` - plus hashes and duplicate verdicts. **Backup has none of that**: it copies
catalog rows (`MissingCopy`) and never dates, categorises or deduplicates anything.

🔑 **Filling fourteen keys with `null` would have rebuilt the defect this file already fixed
once.** `run_record`'s own `unreadable` comment records why a `null` meaning two things is not
acceptable there; a `null` `category` meaning *"backup does not categorise"* and *"the category
is unknown"* alike is that shape fourteen times over, and it is `(aek)`/`(aft)`'s
one-value-two-states a third time.

**So the builder was split rather than called:**

| | |
|---|---|
| `run_record.build_run_record(header, *, files, intended_total, attempted, stopped)` | generic |
| `run_record.files_from_resolutions` | organize's adapter - the old body, lifted |
| `service/backup.py::_copy_entries` | backup's, with its own key set |

`RUN_RECORD_FORMAT` **bumped 1 -> 2**, and the `run` block gained `kind`. That is exactly the
condition the constant exists to announce: a reader that assumed every `files` entry carries
`category` was right for every record written before this and is wrong for a backup's.

⚠ **Organize's record is byte-identical, proved rather than asserted.** A record was captured
before the split and regenerated after: `files` identical, every shared `run` value identical,
one key added (`kind`), format 1 -> 2.

## The identity: uuid authoritative, label the human name

`RunHeader` carries `destination_uuid` **and** `destination_label`, uuid authoritative. A label
can be renamed in Settings; the marker uuid is what this product already treats as drive identity
everywhere else, and **a record naming a since-relabelled drive is unresolvable, which defeats the
record.**

⚠ **Absent rather than `null` where a caller has no drive identity to give.** Organize omits both
keys today. A `null` would mean *"this run wrote to no registered drive"* and *"this surface does
not record which"* alike - the same two-states-one-value shape the split exists to avoid. That
organize *could* supply them is a gap named here, not a null to be filled in later.

## Two hazards in the handler, both real

**1. The unbound loop variable.** `row` is bound inside the loop, so a raise from
`_stop_if_ground_moved` on the **first** iteration - or from `enumerate` itself - leaves it
unbound, and naming it in the handler would raise `NameError` **inside the handler**, replacing
the original exception with one about the record. That is this stage's own defect one level up.
`attempting` is bound before the `try` and the handler tolerates `None`.

**2. The record's own failure.** `write_run_record` returns a string rather than raising on
`OSError`, but it is called from inside an `except` block: a `TypeError` from `json.dumps` on an
unserialisable value would **replace the exception being handled**, turning a read-only disk into
a `TypeError` about paperwork. `_recorder` catches `Exception`. `BaseException` is deliberately
not caught, per `(aet)`: a wrapper that ate a `KeyboardInterrupt` would make Ctrl-C stop working
on the operation people most want to stop.

## Cancel writes a record; a `BaseException` does not

**Backup cancels by flag, not by exception** - `cancel.is_set()` then `break`
(`service/backup.py`). So a cancelled backup falls out of the loop and reaches the normal path,
and **does** write a record. A `BaseException` escaping would not, and that is stated rather than
widened: whether it should is not this stage's call.

## Complexity, declared rather than suppressed

`IMPLEMENTATION_STANDARDS.md`'s complexity rule was answered three times by **naming a group**,
never by a `noqa`:

- `_recorder` as a closure, because six of eight arguments never vary once the run starts.
- `_CopyRun`, because the copy loop needed nine values that travel together.
- `RunHeader`, because five of `build_run_record`'s nine arguments are one idea.

⚠ **Worth knowing before anyone tries it again**: extracting the loop into a **nested** function
did not help, because ruff counts nested statements against the enclosing function. It had to go
to module level, which is what forced `_CopyRun` - and the result is better than the version that
would have passed.

## Guards

`test_a_backup_that_stops_says_what_it_did.py`, four tests. **The record is asserted, never
merely that the run raised** - the raise already happened before this change, so a test stopping
at `pytest.raises` passes against the defect.

Four mutations, each with a visible unmutated control:

| mutation | caught by |
|---|---|
| the record write removed from the failing path | 3 failed |
| every entry reads `uploaded`, so the failure vanishes | 2 failed |
| the recorder narrowed to `except OSError` | 1 failed |
| the failed entry names the file and **not why** - the `(afa)` shape | 1 failed |

⚠ **The failure is injected at `shutil.copy2` inside `safe_copy`, not at backup's own helper**, so
it arrives through `staged_copy`'s single `except OSError` - the site Stage 1 found cannot tell a
source read from a destination write. A test patching `_copy_verified_or_raise` would have
asserted that the test can raise.

## What the existing guards caught, which is worth more than the diff

- `test_every_job_declares_whether_it_mutates`-style table in
  `test_the_app_records_what_a_run_did.py` fired: *"service/backup.py writes a run record, and
  this table says the opposite"*. The recorded decision was updated, which is the guard working.
- `test_vanished_mountpoint.py`'s structural check fired because `device.check(target)` became
  `run.device.check(run.target)`. The needle moved; the property did not.

## Still open after this

- ✅ **Stage 4 shipped 2026-08-23**: one bad file no longer aborts a backup, `verified` is derived
  from the failure count, and the counterfactual clause in `app.js`'s banner is deleted.
- ⚠ **Everything else moved to `(agi)`** rather than being restated here: `ENOSPC` treated as a
  per-file fact on **both** surfaces, no third job state in `jobs.py`, the record's location never
  told (`(afu)`'s lesson), and `failed` present in the payload but unrendered.
- **Organize could supply `destination_uuid`/`destination_label` and does not.**
