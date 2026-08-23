# (agg) `mutating` IS DECLARED PER ROUTE BY JUDGEMENT, AND ITS GUARD IS DERIVED FROM THE DISPLAY STRING - SO IT NOW ENFORCES A ROUTE THAT WRITES WITHOUT THE LOCK.

*Body of backlog entry `(agg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agg)** Recorded 2026-08-23 while inventorying CLI subcommands against app routes, and
  **retitled the same day**: the instance below was the finding, and the cause turned out to be
  larger than it.

  ## THE CAUSE

  `mutating` decides whether `(aaw)`'s cross-process drive lock engages (`jobs.py:253`:
  `cross_process = _hold_across_processes(held) if mutating else []`). It is **declared at each
  route by hand**. Nothing derives it from what the route does, and nothing checks it against
  that.

  **`(agg)` and `(afq)` are two instances pointing opposite ways**, which is what makes it a cause
  rather than two bugs:

  | | |
  |---|---|
  | `(afq)` | a **preview occupies** the drive, and nothing says why |
  | `(agg)` | a route that **writes does not** hold it |

  One declaration, wrong in both directions in the same codebase.

  ## THE INSTANCE

  Four links, each read:

  1. `/api/ingest/archives/run` (`server.py:832`) reaches `service/takeout.py:201` ->
     `extract_archive_set`, which writes *"one merged staging tree under `destination`"*
     (`archive_extract.py:303,312`). Real bytes, on the user's drive.
  2. It is registered `operation="import preview", mutating=False` (`server.py:405-406`).
  3. `mutating` gates the cross-process lock (`jobs.py:253`).
  4. The staging path is `destination / STAGING_DIRNAME / archive_set.stem`
     (`archive_extract.py:211-213`) - **derived from the input, not the process.**

  🔑 That last line is the sentence `7564ed6` wrote for `(aaw)` - *"a staging path is private to
  the process that made it"* - **on a path it did not reach.**

  ## 🔑 AND THE GUARD ENFORCES IT, WHICH IS THE PART THAT MAKES THIS URGENT TO DECIDE

  `test_every_job_declares_whether_it_mutates.py` opens by ruling out the obvious shortcut, in its
  own words:

  > ⚠ **Why not derive it from `operation`.** `"organize"` and `"organize preview"` differ by one
  > word, and a control derived from a display string is one rename away from a lock that stops
  > firing.

  **One screen below, the assertion is derived from `operation`:**

  ```
  for operation, mutating in _declared():
      if "preview" in operation:
          assert not mutating, ...
  ```

  `"import preview"` contains `"preview"`. **So the test requires `mutating=False` for a route
  that writes** - and the obvious fix for the instance above makes an existing test go red.

  ⚠ **Its own failure message is the correct diagnosis, arrived at by accident**: *"a preview that
  writes is either mislabelled or is not a preview."* This route is **both**. The test cannot
  detect that, because it compares the label with the declaration and neither with the behaviour.

  Measured across all **15** declarations: 7 carry `"preview"` and are therefore pinned to
  `mutating=False` by the label alone.

  ## ⚠ COULD IT BE DERIVED AT ALL? - the question this entry exists to answer

  **From the route: no, and it should not try.** The docstring above is right, and the current
  guard is the demonstration of why.

  **From the call graph: partially, and the bounded version catches this.** A job target that
  reaches a known write helper - `extract_archive_set`, `safe_copy.*`, `LocalDestination.upload`,
  `_apply_move` - is writing, whatever it is called. Full cross-package reachability is not worth
  attempting; **one hop from the service function is**, and `takeout.py:201` calls
  `extract_archive_set` **directly**, so a one-hop check would have caught this instance on the
  commit that introduced it. That is the guard the cause deserves: *assert against behaviour, not
  against the label.*

  **From the write itself: yes, completely - and that is the honest answer to "derived".** If the
  **write** took the lock rather than the **route** declaring it, the property would be structural
  and no declaration could be wrong. The costs are real and should not be waved past: acquisition
  moves into a hot path, it needs re-entrancy, and the refuse-or-wait decision arrives **mid-run**
  rather than at the start - which is a worse moment to tell a user their drive is busy, and
  `(afp)` ruled on exactly that trade-off in the other direction.

  **If it stays declared, the declaration needs a REASON rather than a bool.** `mutating=False`
  currently means both *"this writes nothing"* and *"this writes, but not where it matters"* -
  which is the `0`-means-two-things shape `(aek)` and `(aft)` each removed from a different module.
  A reason field makes the second case sayable, reviewable, and greppable.

  ## ⚠ BOUNDED - what is traced and what is not

  - ✅ **The mechanism is traced**, every link read rather than inferred.
  - ❌ **No collision was reproduced**, and none is claimed.
  - **The in-process claim is unconditional** (`jobs.py:240-246`), so **two tabs in one app are
    already refused**. The exposure is **app-versus-CLI**, where the CLI locks under `--apply`
    (`cli.py:4293`) and this route does not check.
  - **Severity is unassessed.** A staging tree is not the user's originals, and what a collision
    there costs - a corrupt merge, a wrong sidecar match, or nothing - has not been worked out.
    **That is the first question, not the fix.**

  ## NOT DECIDED

  - Whether the instance is fixed by `mutating=True` (correct by the rule, and it makes an import
    *preview* hold the drive - `(afq)`'s complaint), a per-process staging stem (the `7564ed6`
    remedy, cheaper and local), or both.
  - Whether the guard moves to behaviour, or the declaration gains a reason, or both.
  - Whether `operation="import preview"` is honest wording for a step that unpacks archives to
    disk. A user reading *"import preview"* in a busy-drive message would not expect it to have
    written anything.

  ## RELATED

  `(aaw)` (the lock, and the sentence this path did not get), `(afq)` (the same declaration
  pointing the other way), `(aek)` and `(aft)` (one value standing for two states, twice),
  `(afw)` (which app runs write a record - the same per-route-judgement shape).
