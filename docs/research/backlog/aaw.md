# (aaw) Cross-process drive lock ("P1-lite"): design settled, build POST-SOAK.

*Body of backlog entry `(aaw)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aaw) Cross-process drive lock ("P1-lite"): design settled, build POST-SOAK.** Designed
  2026-08-03; filed as its own entry rather than folded into `(vv)` because `(vv)` is a recorded
  *limit* and this is an approved *design*, and `(vv)` now points here. **Do not build before
  soak** - the maintainer's ruling, on the analysis below.
  - **What shrank this from "P1", and it is the load-bearing measurement.** SQLite already
    serialises writers, so **the catalog cannot be corrupted by two truestill processes**.
    Measured directly, 2026-08-03: `journal_mode = delete`, `busy_timeout = 5000` (Python's
    `connect(timeout=5.0)` default, not set by us); a second writer blocks **5.009 s** and then
    raises `sqlite3.OperationalError: database is locked`. A **reader is not blocked at all**
    under a held write lock, which is why only writing surfaces are exposed. The hazard is
    filesystem interleaving and plan staleness, not catalog damage.
  - **The one genuine silent-loss path.** Two concurrent `organize --apply` runs. `_free_relative`
    resolves a destination-name collision by *asking the filesystem*, so both processes can pick
    the same free name and one silently overwrites the other. Every other overlap found is loud:
    migrate compares against its journal snapshot and **raises** (see `(vv)`), undo replays rows
    already applied, reclaim deletes idempotently. **It requires deliberately running two
    applies at once**, which is why this waits for soak rather than jumping the queue.
  - **Where the lock lives.** A lock file **local** to the machine, under `app_paths`' data dir
    (the `session_link` precedent), **not** on the drive: FUSE and network mounts are exactly
    where advisory locking is least reliable, a stale lock on the user's own drive is the thing
    they would delete by hand, and the drive marker is meant to be stable identity rather than
    a high-churn runtime file. Keyed by **`DriveRef.key`'s existing scheme** - `uuid:<marker>`
    for a marked drive, else `path:<resolved>` - so the same drive reached by two mountpoints
    still collides and two different drives never block each other. The in-process design
    already answered the granularity question; this is its on-disk twin.
  - **Kernel-enforced, with no PID liveness check and no TTL.** `fcntl.flock(LOCK_EX | LOCK_NB)`
    on POSIX, `msvcrt.locking(LK_NBLCK)` on Windows. The decisive property is that **the OS
    releases these when the process dies** - SIGKILL, crash, or power loss - so "the user is
    locked out of their own library" is a state this design *cannot reach*, and there is no
    stale lock to detect or clear. A PID check would require us to judge liveness and could be
    wrong in the direction of stranding the user; a TTL solves only the cross-machine case that
    is deliberately out of scope. PID, hostname and operation are written **inside** the locked
    file as advisory content for the refusal message only - the flock is the truth.
  - **The FD-not-path trap, which is the real implementation risk.** Both primitives bind the
    lock to the **file descriptor**, so closing the file releases it silently; the FD must be
    held for the operation's whole lifetime. This is the same ownership-window shape as the
    listening-socket handover, and the established in-tree answer is `contextlib.ExitStack` with
    `pop_all()` at the boundary (`__main__.py:235`). A test must assert the lock still holds
    *after* the acquiring function returns.
  - **RULED: hand-rolled, not `filelock`.** `filelock` 3.32.0 is already in `uv.lock` but only
    via `virtualenv`/`python-discovery`, i.e. dev-side, so adopting it is a genuine new runtime
    dependency. It is cheap (pure Python, zero deps of its own) and it **does not solve FUSE** -
    same OS primitives, and its `SoftFileLock` fallback strands a stale lock on a dead process,
    the exact failure this design refuses. The precedent is **`psutil`, rejected** in "Settled
    technical stances" to keep ~60 lines of hand-written platform code; this is ~25. The
    `platformdirs` precedent points the other way but is **weaker here**, because it was
    justified by *"edge cases we would rediscover as bug reports on machines we do not have"* -
    and we have all three machines on every push. Recorded so it is not re-litigated.
  - **RULED: single-machine scope.** CLI-vs-app, CLI-vs-CLI, and app-vs-app across processes.
    Two machines sharing one cloud mount is **a documented limit, not a defended case** - no
    mechanism is reliable there, and saying so beats pretending.
  - **RULED: no `--force`, for a structural reason rather than a policy preference.** Because
    the lock is kernel-enforced, a refusal **always** means a live holder; a crashed process
    leaves nothing to force past. So `--force` could only ever override a *running* operation,
    which is the one thing it must not do. The escape hatch is naming the holder's PID in the
    message, so a user with a genuinely hung process deals with the process rather than the file.
  - **Where it is acquired: the entry layers, never core.** `truestill-core` is a library, and a
    caller that already holds the lock must still be able to use it. App side is **one** call
    site, `server._start_drive_job`. CLI side is the mutating handlers only - organize/ingest
    under `--apply`, migrate-layout, migrate undo, undo-organize, reclaim, clean-empty - roughly
    seven, all already behind `--apply` or a typed confirm. **Read-only paths take nothing**, and
    there is no shared read lock: a preview run during an apply gives a stale preview, which is
    not data loss, while blocking previews would be a worse product than the race.
  - **Two commits.** (1) the primitive and its tests, used by nothing - independently testable,
    and where all the platform risk lives; (2) the wiring, reviewable as a list of call sites,
    with a parity guard that every mutating handler acquires (the shape
    `test_every_drive_touching_route_starts_through_the_locked_helper` already established).
  - **Six named tests.** (i) **two real processes** contending via `subprocess` - a
    single-process test would be coverage theatre, since `JobManager._lock` already covers
    threads; (ii) a killed holder's lock recovered (SIGKILL on POSIX, `terminate()` on Windows),
    proving the never-stuck property, and skipped on no lane; (iii) a live lock respected;
    (iv) a read-only preview not blocked; (v) the FD retained past the acquiring call, which a
    naive `with open(...)` fails; (vi) the Windows branch **exercised on the Windows lane rather
    than skipped**, with an anti-vacuity assertion that the platform branch actually ran.
  - **Already taken, and deliberately not this:** the `database is locked` refusal shipped
    2026-08-03 as the cheap part of this analysis. It converts the *symptom* into an actionable
    sentence on both surfaces; it is **not** a lock and does not serialise anything.
  - **Known gap left open on purpose.** The app's synchronous settings writes (layout,
    organize mode, sidebar, events settings, `dates/confirm`) are not covered by that refusal:
    they are sub-second writes on HTTP routes, and covering them would mean a new HTTP status
    plus teaching `api()` about it, for a millisecond-wide window. A user sees the raw failure
    text in the error banner and retries the click. Recorded rather than built.
