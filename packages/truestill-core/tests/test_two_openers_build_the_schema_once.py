"""Two real threads opening one fresh catalog build its schema exactly once, and both survive.

**The defect, measured rather than reasoned.** `_migrate` read `PRAGMA user_version`, then read
`sqlite_master`, then wrote - three unsynchronised steps, so two openers on a fresh catalog both
decided it was empty and both built it. CI run `31810809571` traced **2170 schema writes from
7696 opens**, and one of those redundant writers held the file for **20260 ms** while the others
expired against `sqlite3.connect`'s 5 s timeout. 104 `database is locked` stacks in one run, all
inside `_migrate`. The `duplicate column` failures are the same race read the other way: an opener
that saw `version = 0`, then found `files` already built by the winner, and ran all 18 migrations
against a schema that was already current.

**Why this asserts on the writer count and not on an exception.** Both openers *succeed* today -
`_SCHEMA` is `CREATE TABLE IF NOT EXISTS` throughout, so building it twice raises nothing. A test
that only checked for errors would have passed against the broken code. What is wrong is the
second build happening at all.

**Why it also asserts both openers succeed, which is the half that stops it testing the wrong
thing.** A plain `BEGIN` instead of `BEGIN IMMEDIATE` also yields one writer - by making the
loser fail. SQLite cannot upgrade a deferred transaction's SHARED lock to RESERVED while another
connection holds one, and returns `SQLITE_BUSY` *immediately*, without honouring `busy_timeout`.
One writer and a casualty is not the fix; the pair of assertions is what tells them apart.

**The race is forced, not hoped for.** `sqlite3.Connection.set_trace_callback` fires once per
statement, so the two threads are held together at the `sqlite_master` read - after both have
connected, before either can write. No hook is added to `Catalog` for this: a seam that exists
only for a test is a seam that can drift from the code it claims to cover.

⚠ **The barrier's timeout is load-bearing.** The first version waited 15 s, and under the fix the
loser cannot reach that read until the winner commits - so the winner blocked inside its own
transaction until the barrier expired, past the 5 s busy timeout, and the loser reported
`database is locked`. That reads exactly like "the fix made it worse". Two seconds, and a broken
barrier meaning "go", so it forces the race where a race exists and steps aside where it cannot.
"""

from __future__ import annotations

import collections
import contextlib
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

from truestill_core.catalog import Catalog

#: Two is enough: the defect is a check-then-act, and one interleaving exhibits it.
OPENERS = 2

#: Long enough that both threads arrive when they can, short enough that the winner giving up on
#: the other stays well inside the 5 s busy timeout.
RENDEZVOUS_SECONDS = 2.0

_READ = "SELECT name FROM sqlite_master"
_FIRST_SCHEMA_STATEMENT = "CREATE TABLE IF NOT EXISTS FILES"


def _open_twice(db: Path) -> tuple[list[str], collections.Counter[int]]:
    """Open ``db`` from two threads held together between the check and the act."""
    real_connect = sqlite3.connect
    barrier = threading.Barrier(OPENERS, timeout=RENDEZVOUS_SECONDS)
    writers: collections.Counter[int] = collections.Counter()
    counting = threading.Lock()

    def traced_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = real_connect(*args, **kwargs)  # type: ignore[arg-type]
        arrived: list[int] = []

        def trace(statement: str) -> None:
            flat = " ".join(statement.split())
            if flat.startswith(_READ) and not arrived:
                arrived.append(1)
                # Suppressed, not handled: a broken barrier means the other opener CANNOT
                # reach this point, which is the fixed behaviour. Proceed rather than deadlock.
                with contextlib.suppress(threading.BrokenBarrierError):
                    barrier.wait()
            if flat.upper().startswith(_FIRST_SCHEMA_STATEMENT):
                with counting:
                    writers[threading.get_ident()] += 1

        connection.set_trace_callback(trace)
        return connection

    outcomes: list[str] = []

    def opener() -> None:
        try:
            with Catalog(db) as catalog:
                assert catalog.schema_version > 0
            outcomes.append("ok")
        except Exception as error:  # the failure IS the measurement here
            outcomes.append(f"{type(error).__name__}: {error}")

    with patch.object(sqlite3, "connect", traced_connect):
        threads = [threading.Thread(target=opener) for _ in range(OPENERS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

    return outcomes, writers


def test_the_race_is_actually_forced(tmp_path: Path) -> None:
    """Cry-wolf guard. If the trace callback stopped matching - a reworded SELECT, a renamed
    table - both threads would sail past the rendezvous, the race would never occur, and the
    guard below would pass for the wrong reason. Assert the seam fired before trusting it."""
    outcomes, writers = _open_twice(tmp_path / "catalog.sqlite")
    assert len(outcomes) == OPENERS, f"an opener never finished: {outcomes}"
    assert sum(writers.values()) >= 1, (
        "no thread executed the first schema statement, so the trace callback never matched. "
        f"Looked for a statement starting {_FIRST_SCHEMA_STATEMENT!r}; the schema has changed "
        "and this file's seam has to change with it."
    )


def test_two_openers_build_the_schema_once(tmp_path: Path) -> None:
    """THE GUARD. Both halves matter - see the module docstring on plain `BEGIN`."""
    outcomes, writers = _open_twice(tmp_path / "catalog.sqlite")

    assert outcomes == ["ok"] * OPENERS, (
        f"an opener failed: {outcomes}. One writer bought by making the other fail is not the "
        "fix - a deferred BEGIN produces exactly that, since SQLite refuses a SHARED-to-RESERVED "
        "upgrade immediately and does not honour busy_timeout."
    )
    assert len(writers) == 1, (
        f"{len(writers)} of {OPENERS} openers built the schema; exactly one should. The version "
        "read, the sqlite_master check and the write must be one atomic step under the write "
        "lock, or two processes both decide the catalog is empty and both build it."
    )
