"""An open that will change nothing does not take the write lock. `(adu)`

**What this guards and why it is not the other test's job.**
`test_two_openers_build_the_schema_once` guards the *correctness* half - that the fast path can
only ever decide to SKIP, never to act - and it catches a fast path that acts on its unlocked read
because that is `§5.4`'s original defect wearing a new shape. It cannot see whether the fast path
exists at all: deleting it entirely leaves that test green, because taking the lock always was
correct. **This file is the other half**: the lock is *not* taken when nothing will be written.

**Why that is worth a guard rather than a comment.** The lock protects exactly one state - two
openers both building a fresh schema - and measurement says that state happens **once per catalog
in the life of a library**: with `BEGIN IMMEDIATE` removed, a fresh catalog immediately shows two
builders and an already-migrated one shows nothing wrong at all, because its migrate transaction
writes nothing (`total_changes` 0, file byte-identical, no journal). `PERFORMANCE.md` §5.6.

**Asserted on the statement, not on a timing.** A performance assertion here would be a flake on a
loaded machine; whether `BEGIN IMMEDIATE` was executed is a fact. `set_trace_callback` fires once
per statement, so no seam is added to `Catalog` for this - a seam that exists only for a test is
one that drifts from the code it claims to cover.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog, CatalogVersionError


def _statements(db: Path) -> list[str]:
    """Every statement one `Catalog(db)` open executes, flattened."""
    real_connect = sqlite3.connect
    seen: list[str] = []

    def traced(*args: object, **kwargs: object) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)  # type: ignore[arg-type]
        conn.set_trace_callback(lambda s: seen.append(" ".join(s.split()).upper()))
        return conn

    with patch.object(sqlite3, "connect", traced), Catalog(db):
        pass
    return seen


def _took_the_lock(db: Path) -> bool:
    return any(s.startswith("BEGIN IMMEDIATE") for s in _statements(db))


def test_a_fresh_catalog_takes_the_write_lock(tmp_path: Path) -> None:
    """The cry-wolf guard. If the trace never matched, every assertion below would pass for the
    wrong reason - a fast path that is never exercised looks identical to one that always is."""
    assert _took_the_lock(tmp_path / "catalog.sqlite"), (
        "a fresh catalog did not take the write lock, so either the trace stopped matching or "
        "the one state the lock exists for is now unprotected"
    )


def test_an_already_current_catalog_does_not_take_the_write_lock(tmp_path: Path) -> None:
    """THE GUARD. Deleting the fast path leaves every other test in the suite green."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass

    assert not _took_the_lock(db), (
        "an open that will change nothing still took the write lock. That is what `(adu)` "
        "removed: it is paid on every open to protect a state - two openers both building a "
        "fresh schema - that happens once per catalog and cannot recur."
    )


def test_a_catalog_behind_the_current_version_still_takes_it(tmp_path: Path) -> None:
    """The fall-through. A fast path that skipped here would silently not migrate."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    behind = sqlite3.connect(str(db))
    behind.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION - 1}")
    behind.commit()
    behind.close()

    assert _took_the_lock(db)
    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION


def test_a_stamped_but_unbuilt_catalog_still_takes_it(tmp_path: Path) -> None:
    """Both halves of the fast path's condition are load-bearing.

    A file carrying the current `user_version` with no `files` table is not a state Truestill
    creates, but keying the skip on the version ALONE would adopt it as current and hand back a
    catalog with no schema. The table check is what refuses that, and a mutation dropping it
    fails here and nowhere else.
    """
    db = tmp_path / "catalog.sqlite"
    stamped = sqlite3.connect(str(db))
    stamped.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
    stamped.commit()
    stamped.close()

    assert _took_the_lock(db)
    with Catalog(db) as catalog:
        assert catalog.count() == 0  # the schema exists, so this is a query rather than an error


def test_a_newer_catalog_is_refused_before_any_transaction_opens(tmp_path: Path) -> None:
    """`_refuse_if_newer` runs on the fast path, not only under the lock.

    A catalog from a newer Truestill must be refused before anything opens a write transaction
    against it - refusing after would take the lock on a file this version must not touch.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    newer = sqlite3.connect(str(db))
    newer.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
    newer.commit()
    newer.close()

    seen: list[str] = []
    real_connect = sqlite3.connect

    def traced(*args: object, **kwargs: object) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)  # type: ignore[arg-type]
        conn.set_trace_callback(lambda s: seen.append(" ".join(s.split()).upper()))
        return conn

    with patch.object(sqlite3, "connect", traced), pytest.raises(CatalogVersionError):
        Catalog(db)

    assert not any(s.startswith("BEGIN IMMEDIATE") for s in seen), (
        "the refusal happened, but only after a write transaction was opened against a catalog "
        f"this version must not touch. Statements executed: {seen}"
    )
