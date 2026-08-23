# (agg) THE ARCHIVE INGEST ROUTE WRITES TO THE DESTINATION WHILE DECLARING `mutating=False`, SO THE DRIVE LOCK NEVER ENGAGES.

*Body of backlog entry `(agg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agg)** Recorded 2026-08-23, found while inventorying CLI subcommands against app routes.

  ## The chain, four links, each cited

  1. **The route writes.** `/api/ingest/archives/run` (`server.py:832`) runs
     `service/takeout.py:201` -> `extract_archive_set`, whose own docstring says it extracts
     *"one merged staging tree under `destination`"* (`archive_extract.py:303,312`). Real bytes,
     on the user's drive.
  2. **It declares itself non-mutating.** `server.py:405-406`:
     `operation="import preview", mutating=False`.
  3. **`mutating` is exactly what gates the cross-process lock.** `jobs.py:253`:
     `cross_process = _hold_across_processes(held) if mutating else []`.
  4. **The staging path is derived from the input, not the process.**
     `archive_extract.py:211-213`: `destination / STAGING_DIRNAME / archive_set.stem`.

  ## 🔑 THE SENTENCE `(aaw)` WROTE, ON A PATH IT DID NOT REACH

  `7564ed6` is titled *"a staging path is private to the process that made it"*. That was
  `safe_copy`'s `.partial`, and it is the fix for exactly this shape: **two writers, one path
  computed from the work rather than from the writer.** This path has the same shape and was not
  covered.

  `(aaw)` measured what that costs when it bites: two concurrent applies lost **99** and **45**
  organized copies, proven by content. That was a different path and a different command; what
  carries over is the mechanism, not the number.

  ## ⚠ BOUNDED HONESTLY - WHAT IS TRACED AND WHAT IS NOT

  - ✅ **The mechanism is traced**, all four links above read rather than inferred.
  - ❌ **No collision was reproduced.** Nothing here claims one has happened or would.
  - **The in-process claim is unconditional** (`jobs.py:240-246`), taken for every job whatever
    `mutating` says - so **two tabs in one app are already refused**. The exposure is
    **app-versus-CLI**, or app-versus-second-app: the CLI takes the lock under `--apply`
    (`cli.py:4293`, `_run_holding_the_drive`) and this route does not check it.
  - **Severity is unassessed.** A staging tree is not the user's originals, and what a collision
    there costs - a corrupt merge, a wrong sidecar match, or nothing - has not been worked out.
    That is the first question, not the fix.

  ## ⚠ AND IT IS `(afq)`'s INVERSE, WHICH IS WHY BOTH ARE WORTH READING TOGETHER

  `(afq)`: *a preview occupies the drive in the app, and nothing says why* - a run that takes the
  lock and should not obviously need it. This: **a run that writes and does not take it.** The
  same declaration, wrong in opposite directions, which suggests the declaration is being made per
  route by judgement rather than derived from what the route does.

  `IMPLEMENTATION_STANDARDS.md` §1 states the rule as *"Mutating operations only - a preview
  writes nothing, and a stale preview is not data loss."* **Here the preview writes.** So either
  the declaration is wrong or the rule's phrasing is, and deciding which is the work.

  ## NOT DECIDED

  - Whether the answer is `mutating=True` (correct by the rule, but it makes an import *preview*
    hold the drive - which is the complaint `(afq)` already carries), a per-process staging stem
    (the `7564ed6` remedy, cheaper and local), or both.
  - Whether `operation="import preview"` is honest wording for a step that unpacks archives to
    disk. A user reading *"import preview"* in a busy-drive message would not expect it to have
    written anything.

  ## RELATED

  `(aaw)` (the lock, and the sentence this path did not get), `(afq)` (the inverse declaration),
  `(afw)` (which of the app's runs write a record - the same per-route-judgement shape).
