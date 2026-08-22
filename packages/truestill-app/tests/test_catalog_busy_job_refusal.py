"""A job that meets a held catalog reports a refusal, not SQLite's own words.

Every mutating operation the app offers runs as a job, so this is the app's whole exposure to
the condition: `truestill organize --apply` in a terminal holds the catalog, the user clicks
something in the open window, and the worker thread meets the lock.

The terminal-event shape is not new -- `JobManager` already sends ``{message, code}`` and
`app.js` already renders it -- so nothing here teaches the browser a new payload. What changes
is which words arrive: ``"database is locked"`` describes SQLite's internals and no action.

The busy error is produced by a **real** second connection against a really-locked file rather
than constructed, because the discrimination under test is `sqlite_errorcode`, which the module
sets and a hand-built exception does not have. A fabricated exception would agree with an
implementation that matched on message text -- the one this must rule out.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from truestill_app.jobs import DriveRef, JobManager, JobTarget
from truestill_core.catalog_busy import CATALOG_BUSY_CODE, CATALOG_BUSY_MESSAGE

_DRIVE = DriveRef(key="uuid:A", label="Drive A")
_ORDINARY_BUG = "something else entirely"


def _terminal(mgr: JobManager, job_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    for frame in mgr.stream(job_id):
        if time.monotonic() > deadline:
            pytest.fail(f"job {job_id} did not finish within {timeout}s")
        if not frame.startswith(b"data:"):
            continue
        event: dict[str, Any] = json.loads(frame[len(b"data:") :].decode().strip())
        if event["type"] in ("done", "error"):
            return event
    pytest.fail(f"job {job_id} stream ended without a terminal event")


@pytest.fixture
def held_catalog(tmp_path: Path) -> Iterator[Path]:
    """A database file whose write lock is held for the duration of the test."""
    path = tmp_path / "catalog.sqlite"
    holder = sqlite3.connect(path, timeout=0.1)
    holder.execute("CREATE TABLE probe (x)")
    holder.commit()
    holder.execute("BEGIN IMMEDIATE")
    try:
        yield path
    finally:
        holder.rollback()
        holder.close()


def _write_from_the_worker(path: Path, statement: str) -> JobTarget:
    """A job target that opens its own connection on the worker thread, as real targets do.

    Reusing a connection made in the test thread would raise `ProgrammingError` instead --
    a different failure that would pass this test for the wrong reason.
    """

    def target(_progress: object, _cancel: threading.Event) -> dict[str, bool]:
        conn = sqlite3.connect(path, timeout=0.1)
        try:
            conn.execute(statement)
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    return target


def test_a_job_that_meets_a_held_catalog_says_what_to_do(held_catalog: Path) -> None:
    mgr = JobManager()
    job_id = mgr.start(
        _write_from_the_worker(held_catalog, "INSERT INTO probe VALUES (1)"),
        drives=[_DRIVE],
        operation="organize",
        mutating=False,
    )
    assert isinstance(job_id, str)
    event = _terminal(mgr, job_id)

    assert event["type"] == "error"
    assert event["code"] == CATALOG_BUSY_CODE
    assert event["message"] == CATALOG_BUSY_MESSAGE
    # The defect: SQLite's own sentence reaching the browser as the whole explanation.
    assert "database is locked" not in event["message"]


def test_an_ordinary_sqlite_failure_keeps_its_own_class_and_message(held_catalog: Path) -> None:
    """Cry-wolf half. A fault must not be reworded into "wait and try again".

    Same fixture, same seam, same `OperationalError` class -- only the error code differs, so
    a handler that keyed on the class or on the exception's text would fail here.
    """
    mgr = JobManager()
    job_id = mgr.start(
        _write_from_the_worker(held_catalog, "INSERT INTO no_such_table VALUES (1)"),
        drives=[_DRIVE],
        operation="organize",
        mutating=False,
    )
    assert isinstance(job_id, str)
    event = _terminal(mgr, job_id)

    assert event["type"] == "error"
    assert event["code"] == "OperationalError"
    assert "no such table" in event["message"]
    assert event["message"] != CATALOG_BUSY_MESSAGE


def test_a_non_sqlite_failure_is_untouched() -> None:
    """The broadest look-alike: the busy check must not intercept ordinary bugs."""

    def target(_progress: object, _cancel: threading.Event) -> dict[str, bool]:
        raise ValueError(_ORDINARY_BUG)

    mgr = JobManager()
    job_id = mgr.start(target, drives=[_DRIVE], operation="organize", mutating=False)
    assert isinstance(job_id, str)
    event = _terminal(mgr, job_id)

    assert event["code"] == "ValueError"
    assert event["message"] == _ORDINARY_BUG
