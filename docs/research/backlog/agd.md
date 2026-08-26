# (agd) A DEGRADED WATCHER SAYS NOTHING, AND THERE IS NO CHANNEL FOR IT TO SAY ANYTHING IN.

*Body of backlog entry `(agd)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agd)** Recorded 2026-08-23, split out of `(aft)` **while building it**, deliberately not
  folded in.

  ## The state `(aft)` left

  `run_health.free_bytes` now returns `None` when the probe cannot be measured, and
  `_check_space` **fails open** - correct, and the module's own recorded posture
  (`run_health.py:17-22`: *"periodic and advisory, so it fails open until proven"*).

  **But it fails open silently.** A user whose catalog folder went unreadable mid-run gets a run
  that completes with the disk-space guard switched off and no sign that it was. Nothing counts
  it, nothing names it.

  🔑 **`(aft)` made the code honour a decision already recorded. It did not make the silence
  right.** That is this entry.

  ## THE TWO SIDES, BOTH STATED, BECAUSE EITHER MAY WIN

  ### For saying it - `IMPLEMENTATION_STANDARDS.md:1354`, §9's never-silent clause

  > **Never-silent, restated for screens.** A skipped, refused, **degraded** or unverifiable
  > outcome is *counted and named*, never folded into a success total or dropped.

  A watcher that was asked to protect a run and could not is degraded by any reading of that
  sentence. It is binding contract, not canon.

  ### Against a new mechanism - `backup.py:247-253`, `_stop_if_ground_moved`'s own docstring

  > *"Stop the backup if the ground under it has moved. **Silent when all is well.** … **Raised,
  > not returned, because this loop already stops this way** … A second mechanism for the same
  > class of event would be a second thing to keep in step."*

  That argument was made about the stop path and it applies with equal force to a notice path.
  **It may win.** A notice channel nobody reads is worse than an honest gap, and this repo has
  `(afn)`'s cry-wolf finding on exactly that.

  ## WHY IT IS ONE ENTRY AND NOT A THIRD OF ONE

  Surfacing on **organize alone** was proposed during `(aft)` and refused. `HealthVerdict`
  (`run_health.py:78-84`) is binary - `ok` plus a sentence read only when `ok` is false - and the
  three watchers consume it three different ways:

  | watcher | today | where a notice would have to go |
  |---|---|---|
  | `organizer.py:1900` | `ActionResult(..., FAILED, None, detail)` | a per-file result carrying a per-run fact |
  | `migrate.py:681` | `stopped = verdict.detail` | a new `MigrationOutcome` field |
  | `backup.py:259` | `raise ValueError(verdict.detail)` | **no non-fatal path exists at all** |

  Building the channel for one and leaving two is §4's **fifty-sixth member scheduled rather than
  inherited** - two sites agreeing is what makes the third invisible, and that member is the exact
  mechanism that produced `(aft)`: `(aek)` reached two surfaces and not the third. Repeating it
  knowingly is worse than inheriting it.

  ## THE WORDING, ALREADY RULED

  Settled during `(aft)` so it is not re-derived. A label/remedy pair in `models.py`, in the
  register of `UNCOMPARED_LABEL`/`UNCOMPARED_REMEDY` (`models.py:301-302`) - the existing
  degraded-but-fine notice, whose remedy deliberately states what still worked.

  ```
  label  : this computer's free space could not be checked during the run
  remedy : the run was not stopped by it; check that the folder holding the
           catalog this run used is reachable before the next long run
  ```

  Three constraints are load-bearing and each cost a draft:

  - ⚠ **No free-space figure.** §9 `:1281`/`:1305` - a thing that could not be read is **named,
    never counted**, because the number is exactly what was not obtained. Stating one would invent
    it, which is the folder-versus-file rule applied to a measurement.
  - ⚠ **No reason word.** An earlier draft reused `UnreadableReason` to say *"(permission
    denied)"*. Refused: a reason claims a category **this fix deliberately refuses to determine** -
    every `OSError` on this axis is indefinite, which is the whole design (`(aft)`).
  - ⚠ **Not *"Truestill's catalog folder"*, and not *"nothing was left half-written"*.** The probe
    is `catalog_path.parent` and `--db` is unconstrained (`cli.py:365-368`), so on
    `--db /media/usb/x.sqlite` the unreachable folder is the **user's**, not ours. And the
    half-written guarantee is `safe_copy`'s, not this one's - a reader takes it as a claim about
    their files.

  ## WHERE IT WOULD LAND, IF IT IS BUILT

  - `run_record.py` `build_run_record`'s `"run"` block - today `stopped` is the only slot and it
    is stop-only. `RUN_RECORD_FORMAT = 1` (`run_record.py:30`) is documented as *"bumped when a
    reader would have to change"*.
  - `cli._print_run_reports` (`cli.py:2628-2658`), beside `_print_uncompared` /
    `_print_suppressed_noise`.
  - The app payload, the way `uncompared` was added - and §9 `:1290` requires the group be
    **absent, not zero**, when there is nothing to say.

  ## RELATED

  `(aft)` (which produced this and states what it does not do), `(afw)` (the other mutating runs
  report nothing - the same missing-channel question from the record side), `(afn)` (cry-wolf).
