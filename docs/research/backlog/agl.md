# (agl) UNDO ACCEPTS A CANCEL AND DROPS IT, AND NOBODY HAS RULED WHETHER IT SHOULD BE CANCELLABLE.

*Body of entry `(agl)`. **OPEN.** The index is [`BACKLOG.md`](../../BACKLOG.md); the provenance index is [`SHIPPED.md`](../../SHIPPED.md).*

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
