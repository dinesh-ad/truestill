# (abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.

*Body of backlog entry `(abr)`. **Shipped** - see [`SHIPPED.md`](../../SHIPPED.md). The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.** Recorded
  2026-08-07. One of **17** `runJob` call sites; the other sixteen all pass one.
  - `runJob` does `if (started && started.ok === false) { ...; onRefuse(started); return; }`, so
    an `{ok: false}` from `/api/ingest/archives/run` calls `undefined` and lands in `guarded`'s
    fatal-error banner instead of the refusal card.
  - **Reachable** (filed as *probably unreachable* until 2026-09-02, P186): `/api/ingest/archives/run`
    goes through `server.py:create_app._start_drive_job` with `mutating=True`, which answers a busy
    drive with `ok: false` from `jobs.py` - the refusal two sibling call sites already handle.
    Content refusals are answered at `precheck`; a busy drive is not a content refusal.
  - **Filed because of the shape, not the severity.** One site of many differing from its
    siblings is `(aak)` / `(abq)` again, and the two before it were each found only after they
    cost something. The fix is one line; the value is that the next reader of `runJob` sees
    fifteen call sites that agree.
  - **Shipped:** `rcRunArchives` passes `onRefuse` with `startRefusedCard(started, "rc-dest")`.
    `test_every_site_calls_run_job_with_on_refuse` pins every `runJob` site the same way
    `onCancelled` already is.
