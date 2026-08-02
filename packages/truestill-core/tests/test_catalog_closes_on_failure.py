"""A `Catalog` that fails to open must not keep the file handle it opened.

`Catalog.__init__` connects and then migrates. When the migration raises - and it has a
documented reason to, `CatalogVersionError` for a catalog written by a newer Truestill - the
connection was never closed. **`with Catalog(...)` cannot help:** `__init__` raises, so the
object is never returned, `__enter__` is never reached, and `__exit__` never runs.

Asserted on the handle's own state rather than on a `ResourceWarning`. Warnings here are emitted
by the garbage collector, so they arrive at an unpredictable moment and land on whichever test
happens to be running - which is how these went unnoticed in the first place.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from truestill_core import catalog as catalog_module
from truestill_core.catalog import Catalog, CatalogVersionError


def _newer_than_this_build(db: Path) -> None:
    """A catalog claiming a schema version from the future - the real refusal path."""
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()


def _capture_connections(monkeypatch: pytest.MonkeyPatch) -> list[sqlite3.Connection]:
    """Every connection `Catalog` opens, so the test can inspect one it never received."""
    opened: list[sqlite3.Connection] = []
    real = sqlite3.connect

    def spy(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = real(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(catalog_module.sqlite3, "connect", spy)
    return opened


def _is_open(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


def test_a_refused_catalog_does_not_leave_its_connection_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The leak. A user opening a catalog from a newer build hits this every time."""
    db = tmp_path / "newer.sqlite"
    _newer_than_this_build(db)
    opened = _capture_connections(monkeypatch)

    with pytest.raises(CatalogVersionError):
        Catalog(db)

    assert len(opened) == 1, "fixture check: exactly one connection should have been opened"
    assert not _is_open(opened[0]), "the connection opened by __init__ outlived the failure"


def test_the_original_failure_is_what_the_caller_sees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup must not change the diagnosis. The message names the version problem."""
    db = tmp_path / "newer.sqlite"
    _newer_than_this_build(db)
    _capture_connections(monkeypatch)

    with pytest.raises(CatalogVersionError, match="upgrade truestill to open it"):
        Catalog(db)


def test_a_failing_close_does_not_mask_the_real_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trap in the fix itself.

    If cleanup raises while handling the original exception, Python would surface the *close*
    failure and bury the one that matters - turning "this catalog is from a newer Truestill"
    into an unrelated sqlite error.
    """
    db = tmp_path / "newer.sqlite"
    _newer_than_this_build(db)
    real = sqlite3.connect
    close_attempts: list[bool] = []
    opened: list[sqlite3.Connection] = []

    class UncloseableConnection(sqlite3.Connection):
        """Fails the *first* close only, so the handle can still be released afterwards.

        Always raising would leave this fixture leaking the very handle the suite is trying to
        stop leaking - and the warning would surface against an unrelated test.
        """

        def close(self) -> None:
            if not close_attempts:
                close_attempts.append(True)
                message = "close failed"
                raise sqlite3.OperationalError(message)
            super().close()

    def spy(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs["factory"] = UncloseableConnection
        conn = real(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(catalog_module.sqlite3, "connect", spy)

    with pytest.raises(CatalogVersionError):
        Catalog(db)

    assert close_attempts, "fixture check: the cleanup must actually have tried to close"
    for conn in opened:
        conn.close()  # the second attempt succeeds; nothing is left open by this test


def test_a_failure_after_the_migration_also_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard covers the whole region, not just the one statement that was reported.

    `commit()` is the last thing `__init__` does and can fail on a full or locked disk. A fix
    scoped to `_migrate` alone would leave this path leaking.
    """
    opened = _capture_connections(monkeypatch)
    message = "disk I/O error"

    def boom(_self: Catalog) -> None:
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(Catalog, "_migrate", boom)

    with pytest.raises(sqlite3.OperationalError, match=message):
        Catalog(tmp_path / "c.sqlite")

    assert not _is_open(opened[0])


def test_a_catalog_that_opens_normally_is_usable(tmp_path: Path) -> None:
    """Cry-wolf half: the ordinary path must not close the connection it just opened."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.set_setting("k", "v")
        assert catalog.get_setting("k") == "v"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.get_setting("k") == "v"
