"""Not every unwritable catalog is a `sqlite3.Error`. `(aen)`

`Catalog.__init__` creates the catalog's parent directory **before** it connects, so on a
read-only or full disk the failure is a ``PermissionError`` that never reaches SQLite - and both
surfaces' catalog handlers are written around ``sqlite3.Error``. It walked past them and reached
the terminal as a stack.

The second half of the same entry is a wording defect rather than a missing guard: the backstop
sentence is reached from **any** command, including ones that write nothing, so it may not say
what the run "did".
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.catalog_busy import (
    CatalogUnwritableError,
    catalog_unwritable_message,
    is_catalog_busy,
    is_catalog_unwritable,
)

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="chmod 555 does not deny the owner on Windows; this refusal has no Windows equivalent",
)


@posix_only
def test_a_catalog_directory_that_cannot_be_created_is_a_condition_not_a_crash(
    tmp_path: Path,
) -> None:
    """The `mkdir`, which happens before SQLite is asked anything."""
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        with pytest.raises(CatalogUnwritableError) as caught:
            Catalog(parent / "nested" / "catalog.sqlite")
    finally:
        parent.chmod(0o755)

    assert isinstance(caught.value.cause, OSError)
    assert caught.value.directory == parent / "nested"
    assert is_catalog_unwritable(caught.value), "it must reach the same refusal as a SQLite one"
    assert not is_catalog_busy(caught.value), "nothing here clears by waiting"
    assert "EACCES" in catalog_unwritable_message(caught.value)


def test_it_is_not_an_oserror_so_a_filesystem_handler_cannot_absorb_it() -> None:
    """⚠ The codebase is full of `except OSError` around filesystem work.

    An ``OSError`` caused this, but a catalog that cannot be created is not something any of
    those blocks should quietly treat as one more unreadable path.
    """
    assert not issubclass(CatalogUnwritableError, OSError)


def test_the_backstop_says_nothing_a_command_that_wrote_nothing_would_contradict(
    tmp_path: Path,
) -> None:
    """⚠ The §9 half of `(aen)`, and it was introduced by the fix for `(afe)`.

    The first version said the command "stopped rather than continue without recording what it
    did" and sent the reader to ``rescan``. On ``truestill status`` - which writes nothing - both
    describe work that never happened. This function is the **backstop**: reached from any
    command, and it cannot know whether anything was written, so it may not assert that anything
    was.
    """
    # A real SQLite refusal, not a hand-built one: a constructed exception carries no
    # `sqlite_errorname`, so a test using one would agree with an implementation that lost the
    # diagnostic entirely.
    with pytest.raises(sqlite3.Error) as caught:
        sqlite3.connect(tmp_path / "no" / "such" / "dir" / "c.sqlite")
    assert caught.value.sqlite_errorname == "SQLITE_CANTOPEN"
    message = catalog_unwritable_message(caught.value)

    assert "what it did" not in message
    assert "without recording" not in message
    # `rescan` stays, but offered against a condition the reader checks rather than asserted.
    assert "rescan" in message
    assert "If a run was interrupted" in message
    # And it still says the two things that are true whatever the command was.
    assert "could not write to the library catalog" in message
    assert "SQLITE_CANTOPEN" in message


def test_a_failure_that_never_reached_sqlite_still_carries_a_diagnostic(tmp_path: Path) -> None:
    """An errno name where a SQLite name would be: a bug report stays actionable either way."""
    cause = PermissionError(13, "Permission denied")
    exc = CatalogUnwritableError(cause, tmp_path / "nowhere")
    assert "Diagnostic: EACCES." in catalog_unwritable_message(exc)


def test_a_catalog_in_a_writable_place_is_unaffected(tmp_path: Path) -> None:
    """The control: the guard must not make an ordinary open harder."""
    catalog = Catalog(tmp_path / "fresh" / "catalog.sqlite")
    assert catalog.path.parent.is_dir()
    catalog.close()
