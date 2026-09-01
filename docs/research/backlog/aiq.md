# (aiq) A RUN THAT FAILS MOST OF ITS FILES REPORTS "done", AND NAMES NONE OF THEM

> ⚠ **REWRITTEN 2026-09-01 (P170) AGAINST MEASUREMENT.** The title above replaces
> *"THE APP SHOWS A NUMBER FOR FAILURES AND NEVER A FILE, AND SHOWS NOTHING AT ALL ON A STOP."*
> **The original body is kept entire beneath, unedited**, because it was an honest reading of the
> source and the correction is only legible next to it.
>
> **This entry was filed from a code read that the P145 brief required.** Soak twelve's app half
> ran it for the first time on 2026-09-01
> ([`soak-twelve-record.md`](../../soak-twelve-record.md) 12b). Three things changed:
>
> 1. 🔑 **THE REAL DEFECT WAS NOT IN THIS ENTRY.** Measured: `organize` onto a drive that vanished
>    failed **1,130 of 1,324 files** and the terminal event was
>    `{"type": "done", "status": "done", …}`. **A run that lost 85% of its work reports success.**
>    Not a missing filename - a missing *failure state*.
> 2. ⚠ **GAP 2's MECHANISM WAS NEVER REACHED.** It rests on `RunStoppedError` escaping and
>    `app.js` forcing `summary: {}`. A vanished destination does not raise: it is classified
>    `GONE`, `persists_for_the_run` returns `False` for it, and the loop **failed 1,130 files one
>    at a time and returned normally**. The gap is real for the conditions that *do* raise; it is
>    not what a user meets when a drive is pulled.
> 3. ⚠ **THE FRAMING INVERTED ON `backup`.** This entry says the app is worse than the CLI on
>    detail. On a vanished drive the **app printed the sentence and the CLI printed an eight-frame
>    traceback** - that is `(ajg)`, found *because* the app degraded gracefully. The app is worse
>    on organize's detail and **better** on backup's failure. "The app is worse" is not a property
>    of the app; it is a property of each path.
>
> **Gap 1 and gap 3 are unchanged and confirmed**: the failure list is still a scalar
> (`service/organize.py:1562`), rendered as one banner (`app.js:1053`) reading
> *"1,130 files could not be organized."*, and `metadata_ok` still has zero occurrences in
> `truestill-app`.

## ✅ THE STATUS ROOT SHIPPED 2026-09-01 (P171). THE COUNT ROOT DID NOT

**One of the two roots below is closed.** `jobs._terminal_status` derives the terminal status from
what the target **returned**, and each service declares its own verdict in `finished_clean` -
because `jobs.py` holds thirteen shapes in one registry and cannot know that "unclean" is `failed`
for organize, `missing`/`mismatch`/`unreadable` for verify, `stopped`/`refused` for migrate and
undo, and an unfinished `renamed` for a rename. **A third status**, `completed_with_errors`, and
the two completion cards say *"Finished with errors"* through one `outcomeWord` helper.

🔑 **THE LINE IS THE CLI's, NOT A NEW ONE.** `_cmd_verify` already returns
`1 if (missing or mismatch or unreadable)` - a **finding**, not work it could not do - and `(air)`
quotes exit 1 as *"finished, but something is wrong with the library"*. So the app now says what
the CLI has always said, and `verify` is deliberately in scope for that reason.

⚠ **THE COUNT ROOT IS STILL OPEN and this entry stays open for it.** `_completion` still ships a
scalar `failed` and no per-file list; the screen still reads *"1,130 files could not be
organized."* with no names. That is gap 1 below, it needs `(afd)`'s cap and a renderer, and
folding a screen redesign into a status fix is what `CLAUDE.md`'s browser-lane rule exists to
prevent.

### ⚠ It is additive on the wire and a NARROWING of `done`, and both halves must be said

**Additive**: a new member. Verified in `app.js` - `ok` comes from `type`, never from `status`
(`const failed = d.type === "error"`), and the dispatch is
`!ok -> onError`, `status === "cancelled" -> onCancelled`, **else -> onSuccess**. An unknown status
therefore renders exactly as it does today. Nothing crashes and nothing is hidden.

**Narrowing**: a run that previously carried `status: "done"` **with failures** now carries
`completed_with_errors`. A consumer keying on `status === "done"` to mean *finished* would miss
those runs. **Checked: no consumer anywhere in this tree does that** - `grep` for `=== "done"`
across `app.js` and `frontend/src` returns nothing, and `"cancelled"` is the only status value
compared against.

🔑 **So it ships in 0.2.0, not a patch on 0.1.0.** v0.1.0 is published and the no-users regime
expired at the tag; narrowing the meaning of a value already on the wire is a behaviour change a
consumer can observe, whatever the enum does.

## ⚠ TWO ROOTS, NOT ONE, AND THEY ARE IN DIFFERENT LAYERS

**Established by reading, 2026-09-01.** The count and the status do not share a cause, so neither
fix reaches the other:

| | where | what is wrong |
|---|---|---|
| **the count** | `service/organize._completion` | the payload carries a **scalar** `failed` and no per-file list. A *payload* defect |
| **the status** | `jobs.py:392` - `job.status = "cancelled" if job.cancel.is_set() else "done"` | status is derived from **whether the target returned**, never from what it returned. A *job-layer* defect, and **one line** |

🔑 **Both are `(aim)`'s family** - *a report derived from something other than the outcome it
claims to describe.* `(aim)` was the wrong **tense** (a plan-derived count in outcome tense); this
is the wrong **source** (control flow instead of the returned outcome). `jobs.py` cannot know what
"failed" means for every job shape, so the fix is not a `failed > 0` test inside it: the target
must be able to say *"I completed and I did not succeed"*, and only the service knows that.

⚠ **This is NOT ruled here and must not be hot-patched.** `job.status` is read by
`_retire_finished` and shipped in every terminal event; changing what "done" means is a payload
contract change on a surface `PROJECT_STATUS.md` §1b has not declared stable yet. **What is
established is that there are two roots, in two files, at two layers.**


*Body of entry `(aiq)`, **CLOSED 2026-09-01**. The closure is in [`SHIPPED.md`](../../SHIPPED.md);
the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-08-30 (P145), from the surface audit `(aim)` needed and did not have. **Read from
source, not from the browser lane** - which the P145 brief forbade - so the rendering claims are
traced through `main.tsx` → `app.js`, not observed.

## ⚠ FIRST, THE CORRECTION THIS ENTRY EXISTS TO CARRY

`(aim)` recorded *"the app already solved it"* and cited `service/organize._completion`. **On the
TENSE that is right**: `_completion` is built only from `results` and its own docstring says
*"every number here is counted from the results - nothing is estimated."* The app renders that as
its headline. So a reader of `(aim)` would conclude the app is the model to copy. **On two of the
three axes below it is the surface to fix.**

## THE THREE GAPS

### 1. No per-file failure list exists at all

`CompletionBase` carries a **scalar**: `"failed": sum(1 for r in results if r.status is
ActionStatus.FAILED)`. `app.js` renders one banner - *"3 files could not be organized."* No names,
no reasons, no cap notice.

The CLI names every one through `cli._print_capped`, capped at `_STATUS_PREVIEW` with a tail
saying how many more and how many distinct reasons - which is `(afd)`, built because 2,096
identical lines is its own defect. **So the app is not behind on volume control; it never had the
list.**

⚠ **This is the inverse of `(aim)`'s framing and that is why it is written down.** Left as
filed, the next person improving the CLI would copy the app.

**It is also the surface's own stated standard, unapplied.** `service/organize._unreadable_files`
and `_duplicate_report` both ship `{total, shown}` and both **are** rendered. Failures are the one
never-silent list that never got one.

### 2. A hard stop shows no counts whatever

`RunStoppedError` escapes `organize_run` after the record is written; `jobs.py` takes its
`except Exception` branch and emits a terminal `{"type": "error"}` with **no `summary`**;
`app.js` then forces `summary: {}` on a failed job and renders a single banner.

🔑 **So the user is told the reason and nothing about what landed.** This is `(aim)`'s worst CLI
route in a worse form - and after P145 the CLI prints `1 failed / 2 not attempted` there while the
app still prints neither. The counts exist: they are in the run record on disk, written three
lines before the re-raise.

⚠ **A cancel is NOT this case and must not be folded in** - it returns normally, carries the full
summary, and already renders *"Stopped - N files organized before you stopped it."* That half is
correct and is the model for this one.

### 3. `metadata_ok` does not exist in `truestill-app`

Zero occurrences in the package. `(aie)` and `(ain)` shipped *"copied to X and is safe, but this
drive does not let Truestill set timestamps or permissions"*, the CLI prints it under
`METADATA NOT SET`, and **the app cannot show it** - the field is not on the payload. A degradation
that is silent on one surface is the shape `(aek)` and `(aep)` each closed once.

## ⚠ AND `MOVE_KEPT` FALLS OUT OF BOTH TALLIES

`_ORGANIZED_STATUSES` is `{UPLOADED, RENAMED, MOVED, MOVED_IN_PLACE}` and `failed` counts
`ActionStatus.FAILED` exactly, so a `MOVE_KEPT` file is in **neither**. Its only trace is the
`outcomes` dict, which `app.js` reads **once, as a truthiness check**, and never renders. The
CLI's half of this question is `(air)`.

## WHAT PINS IT AFTERWARDS - and the hole is already documented

`test_job_summaries_are_read_where_they_are_delivered.py` records the identical defect on
**backup's** summary (*"a run that could not copy a file says so nowhere on this screen"*) and
then **exempts `/api/organize/run` by name in its own comment**. So the guard for this class
exists, was written by someone who saw this payload, and was scoped around it.

`test_server.py`'s `test_organize_run_summary_matches_files_on_disk` asserts `set(summary) >= {…}`
- a **superset** check, which `CompletionBase`'s own docstring notes lets key additions pass
silently. **No test anywhere asserts a non-zero `failed`, any `outcomes` content, or `MOVE_KEPT`
reaching a surface.**

## WHY IT WAS NOT BUILT IN P145

Three app changes of one class riding inside a `cli.py` commit would make a screen change
dependent on a core one, and `CLAUDE.md`'s browser-lane rule exists for exactly the change that
*"could make a screen STOP SHOWING SOMETHING"* - which adding a payload field and a renderer is.
This wants its own commit and the browser lane on.

## RELATED

`(aim)` (the CLI half, shipped), `(air)` (`MOVE_KEPT`'s exit code), `(aer)` (the last time a
payload field a renderer read went missing), `(afd)` (the cap the list would need), `(aie)` /
`(ain)` (the warning gap 3 hides).
