# (aaw) Cross-process drive lock ("P1-lite"): design settled, build POST-SOAK.

*Body of entry `(aaw)`. **SHIPPED 2026-08-22.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(aaw) Cross-process drive lock ("P1-lite"): design settled, build POST-SOAK.** Designed
  2026-08-03; filed as its own entry rather than folded into `(vv)` because `(vv)` is a recorded
  *limit* and this is an approved *design*, and `(vv)` now points here. **Do not build before
  soak** - the maintainer's ruling, on the analysis below.
  ## ⚠ RE-RANKED LIVE 2026-08-22 - THE GATE FIRED, AND ITS REASON WAS NEVER SERVED

  *"Do not build before soak"* was the ruling. **Four soaks ran** - 2026-08-20, -21, -21, -22 -
  and this entry did not move, because a deferral whose condition nobody re-reads is
  indistinguishable from one that never expires. `(aef)` carries that pattern.

  ⚠ **But the honest re-ranking is worse than "the gate opened".** The gate's stated reason was
  that *"the soak is what will say which things actually break under real use"* - and **no soak
  tested concurrency at all.** Measured 2026-08-22: not one step in any of the four plans runs two
  processes against one library; the word does not appear in any plan or record. So the evidence
  this waited for **does not exist, and will not arrive from soaks that are finished.**

  Two honest routes, and the maintainer picks: build it on the 2026-08-03 analysis below, which is
  unchanged and still correct, or write the step that actually exercises the one silent-loss path.
  **What is no longer available is deferring it to "the soak".**

  ## ✅ MEASURED 2026-08-22 - THE HARM REPRODUCES, AND THE MECHANISM IS NOT THE ONE BELOW

  The deferral was *"the soak will say which things break"* and no soak tested concurrency, so it
  was measured directly instead: two real `organize --apply` processes, one shared catalog, one
  destination, real photographs from the library.

  **It reproduces.** Byte-exact, one file of 45 in the preserved run:

  ```
  A source : 2,174,172 bytes  sha 9aadb75640926ea1...
  B source : 2,174,180 bytes  sha b2100e551c8c9413...
  on disk  : 2,174,180 bytes  sha b2100e551c8c9413...   <- B's bytes, exactly
  ```

  `a.json` claims that path `"status": "uploaded"` with **A's** sha. **A reported success, wrote a
  catalog row, and the file holds B's photograph.**

  | corpus | attempts | hits | copies lost | each |
  |---|---|---|---|---|
  | 2,110 real photos per side, 6 GB per side | **9** | **2** | **99** and **45** | ~29-39 s |
  | 4 x 300 MB per side (wide window) | **5** | **4** | 3, 3, 1, 2 | ~2 s |

  **Positive control first**: a single-process baseline over 2,108 files showed **0**, and an
  injected replacement was detected as exactly **1**. A zero from this harness means something.

  ⚠ **THE MECHANISM IS UPSTREAM OF `_free_relative`, AND THE ANALYSIS BELOW HAS IT WRONG.** The
  race is not two processes choosing the same free name and one overwriting the other. It is that
  **both stage into the same file**: `safe_copy.py:60-64` sets `STAGING_SUFFIX = ".partial"`
  appended to the **target's** name, so the staging path is a pure function of the destination.
  Two processes writing one destination name write into **one** `.partial`. Then one renames it
  and reports success; the other's rename fails loudly with `ENOENT` on a `.partial` that is no
  longer there, which is what the `FAILED` lines and exit 1 in the runs above actually are.

  **The window, instrumented on unmodified code across 2,108 files** (`_free_relative` returning
  to `StagedCopy.commit`): **min 0.67 ms, median 4.60, p95 8.86, max 414.56, mean 5.26** - about
  **11 seconds of cumulative exposure per 2,110-file run**. Narrow enough that 7 of 9 attempts
  missed; not narrow enough to be safe, and the two processes drift into alignment unaided.

  ## ⚠ WHAT WAS LOST IS A COMPLETE FILE, NOT TORN BYTES - AND THAT DECIDES THE SEVERITY

  Measured over the preserved run's 45: **0 hybrids.** Every destination file is a complete, valid
  photograph; it is simply **the wrong one**, with a catalog row asserting otherwise.

  ```
  claimant's own bytes present          2105
  a COMPLETE but WRONG source              3
  bytes matching NO source (torn)          0
  ```

  The 45 decompose as **42** paths both runs claimed where one run's bytes are gone, plus **3**
  claimed by one run alone whose bytes are not there. ⚠ **Not observed is not impossible**: two
  writers sharing one file descriptor-less path can interleave, and nothing in the code prevents
  it - it was simply not produced in these samples.

  **So the severity is mode-dependent, and both halves must be said:**

  - **Copy mode** - the source survives. What is lost is the *organized copy* plus a **false
    catalog row**: a bookkeeping error with a missing copy behind it, recoverable by re-running,
    and detectable by `verify` because the row's sha will not match the file.
  - **`--move` / `--in-place`** - the source is **gone**. The only copy of that photograph is the
    one that was overwritten. That is irreversible loss, not bookkeeping.

  ## THE FIX OPTIONS - REPORTED, NOT DESIGNED

  **1. Per-process unique staging name.** Give the `.partial` a per-process suffix so two runs
  never share a staging file.
  - *Fixes*: the shared-partial collision entirely, and with it the torn-bytes possibility and the
    misleading `ENOENT` on a missing `.partial`. No platform-specific code, no locking, no new
    dependency; the smallest change of the three.
  - *Leaves*: **who wins the name.** Both still resolve to the same target and both still rename
    onto it, last-write-wins - the residual described above.
  - ⚠ *Costs, and this is the part that is easy to miss*: **it removes the only loud signal.**
    Today the loser fails with `ENOENT` and exits 1, so a user is told something went wrong. With
    unique staging both renames succeed, **both processes exit 0**, and the losing run's catalog
    row is silently wrong. Cheaper, and quieter about a harm it does not fully fix.

  **2. The cross-process lock, as designed below.**
  - *Fixes*: both halves - no two mutating runs overlap, so neither the staging collision nor the
    contested name can occur. It also covers `(afp)`, where a run refuses a catalog another
    process is creating, by making the second run wait instead.
  - *Leaves*: two machines on one cloud mount, already a documented limit; and the in-process case
    `(adt)`, which no cross-process lock can touch.
  - *Costs*: ~25 lines of platform-specific code, six named tests including a two-real-process
    contention test and a Windows branch that must be exercised rather than skipped, and the
    FD-lifetime trap below. A refusal a user must understand, on a path that today just works.

  **3. Both.** Unique staging is correct on its own terms - a staging file is private to the run
  that made it, whatever else is true - and it is the difference between a lock being a *safety*
  property and a *correctness* one.
  - *The question worth ruling on*: with unique staging in place, the lock's remaining job is
    preventing **last-write-wins on a contested name**. Whether ~25 lines plus six tests is worth
    that depends on whether the residual is judged bookkeeping or loss - and the answer above is
    **that it is bookkeeping in copy mode and irreversible loss under `--move`/`--in-place`**,
    which are exactly the modes a user reaches when they have no room for a second copy.

  **The reproduction is kept** at `~/TruestillLibrary/scratch-race-2026-08-22/` - **26 GB** as of
  2026-08-22 - and is the regression evidence for the only measured data-loss defect in the
  product. ⚠ **A future clean-up should know what it is deleting:**
  - **DURABLE, ~12 GB**: `detect.py` (content-based and name-blind - a name cannot show this
    defect), `window.py` (the check-to-replace instrumentation), and the `A`/`B` corpora, whose
    whole point is that **B is A with 8 bytes appended** - same name, same EXIF, different sha, so
    every file is a collision candidate. Rebuilding `B` is scripted; rebuilding the *idea* is not.
  - **REGENERABLE, ~14 GB**: `bigA`/`bigB` (four 300 MB files each, to widen the window) and the
    `dest`/`bdest`/`fdest`/`cdest`/`rdest` trees, which are outputs. All reproducible from the
    corpora above in minutes.
  - **Delete freely**: the `*.log`, `*.json` and `*cat.sqlite*` files - one run's worth each.

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
  - **Known gap left open on purpose, and it has a letter: `(adt)`.** The app's synchronous settings writes (layout,
    organize mode, sidebar, events settings, `dates/confirm`) are not covered by that refusal:
    they are sub-second writes on HTTP routes, and covering them would mean a new HTTP status
    plus teaching `api()` about it, for a millisecond-wide window. A user sees the raw failure
    text in the error banner and retries the click. Recorded rather than built.
