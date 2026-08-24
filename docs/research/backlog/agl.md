# (agl) UNDO ACCEPTS A CANCEL AND DROPS IT, AND NOBODY HAS RULED WHETHER IT SHOULD BE CANCELLABLE.

*Body of entry `(agl)`. **SHIPPED 2026-08-24** - option (c), ruled by the maintainer from the
field. The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with
[`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-24 - option (c), and the research prior below was wrong
>
> The cancel is accepted and honoured **between files**: the restore in flight completes, then the
> run stops and reports. `run_undo` takes a `cancel`, the app's target no longer discards it, and
> `UndoStop` gained a `kind` so a cancel cannot be worded as a fault.
>
> ⚠ **The prior in *Research before ruling* - "restores are treated as safer to finish than to
> stop" - is REFUTED, and the entry was right to call it a hypothesis.** Every system checked
> accepts the cancel and defines what it means: Oracle's tape library completes the in-progress
> operation before returning the tape to its source cell, IBM Spectrum Protect names the
> interrupted state a **restartable restore session**, and SQL Server's `RESTORE WITH RESTART`
> states there is no resume. The counter-example is Windows Explorer's unresponsive Cancel on a
> stalled copy, whose real cost is that people stop trusting the operation. **NULL, reported as a
> finding:** Immich, PhotoPrism and digiKam offered no prior art - they do not move your files, so
> the question never arises for them. **rsync and restic were the entry's named candidates and
> neither is the closer analogue**; the systems above are, because they reverse a destructive
> arrangement of data that has no second copy.
>
> ⚠ **The option (b) argument is not dismissed, it is answered.** *"A reversal stopped halfway
> leaves MORE files displaced than one allowed to finish"* is true, and the answer is that the
> stop is **named and recoverable** rather than avoided: the run stays armed, the journal rows
> stay valid, and both surfaces tell the user a second undo finishes the job.
>
> **Kept below unedited** - the three options and the argument against cancelling are the reasoning
> the ruling was made against, and a body rewritten to match its outcome stops being evidence.

> ## ⛔ THE FIRST QUESTION IS NOT "WIRE IT UP"
>
> It is **whether undo should be cancellable at all**, and that decides the design. Wiring it
> first would settle the product question by implementation rather than by ruling.

## What is true today

`undo.run_undo` takes **no `cancel` parameter**. `service/organize_undo.py`'s job target takes
`_cancel: threading.Event` and **ignores it**, so the app's stop button cannot stop an undo.

⚠ **"Deliberately uninterruptible" is not today's state, and documenting it as such would dress an
oversight as a decision.** A parameter named `_cancel` is one accepted and dropped, and the
underscore that tells the linter it was intentional is the same thing that hides it from a reader.
**Whatever is chosen, the signature must stop claiming to take something it ignores.**

## The argument that must be answered, not skipped

**A reversal stopped halfway leaves MORE files displaced than one allowed to finish.** So *stop*
on undo may be the button that causes the harm - which is the opposite of what a stop button
usually means, and is why this is a product question rather than a wiring task.

Against it: a user who realises mid-undo that they are reversing the wrong run has no way out, and
a reversal of 33,000 files takes about **3.1 minutes** (measured, `(afw)`).

## Three options, not one implementation

* **(a) Cancel wired through `run_undo`.** Undo becomes interruptible and the record describes the
  partial. **`UndoOutcome.stopped` already exists** - `(afw)` built it for the persistent-condition
  abort - so the record shape is in place and this is the cheapest of the three to build.
* **(b) Undo declared uninterruptible ON PURPOSE.** The parameter is **removed** rather than
  underscored, and the UI's stop button is disabled with a sentence saying why: *"stopping now
  leaves more files displaced"*.
* **(c) Cancel honoured only BETWEEN files, never mid-file.** Likely the honest middle: no rename
  is ever interrupted, and the user's stop is respected within one file's latency.

## Research before ruling, and it is a hypothesis rather than a finding

What do **rsync**, **restic** and desktop file managers do about interrupting a **restore** rather
than a backup? The prior is that restores are treated as safer to finish than to stop, but that is
untested. Report nulls as findings.

## Not in scope for `(afw)`

Folding this into the record stage would have put an unanswered product question inside a stage
that was already changing a contract.

## ⚠ MEDIUM CORRECTION, 2026-08-23

The "about 3.1 minutes" above was measured end-to-end on **tmpfs** (P22's finding). Spot-checked
on real ext4: pure SHA-256 reads **1,145 MiB/s** (hashing is CPU-bound, not the bottleneck), but
undo's per-file catalog write costs **~2.5 ms on ext4** (measured in `(agk)`'s correction), so
the real-disk figure is plausibly **4-5 minutes** at 33k. **The conclusion the entry uses
survives - minutes, worth stating to the user - and the exact 3.1 is retired as tmpfs-measured.**
