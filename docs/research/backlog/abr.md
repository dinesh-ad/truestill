# (abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.

*Body of backlog entry `(abr)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.** Recorded
  2026-08-07. One of **15** `runJob` call sites; the other fourteen all pass one.
  - `runJob` does `if (started && started.ok === false) { ...; onRefuse(started); return; }`, so
    an `{ok: false}` from `/api/ingest/archives/run` calls `undefined` and lands in `guarded`'s
    fatal-error banner instead of the refusal card.
  - **Probably unreachable today** - archive refusals are answered at `precheck`, and the run
    endpoint is not known to return `{ok: false}` - which is why this is filed rather than fixed.
    It was found by routing that endpoint to a refusal in a test, not by a real run.
  - **Filed because of the shape, not the severity.** One site of many differing from its
    siblings is `(aak)` / `(abq)` again, and the two before it were each found only after they
    cost something. The fix is one line; the value is that the next reader of `runJob` sees
    fifteen call sites that agree.
