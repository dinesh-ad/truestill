# (afq) A PREVIEW OCCUPIES THE DRIVE IN THE APP, AND NOTHING SAYS WHY.

*Body of backlog entry `(afq)`, under **Rulings - decided, no work attached**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afq)** THE APP REFUSES A PREVIEW WHILE AN APPLY RUNS; THE CLI DOES NOT. Split out of `(aaw)`
  on 2026-08-22 rather than folded into it, and the split is the point.

  ## WHAT IS TRUE TODAY

  `_start_drive_job` passes `operation="organize preview"` (`server.py:create_app._start_drive_job`) to `jobs.start`,
  which occupies the drive in `self._occupied` exactly as an apply does (`jobs.py:DriveBusyPayload`). So a
  second tab asking for a preview while an organize runs gets `DriveBusyPayload`. The CLI has
  never done this: `truestill organize` without `--apply` reads and reports, whatever else is
  running.

  ## WHY IT IS NOT `(aaw)`'s TO ANSWER

  ⚠ **`(aaw)`'s lock rests on a data-safety argument, and this behaviour cannot inherit it.**
  Measured: two applies to one destination lose organized copies. A preview writes nothing, so no
  quantity of that evidence says anything about whether a preview should be refused.

  It may well be **right** as a UX choice - a preview whose destination is being rewritten under
  it is misleading, and showing a plan that is already stale is its own kind of lie. But that is a
  *different justification*, and folding it into `(aaw)` would let a UX decision inherit a safety
  argument it has not earned. That is exactly what the 2026-08-03 design did without noticing: it
  ruled *"read-only paths take nothing… blocking previews would be a worse product than the
  race"* while the app had already been blocking them for months, and nobody reconciled the two.

  ## THE QUESTION, NOT DECIDED

  - **Is refusing right, or should a preview run and be labelled stale?** The second keeps the
    surface responsive and needs a way to say *"this plan was made while something else was
    writing"*, which does not exist.
  - **If refusing is right, why does the CLI not?** Two surfaces disagreeing about the same
    question is the shape `(aca)` already carries for confirmation prompts.
  - ⚠ **Whichever way it goes, the reason must be written down as a UX reason.** The failure this
    entry exists to prevent is the next reader finding the refusal, assuming `(aaw)` justified it,
    and extending it somewhere the safety argument does not reach.

  ## RELATED

  `(aaw)` (the lock, shipped 2026-08-22, mutating operations only), `(aca)` (app and CLI disagree
  about when an organize needs confirming), `(adt)` (two writers inside one process).
