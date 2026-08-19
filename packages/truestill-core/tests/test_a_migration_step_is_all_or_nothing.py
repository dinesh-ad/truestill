"""A migration step that fails part-way leaves the catalog exactly as it was. `(adl)`.

**The defect, measured before the fix.** `_migrate` ran the chain outside any transaction and
stamped the version in a *separate* statement from the step that earned it, so forcing the v4 step
to raise after its first of three statements left:

    user_version = 3      the stamp never ran
    files.event_id        PRESENT   - the step's first half, autocommitted
    events table          ABSENT    - the step's second half, never ran

A schema that has moved and a version that has not. **No code can reason about that state**, and
it is what Open WebUI's users meet as `duplicate column name: ...` cascading into "table already
exists" and "no such column" on each re-run, remedied by hand-written SQL.

⚠ **Our own migrations absorb it today, and that is why this was survivable rather than fine.**
Every step is guarded, so a retry skips what already landed - `test_migration_safety.py` pins
exactly that and argues from it that a transaction is unnecessary. The argument holds only while
no migration backfills: DDL autocommits and DML does not, so a crash between them would commit
the column, roll back the data, and then have the column guard **skip** the retry - leaving an
empty column for ever. This closes that by construction rather than by convention.

**Why a transaction works here, which was doubted and is now measured.** `PRAGMA user_version` is
itself transactional: rolled back, it returns to the old value together with the DDL beside it. So
with the stamp *inside* the step's transaction, "the migration ran but the version stayed old"
stops being a state the code can produce.

⚠ **Under `LEGACY_TRANSACTION_CONTROL` this needs an EXPLICIT `BEGIN`.** Python opens an implicit
transaction before DML only; DDL autocommits, and `rollback()` after a bare `ALTER TABLE` does
nothing. That is the whole reason the chain behaved this way, and it is why `Catalog._tx` cannot
be reused here - it never issues a `BEGIN`.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from truestill_core import catalog as catalog_module
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

#: The step to interrupt. v4 is the natural choice: it does an `ALTER TABLE` and then creates two
#: tables, so "part-way" is a real place to stop rather than a contrived one.
_STEP = 4
_COLUMN = "event_id"
_TABLES = ("events", "skipped_clusters")


class _PowerLossError(Exception):
    """Stands in for a crash mid-migration, matching `test_migration_safety.py`'s injector."""


def _at_version_three(db: Path) -> None:
    """A real catalog wound back to v3, so the v4 step is the next one the chain will run."""
    with Catalog(db):
        pass
    conn = sqlite3.connect(str(db))
    for table in _TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"ALTER TABLE files DROP COLUMN {_COLUMN}")
    conn.execute(f"PRAGMA user_version = {_STEP - 1}")
    conn.commit()
    conn.close()


def _shape(db: Path) -> tuple[int, bool, bool]:
    """`(user_version, the column exists, the tables exist)` - the three facts that must agree."""
    conn = sqlite3.connect(str(db))
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        columns = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return version, _COLUMN in columns, all(t in names for t in _TABLES)
    finally:
        conn.close()


def _chain_where(
    step: int, fn: Callable[[sqlite3.Connection], None]
) -> AbstractContextManager[Any]:
    """`_MIGRATIONS` with one step replaced, patched for the duration of the `with`.

    Scoped rather than a fixture: two of the tests below need the patch to end **before** their
    second open, and a fixture that lives to the end of the test cannot give them that.
    """
    swapped = tuple((v, fn if v == step else f) for v, f in catalog_module._MIGRATIONS)
    return patch.object(catalog_module, "_MIGRATIONS", swapped)


def _half_a_step(conn: sqlite3.Connection) -> None:
    """The v4 step's first statement, then a crash. The rest of it never runs."""
    conn.execute(f"ALTER TABLE files ADD COLUMN {_COLUMN} INTEGER")
    raise _PowerLossError


def test_a_step_that_fails_part_way_leaves_nothing_behind(tmp_path: Path) -> None:
    """THE GUARD. Fails against the old code on the column assertion, which is the half-lift."""
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)

    with _chain_where(_STEP, _half_a_step), pytest.raises(_PowerLossError), Catalog(db):
        pass

    version, has_column, has_tables = _shape(db)
    assert version == _STEP - 1, "the version must not claim a schema the step never finished"
    assert not has_column, (
        "the interrupted step's first statement survived. The schema has moved and the version "
        "has not, which is a state no later code can reason about - and it is what produces "
        "`duplicate column name` on the next open."
    )
    assert not has_tables


def test_a_step_that_runs_a_multi_statement_script_is_atomic_too(tmp_path: Path) -> None:
    """⚠ THE `executescript` HALF, and it is a separate guard because it fails separately.

    Python documents `executescript` as issuing an implicit `COMMIT` **first**. So a step that
    opened a transaction and then called it would silently commit everything done so far and run
    the rest outside any transaction - the wrapper would look right and roll back nothing. Ten of
    the eighteen steps were written that way.

    This interrupts v4 **after** its full real body, including the two-table script. With
    `executescript` in place the column and both tables survive the rollback; converted to
    per-statement `execute` they do not. That is the difference this test exists to see, and it is
    invisible to a test whose double only calls `execute`.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)
    real = dict(catalog_module._MIGRATIONS)[_STEP]

    def whole_step_then_die(conn: sqlite3.Connection) -> None:
        real(conn)
        raise _PowerLossError  # after the whole step, before the version is stamped

    with _chain_where(_STEP, whole_step_then_die), pytest.raises(_PowerLossError), Catalog(db):
        pass

    version, has_column, has_tables = _shape(db)
    assert version == _STEP - 1
    assert not has_tables, (
        "the step's `executescript` committed its tables despite the rollback - Python issues an "
        "implicit COMMIT before running a script, so the transaction was already gone. Those "
        "statements must go through `execute` one at a time."
    )
    assert not has_column


def test_the_interruption_is_really_reached(tmp_path: Path) -> None:
    """Cry-wolf half. If the injection stopped firing, the guard above would pass for the wrong
    reason - a step that never ran leaves nothing behind either."""
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)
    with _chain_where(_STEP, _half_a_step), pytest.raises(_PowerLossError), Catalog(db):
        pass


def test_the_next_open_completes_the_upgrade_instead_of_a_duplicate_column(tmp_path: Path) -> None:
    """Rolling back must not strand the catalog: the interruption is recoverable, not terminal.

    ⚠ **This one passes before the fix as well, and saying so is the point.** Our migrations are
    guarded - the real v4 step skips its `ALTER` when the column is already there - so idempotence
    already carried the half-lift, which is exactly what `test_migration_safety.py` pins and why a
    transaction was judged unnecessary. This test does not discriminate; it is here so the
    rollback cannot strand a catalog it used to heal.

    **What the guards do NOT cover** is the case that file's own docstring names: a migration that
    backfills. DDL autocommits and DML does not, so a crash between them commits the column and
    rolls back the data - and the column guard then *skips* the retry, leaving the row empty for
    ever. That is the cascade this fix actually removes, and it is unreachable today only because
    no migration backfills.

    The patch is scoped to the FIRST open, deliberately: left active it would make the retry fail
    because the step still raises, proving nothing about recovery.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)

    with _chain_where(_STEP, _half_a_step), pytest.raises(_PowerLossError), Catalog(db):
        pass

    with Catalog(db) as catalog:  # unpatched: the real v4 step, on a catalog that rolled back
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION

    version, has_column, has_tables = _shape(db)
    assert (version, has_column, has_tables) == (CURRENT_SCHEMA_VERSION, True, True)


def test_a_clean_stop_between_steps_leaves_the_version_and_schema_agreeing(tmp_path: Path) -> None:
    """⚠ WHAT THIS FIX DOES **NOT** CLOSE, asserted so it is not credited with more than it does.

    A per-step transaction makes each step atomic. It does not make the *chain* atomic, and it is
    not meant to: interrupted BETWEEN steps, the catalog sits at version N with schema exactly N.
    The schema and the stamp **agree**, so the state is ordinary and resumable - the next open
    reads N and continues at N+1, which is what the chain already does.

    That is a different thing from the half-lift above, and collapsing the two would let this fix
    read as whole-chain atomicity, which it is not.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)

    def die_before_the_fifth(_conn: sqlite3.Connection) -> None:
        raise _PowerLossError  # cleanly, before this step did anything

    with _chain_where(_STEP + 1, die_before_the_fifth), pytest.raises(_PowerLossError), Catalog(db):
        pass

    version, has_column, has_tables = _shape(db)
    assert version == _STEP, "the completed step must have stamped its own version"
    survived = "rolling back a LATER step must not undo an earlier step that committed"
    assert has_column, survived
    assert has_tables, survived


def test_concurrent_openers_of_a_behind_catalog_all_succeed(tmp_path: Path) -> None:
    """⚠ THE SECOND DEFECT THIS CLOSED, and it was not the one the fix was written for.

    `(adl)` also recorded that every migration's guard is a **check-then-act** outside any lock, so
    two openers of a behind catalog could both pass the column check and both `ALTER`. Measured
    before this change on the real catalog: **8% of opens failed at six openers, 12% at twelve**,
    with `duplicate column name`, and 100% when the two were forced to interleave.

    Taking the step's transaction as **IMMEDIATE** closes it, because the guard's read and the
    write it decides now happen under one RESERVED lock. Measured after: **960 opens, zero
    failures**, at six and twelve openers, forced and natural.

    **A deferred `BEGIN` does not do this**, which is why this test is separate from the
    all-or-nothing ones above - those pass either way. Deferred starts on SHARED, SQLite refuses
    the SHARED->RESERVED upgrade immediately without honouring `busy_timeout`, and the failures
    come back as `database is locked` instead.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)
    openers, outcomes = 6, []
    lock = threading.Lock()
    start = threading.Barrier(openers)
    checked = threading.Barrier(openers, timeout=2.0)
    real_columns = catalog_module._column_names

    def gated(conn: sqlite3.Connection) -> set[str]:
        """Hold every opener AFTER its column check and BEFORE it acts - forcing the race."""
        seen = real_columns(conn)
        with contextlib.suppress(threading.BrokenBarrierError):
            checked.wait()
        return seen

    def opener() -> None:
        start.wait()
        try:
            with Catalog(db) as catalog:
                assert catalog.schema_version == CURRENT_SCHEMA_VERSION
            with lock:
                outcomes.append("ok")
        except Exception as error:  # the failure IS the measurement here
            with lock:
                outcomes.append(f"{type(error).__name__}: {error}")

    with patch.object(catalog_module, "_column_names", gated):
        threads = [threading.Thread(target=opener) for _ in range(openers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

    assert outcomes == ["ok"] * openers, (
        f"a concurrent open of a behind catalog failed: {outcomes}. Each step's transaction must "
        "be IMMEDIATE so the migration's own column guard and the ALTER it decides are one atomic "
        "step; deferred leaves them a check-then-act and the loser reports a broken catalog."
    )


def test_a_crash_at_the_stamp_itself_undoes_the_step(tmp_path: Path) -> None:
    """⚠ THE MUTATION THE WHOLE FIX IS ABOUT, and nothing else in this file catches it.

    Moving `PRAGMA user_version` back **outside** the transaction - committing the step, then
    stamping - passes every other test here, because they inject their failure *inside* the step
    and both arrangements roll that back identically. The difference lives in the gap between the
    commit and the stamp, so the crash has to be injected exactly there.

    `set_authorizer` is what makes that possible: it can deny one specific statement, and denying
    the stamp is a faithful stand-in for dying at it. A trace callback cannot - it swallows
    exceptions - which is why this is not written the obvious way.

    Stamp inside: the deny rolls the step back, so the catalog is untouched.
    Stamp outside: the step is already committed, and the schema has moved while the version has
    not - the half-lift, back again.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)
    real_connect = sqlite3.connect

    def connect_denying_the_stamp(*args: object, **kwargs: object) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)  # type: ignore[arg-type]

        def authorize(action: int, arg1: str | None, arg2: str | None, *_rest: object) -> int:
            # ⚠ ONLY THE WRITE, AND ONLY THIS STEP'S. `arg2` carries the value for
            # `PRAGMA user_version = N` and is None for a read. Denying reads too made this test
            # pass for the wrong reason - the open died at `_migrate`'s fast-path read, no
            # migration ran, and "nothing was left behind" was trivially true. Caught by the
            # mutation it was written to kill surviving anyway.
            deny = action == sqlite3.SQLITE_PRAGMA and arg1 == "user_version" and arg2 == str(_STEP)
            return sqlite3.SQLITE_DENY if deny else sqlite3.SQLITE_OK

        conn.set_authorizer(authorize)
        return conn

    with (
        patch.object(sqlite3, "connect", connect_denying_the_stamp),
        contextlib.suppress(sqlite3.DatabaseError),
        Catalog(db),
    ):
        pass

    version, has_column, has_tables = _shape(db)
    assert version == _STEP - 1
    assert not has_column, (
        "the step committed and then failed to stamp its version, leaving a schema that has "
        "moved and a version that has not. The stamp must be INSIDE the step's transaction - "
        "that is the entire point of `(adl)`, and it is the one thing this file exists to pin."
    )
    assert not has_tables


def test_the_stamp_deny_really_reaches_the_migration(tmp_path: Path) -> None:
    """Cry-wolf half for the test above, and it is owed rather than optional.

    Denying too much makes that test pass for the wrong reason: the open dies at `_migrate`'s
    fast-path `PRAGMA user_version` read, no migration ever runs, and "nothing was left behind"
    is trivially true. This asserts the step DID run - by letting it stamp, and finding the
    catalog moved on.
    """
    db = tmp_path / "catalog.sqlite"
    _at_version_three(db)
    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
    assert _shape(db)[1], "the v4 step never ran at all, so the deny above proves nothing"
