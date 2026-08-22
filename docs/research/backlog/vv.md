# (vv) Known limit: app per-drive job lock is process-local; CLI↔app overlap is not serialized.

*Body of backlog entry `(vv)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(vv) Known limit: app per-drive job lock is process-local; CLI↔app overlap is not serialized.**
  Recorded 2026-07-29 when Commit 3 of (oo) shipped the server-side one-op-per-drive guard.
  - **What is covered.** Concurrent jobs inside one `truestill-app` process (reload, second tab,
    double-click) are refused with `DriveBusy`.
  - **What is not.** The lock lives in `JobManager` memory. A `truestill` CLI invoke in another
    process does not see it, and a restarted app starts empty (no stale lock - deliberate).
    Catalog/journal crash-safety still applies; this is not a claim that two writers cannot
    touch the same drive across processes.
  - **Do not assume solved** when designing reclaim, migrate, or backup concurrency. A real
    cross-process guard (e.g. flock on the drive marker or catalog) is a separate design if
    soak ever shows CLI↔app races mattering in practice.
  - ⚠ **CLOSED IN SUBSTANCE 2026-08-22 BY `(aaw)`, AND THE HEADLINE IS NOW FALSE.** This entry
    asked for *"a real cross-process guard (e.g. flock on the drive marker or catalog)"* and said
    it was *"a separate design if soak ever shows CLI↔app races mattering in practice"*. No soak
    ever tested concurrency; it was measured directly instead, two concurrent applies losing 99
    and 45 organized copies, and the guard shipped: `flock`/`msvcrt`, keyed on the same
    `uuid:`/`path:` identity this entry's in-process lock uses. **CLI↔app and CLI↔CLI overlap on
    a mutating operation IS serialized now.**
    ⚠ **What is left is not a lock**: the session-link half below - a second instance overwriting
    the first's URL file, and quitting it deleting the link to a still-running first - which is
    single-instance detection and belongs to `(adn)`. **Kept open only for that**; if `(adn)`
    takes it, this entry closes.
  - **Date-provenance step 4 narrows this, and does not close it (2026-07-31).** The bake
    refuses to write while a migration is journalled and unfinished on the same drive, reading
    `Catalog.pending_migration` - the journal lives in the shared catalog, so unlike this lock
    it **is** visible across processes. It re-checks before **every file**, so the exposure is
    the gap around a single write rather than the length of a run. **That is a check, not a
    mutex, and the residual race belongs to this item:** closing it needs the cross-process
    on-disk lock described above, deliberately not smuggled into step 4.
  - **CORRECTION 2026-08-03: "app-vs-app is already complete" was wrong, and this entry said
    it.** The 2026-07-31 note above claimed that coverage was complete because every job route
    goes through `server._start_drive_job` keyed on `uuid:<marker uuid>` (pinned by
    `test_every_drive_touching_route_starts_through_the_locked_helper`), leaving only CLI-vs-app
    and CLI-vs-CLI. **That is true within one process and false across two**, which is exactly
    the distinction this whole entry is about - so the claim contradicted its own headline.
    - **The mechanism, read in the code rather than assumed.** `bind_listening_socket` tries
      `for candidate in (preferred, 0)` (`__main__.py:167`): if the preferred port is taken it
      binds an **ephemeral** one instead of refusing. A second `truestill-app` therefore starts
      **successfully**, on another port, with its own `JobManager` and its own empty
      `_occupied` map. Neither instance can see the other's locks. **Double-clicking the icon
      twice is enough** - no unusual invocation is needed.
    - **The session link makes it worse, not merely equal.** `session_link.write` is *replaced,
      never appended*, so the second instance overwrites the first's URL file; and the file is
      *removed when the process exits*, so quitting the second instance **deletes the link to
      the first, which is still running**. The ephemeral port is by then the only way in, and
      nothing records it.
    - **What was actually right in the old note:** the in-process guard and its test. They
      cover what they claim. The error was reading "every route goes through one locked helper"
      as "there is only one `JobManager`".
    - **It had been copied twice more**, which is why the grep matters and not the care:
      `service/bake.py` said the lock covers app-vs-app *"completely"* and
      `test_bake_refuses_during_migration.py` said it *"fully"* and *"already solved"*. All
      three corrected in one commit. `code-quality-audit.md` repeats it too and is left alone -
      it is a dated record of what was believed then, not a live claim.
    - So the exposure is **CLI-vs-app, CLI-vs-CLI, and app-vs-app across processes**. The
      design that closes all three is `(aaw)`.
  - **What the residual actually costs, stated so nobody over-corrects for it.** If the check
    does interleave, migrate compares the relocated file against its journal snapshot, finds the
    baked bytes, and **raises** - a loud, recoverable stall. `destination.relocate` copies rather
    than renames, so the file is preserved at its old path with an orphan at the new one and the
    journal row still pending; nothing is lost. That outcome is *why* `(aah)` was closed rather
    than built: weakening the comparison to avoid this stall would cost a real check, and the
    right fix if soak ever shows it biting is the on-disk lock above.
  - **Not fixed here, on purpose** - recorded only, per instruction.
