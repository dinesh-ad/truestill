# (yy) Reconnect a moved location (Lightroom-style Find Missing Folder).

*Body of backlog entry `(yy)`, **shipped** - listed in [`SHIPPED.md`](../../SHIPPED.md), not in
[`BACKLOG.md`](../../BACKLOG.md). The letter namespace is shared between the two. ⚠ This line said
"under **Approved - still to build**" until 2026-08-22, three weeks after the body below started
saying **BUILT 2026-08-02** four lines further down.*

- **(yy) Reconnect a moved location (Lightroom-style Find Missing Folder).** Ruled by
  the maintainer 2026-07-30 after research into how Lightroom Classic repairs a moved library -
  the closest mature analogue. **BUILT 2026-08-02** as `truestill repoint-sources OLD NEW`:
  preview, content proof, typed `repoint`. Cross-reference **(xx)** (`files.source_path`
  absolute), which stays open for the two journals below.
  - **The proof is the feature, not the rewrite.** `reclaim` deletes `files.source_path`, and
    its gate re-hashes the **destination copy on the drive** - `plan_reclaim` only checks that
    the source *exists*, and never hashes it. So a path repointed at the wrong tree would have
    reclaim delete a file it never verified at all, on the strength of a different file being
    intact. The repoint therefore refuses unless `drive_adoption.inspect_root` proves the new
    root holds the recorded content: stat-sample, then 3 full reads that must all agree. Reused
    rather than reimplemented - it is the same question `(aap)` asks, with the same measured
    thresholds. **This is a stronger claim than "reclaim re-verifies", which is what the
    original scoping assumed; that re-verification is of the copy, not the source.**
  - **Out of scope, decided rather than forgotten.** `reclaim_journal.source_path` is crash
    resume: a row exists only between the record and the clear, and one that survives describes
    a deletion already in flight. Rewriting it could point a stale journal row at a *live* file
    in the new tree, which is worse than leaving it stale. `inplace_runs.source_root` /
    `dest_root` are undo state with `--source-root` / `--dest-root` overrides that already
    work; rewriting undo records is its own decision on a reversal path. Neither belongs in a
    change about source provenance.
  - **Why Lightroom's version works at scale.** Reconnecting the *top-level* missing
    folder cascades to every subfolder in one action. That cascade is load-bearing: without
    it, a moved library is a per-folder slog; with it, the fix is roughly two minutes.
  - **Scope for truestill - narrow on purpose.** Needed **only** for `files.source_path`
    (and the reclaim / search / near-dup labels that read it). After a move those absolute
    sources are dead: reclaim reports missing rows instead of offering deletes, and Find /
    near-dup display cites old paths. **Drive-relative copies need no repair at all** -
    custody is uuid + `file_copies.relative` under the marker; do not invent a reconnect
    flow for organized drive trees or anyone will over-build what already survives a remount
    (see [`moving-machines.md`](../../moving-machines.md)).
  - **Design when built.** Point once at the new root; rewrite the stored absolute prefix
    for every affected `files.source_path` row; preview-then-typed-confirm like every other
    bulk change in this product; never silent. Cascade from the chosen root the way
    Lightroom cascades from the top folder - one action, all descendants.
  - **Not fixed here, on purpose** - recorded only, per instruction.
