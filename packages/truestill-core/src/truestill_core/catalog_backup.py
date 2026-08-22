"""A copy of the catalog taken before the migration chain runs. `(ady)`

**What this is for, and what it is NOT.** A transaction restores what a *failed* step touched.
It cannot restore what a *successful* step deliberately removed: a migration that drops a column
and commits has destroyed that data correctly, and no rollback brings it back. `(adl)` shipped
the per-step transaction and closes *interruption*; this closes *intent*.

**No shipped migration has ever destroyed anything** - the chain is 19 forward steps to v20, all
``ALTER TABLE ADD COLUMN`` / ``CREATE TABLE`` / ``CREATE INDEX`` plus one ``DROP INDEX``. That is
a property of the migrations written so far, not of the mechanism, and the first destructive one
is the one that would find this with the evidence already gone.

Complexity: one pass over the database, O(pages) time and O(1) memory - SQLite copies page by
page inside one ``sqlite3_backup_step``. Measured 2026-08-22 on ext4, Python 3.14.4 /
SQLite 3.46.1: **18.66 ms median** on the real 6,365,184-byte catalog (n=9), **200.23 ms** at
110,628,864 bytes (n=5). Roughly 1.8-2.3 ms/MB, linear, and paid **once per upgrade** rather
than per open.

**Why the online backup API rather than a file copy.** `(adb)` refused a filesystem copy of a
live SQLite database and was right: SQLite says copying one can yield *"some old and some new
content"*. It also refused ``VACUUM INTO`` here, because that rewrites every page - a copy
should reproduce the database, not compact it. What `(adb)` could not use was ``.backup()``,
because it ran in a **separate process** where any external write restarts the operation. This
runs **in-process, on the connection that is about to migrate**, which is the case SQLite
documents as safe: a write through the same connection updates the backup in place.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from truestill_core.app_paths import backup_path_for
from truestill_core.safe_copy import staging_path

#: ⚠ **LOAD-BEARING, NOT A DEFAULT. DO NOT CHUNK THIS FOR PROGRESS REPORTING.**
#:
#: ``-1`` copies every page inside ONE ``sqlite3_backup_step``. Any positive value makes the
#: copy incremental, and an incremental backup is **restarted from the beginning by any write
#: from another connection** - so under a concurrent writer it can never finish.
#:
#: Measured 2026-08-22, 123 MB source, a second connection committing at 376 writes/sec:
#:
#: * ``pages=-1``  -> completed in **2,581 ms**, 1 step, 0 restarts.
#: * ``pages=64``  -> **never committed a single page in 300 s**, killed at its bound, leaving a
#:   0-byte destination and an uncleared ``-journal``.
#:
#: That is `(adb)`'s *"correct-or-never-finishing"* finding, and this constant is the whole of
#: what avoids it: a single step has no inter-step window for a writer to invalidate.
SINGLE_STEP = -1

#: How long to keep retrying a BUSY source before giving up and reporting.
#:
#: ⚠ **This bounds CONTENTION, never the copy.** With :data:`SINGLE_STEP` the progress callback
#: fires once on success - after the copy - so a legitimately slow copy is never interrupted by
#: it. It fires repeatedly only while SQLite is returning ``SQLITE_BUSY``, which is the only
#: state this deadline can end.
#:
#: It exists because CPython's ``Connection.backup`` retries ``SQLITE_BUSY``/``SQLITE_LOCKED``
#: **forever** - there is no timeout parameter, and ``busy_timeout`` does not reach it. Measured:
#: a backup whose source connection held a write transaction sat in ``nanosleep`` for over three
#: minutes, burning no CPU, until it was killed. On the launch path that is a product that never
#: starts (`ENGINEERING_STANDARD.md` §4, forty-third member).
#:
#: 5 s matches the ``busy_timeout`` every other contended wait in this product already uses.
DEADLINE_SECONDS = 5.0

#: Seconds between BUSY retries. Short enough that the deadline above is honoured with useful
#: granularity - the callback is what enforces it, and it only runs between retries.
_RETRY_SLEEP_SECONDS = 0.05


class _ExpiredError(Exception):
    """Raised out of the progress callback to abort a backup that is only ever getting BUSY.

    Private: it never leaves this module. :func:`copy_before_migration` turns it into an outcome
    like every other failure, because a catalog must still open when its safety copy cannot be
    taken.
    """


@dataclass(frozen=True, slots=True)
class BackupOutcome:
    """What happened, in a form a surface can word. **Never an exception.**

    The same shape as `decisions.WriteOutcome`, for the same reason: taking the copy must not be
    able to stop a user opening their own library, so every failure comes back as a report.
    """

    taken: bool
    path: Path | None = None
    error: str = ""


def _copy(source: sqlite3.Connection, staged: Path, deadline: float) -> None:
    """Back ``source`` up to ``staged``, bounded, raising on anything that goes wrong."""
    target = sqlite3.connect(str(staged))
    try:

        def progress(_status: int, _remaining: int, _total: int) -> None:
            # Fires after every step INCLUDING each BUSY retry, which is what makes a deadline
            # expressible at all - verified rather than assumed: 41 callbacks in 2 s against a
            # source that was permanently BUSY.
            if time.monotonic() > deadline:
                raise _ExpiredError

        source.backup(target, pages=SINGLE_STEP, progress=progress, sleep=_RETRY_SLEEP_SECONDS)
    finally:
        with contextlib.suppress(sqlite3.Error):
            target.close()


def _harden(path: Path) -> None:
    """Force the copy's bytes and its directory entry to disk before it takes the real name.

    Mirrors `decisions.write_decisions`: flush, ``fsync``, then rename. A copy that is only in
    the page cache is not a copy if the machine loses power a second later.
    """
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_directory(directory: Path) -> None:
    """``fsync`` the directory so the rename itself survives a power cut.

    Best effort: not every platform lets you open a directory, and failing to harden a rename
    that has already happened is not a reason to report the copy as untaken.
    """
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def copy_before_migration(
    source: sqlite3.Connection,
    catalog_path: Path,
    *,
    deadline_seconds: float = DEADLINE_SECONDS,
) -> BackupOutcome:
    """Copy ``catalog_path`` beside itself before its schema is changed. **Never raises.**

    ⚠ **THE SOURCE CONNECTION MUST NOT BE INSIDE A WRITE TRANSACTION, AND THAT IS NOT A STYLE
    RULE - IT IS AN INFINITE HANG.** Measured 2026-08-22, and the shape of the result is why the
    rule reads as arbitrary without it:

    ======================================================  ==========================
    who holds what                                          outcome
    ======================================================  ==========================
    source connection, no transaction                       COMPLETED, 45.8 ms
    source connection, read-only deferred transaction       COMPLETED, 42.1 ms
    **a DIFFERENT connection holds ``BEGIN IMMEDIATE``**    **COMPLETED, 27.1 ms**
    **the source connection holds ``BEGIN IMMEDIATE``**     **HUNG, killed at 8 s**
    **the source connection has written in a deferred tx**  **HUNG, killed at 8 s**
    ======================================================  ==========================

    So another process's write lock is **harmless**, and the connection's own is fatal. Anyone
    reasoning from "backup needs a stable read, so hold the lock" gets it exactly backwards.
    `catalog._migrate` calls this **after** its ``BEGIN IMMEDIATE`` block has committed, where
    ``in_transaction`` is ``False``; `test_catalog_backup.py` pins that.

    The copy is staged under a per-process name and only renamed onto the real one when it is
    complete, so a partial copy never wears the name of a good one.
    """
    if catalog_path == Path(":memory:"):
        return BackupOutcome(taken=False, error="an in-memory catalog has nothing to copy")

    target = backup_path_for(catalog_path)
    staged = staging_path(target)
    deadline = time.monotonic() + deadline_seconds
    try:
        _copy(source, staged, deadline)
        _harden(staged)
        staged.replace(target)
    except _ExpiredError:
        _discard(staged)
        return BackupOutcome(
            taken=False,
            error=(
                f"the catalog was busy for {deadline_seconds:.0f}s, so no copy was made "
                f"before the upgrade"
            ),
        )
    except (sqlite3.Error, OSError) as exc:
        _discard(staged)
        return BackupOutcome(taken=False, error=f"no copy could be made before the upgrade: {exc}")
    _sync_directory(target.parent)
    return BackupOutcome(taken=True, path=target)


def _discard(staged: Path) -> None:
    """Remove a copy that did not finish.

    ⚠ **The residue is not an empty file, which is why staging is mandatory rather than tidy.**
    Measured: a write failure part-way through left **1,048,576 bytes** at the destination -
    a plausible size - that opens as ``UNREADABLE``, beside a stale ``-journal``. `(adr)`'s
    discriminator is a **0-byte** file and would not have seen it. `decisions.write_decisions`
    already states the general rule: *"A truncated file at the right path is worse than no file,
    because it looks like a backup."*

    A failure to clean up is deliberately swallowed: the staged name is not the real one, so what
    is left is inert, and reporting it would replace the real error with a housekeeping one.
    """
    with contextlib.suppress(OSError):
        staged.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        staged.with_name(f"{staged.name}-journal").unlink(missing_ok=True)
