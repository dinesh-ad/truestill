# (akn) AN ORPHANED STAGING TREE HAS NO OWNER RECORDED, SO NOTHING CAN SWEEP ONE SAFELY - AND THE KEPT TREE IS NOT REUSED.

*Body of entry `(akn)`, in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(akn)** Filed 2026-09-12, on closing `(aht)`. Both halves of this are things that ruling
  deliberately did **not** build, recorded so the reasons survive the decision.

  ## WHY NO ORPHAN SWEEP WAS BUILT

  PaperCut sweeps orphans **at startup** rather than on a timer, and that is the right shape: the
  case being handled is a process that died without cleaning up, not a directory that got old.
  The shape is not the problem here. The problem is that **a sweep cannot tell the two states
  apart**, because the journal does not record which one it is in.

  `archive_extract._write_journal` writes `{"staging_root": ..., "sources": [...]}` and nothing
  else. After `(aht)`'s ruling the trees that exist on a drive are:

  | how it got there | what a sweep should do |
  |---|---|
  | a run was cancelled, failed, or was refused | **keep** - it is the retry material, promised |
  | a process died mid-extraction | remove |
  | a clean import | already gone, it removes its own |

  Rows one and two are **byte-identical on disk**. A startup sweep would delete row one, which is
  exactly the thing this ruling just promised the user, and it is GitLab's age-based cron wearing
  a different hat - their sweep ate imports that were still running because age says nothing
  about ownership. A sweep here would eat imports that were about to be retried because presence
  says nothing about intent.

  ⚠ **This is not "later, when there is time".** A sweep written today would be wrong, and the
  thing that makes it right is a change to what the journal records - the run's outcome, or its
  id - which is design work with its own question (what does a journal say about a run that never
  reached an outcome?). `(ago)`'s bar: an artifact has to earn itself, and this one cannot yet.

  ## THE SECOND HALF: KEEPING IT SAVES NOTHING TODAY

  `(aht)` measured it directly - *"the second run unpacked all 534 files again"*. Previewing again
  re-extracts into the same path. So a kept tree costs the user disk and saves them no time, and
  the argument for keeping it is only that **deleting it would be worse**: a retry would then pay
  a second full extraction of a 200 GB export.

  The completion card is worded against this and does not claim reuse. Making the claim true means
  the extractor asking "is this tree already the whole of this archive set?" - which is the same
  journal question as above, from the other side. That is why the two halves are one entry.

  ## WHAT WOULD SETTLE IT

  - Decide what the journal records about its run, then the sweep and the reuse both follow.
  - Until then: every clean import cleans itself, and every other outcome names its tree on screen.

  ## RELATED

  `(aht)` (closed, the ruling), `(ags)` (staging under the destination), `(ahp)` (the crash whose
  artifact `(aht)` was found in).
