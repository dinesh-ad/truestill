"""`(ady)`: the catalog is copied before the migration chain runs.

Every assertion here is on a property the copy PROMISES, never on a file existing - a file at
the right path with a plausible size is exactly what a torn copy leaves, which is the residue
`_discard` exists for.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest
import truestill_core.catalog as catalog_module
from truestill_core import catalog_backup
from truestill_core.app_paths import backup_path_for
from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog

#: The message a torn write raises with, named so the double does not inline a literal.
_TORN = "disk I/O error"


def _behind(path: Path, version: int = CURRENT_SCHEMA_VERSION - 1) -> Path:
    """A real, current catalog rewound to an older ``user_version`` so a chain will run."""
    with Catalog(path):
        pass
    con = sqlite3.connect(path)
    con.execute(f"PRAGMA user_version = {version}")
    con.execute(
        "INSERT INTO settings (key, value) VALUES ('probe', 'before-the-upgrade') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    con.commit()
    con.close()
    return path


def _read(path: Path) -> tuple[int, str | None]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        version = int(con.execute("PRAGMA user_version").fetchone()[0])
        row = con.execute("SELECT value FROM settings WHERE key = 'probe'").fetchone()
        return version, None if row is None else str(row[0])
    finally:
        con.close()


def test_a_migrating_open_leaves_a_usable_copy_of_the_pre_upgrade_schema(tmp_path: Path) -> None:
    """The whole entry, as one assertion: the copy opens, and it is the OLD schema.

    Asserting the file exists would pass against a truncated one; asserting its ``user_version``
    is the pre-migration number cannot.
    """
    db = _behind(tmp_path / "catalog.sqlite")

    with Catalog(db) as catalog:
        outcome = catalog.pre_migration_backup
        upgraded = catalog.schema_version

    assert outcome is not None
    assert outcome.taken, outcome.error
    assert upgraded == CURRENT_SCHEMA_VERSION
    version, probe = _read(backup_path_for(db))
    assert version == CURRENT_SCHEMA_VERSION - 1
    assert probe == "before-the-upgrade"


def test_a_fresh_catalog_copies_nothing(tmp_path: Path) -> None:
    """`fresh` returns before the copy, so a first run pays nothing for it."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db) as catalog:
        assert catalog.pre_migration_backup is None
    assert not backup_path_for(db).exists()


def test_an_already_current_catalog_copies_nothing(tmp_path: Path) -> None:
    """The common case by far - every open after the upgrade - must not re-copy."""
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    with Catalog(db) as catalog:
        assert catalog.pre_migration_backup is None
    assert not backup_path_for(db).exists()


def test_the_copy_is_superseded_rather_than_accumulating(tmp_path: Path) -> None:
    """One copy per catalog. Two upgrades leave one file, holding the SECOND one's source."""
    db = _behind(tmp_path / "catalog.sqlite", CURRENT_SCHEMA_VERSION - 2)
    with Catalog(db):
        pass
    _behind(db, CURRENT_SCHEMA_VERSION - 1)
    with Catalog(db):
        pass

    siblings = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("catalog"))
    assert siblings == ["catalog.pre-upgrade.sqlite", "catalog.sqlite"], siblings
    assert _read(backup_path_for(db))[0] == CURRENT_SCHEMA_VERSION - 1


def test_a_copy_that_cannot_be_taken_does_not_stop_the_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Degrade and say why. A catalog whose safety copy failed must still open.

    Asserts BOTH halves: the migration completed, and the failure was reported rather than
    swallowed - "it opened" alone would pass against a copy that silently did nothing.
    """
    db = _behind(tmp_path / "catalog.sqlite")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(catalog_backup, "_copy", refuse)

    with Catalog(db) as catalog:
        outcome = catalog.pre_migration_backup
        upgraded = catalog.schema_version

    assert upgraded == CURRENT_SCHEMA_VERSION
    assert outcome is not None
    assert not outcome.taken
    assert "No space left on device" in outcome.error
    assert not backup_path_for(db).exists()


def test_a_partial_copy_never_takes_the_real_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The staged file absorbs the residue. `(adr)` cross-reference, and M1/M2's real finding.

    A write failure part-way leaves a file of PLAUSIBLE SIZE that opens as unreadable - not an
    empty one - so `(adr)`'s zero-byte discriminator would not catch it. This proves it never
    reaches the name a person would restore from.
    """
    db = _behind(tmp_path / "catalog.sqlite")
    real = backup_path_for(db)

    def half_write(_source: sqlite3.Connection, staged: Path, _deadline: float) -> None:
        # A PLAUSIBLE size with a real header, which is what a torn backup actually leaves -
        # not an empty file. `(adr)`'s zero-byte discriminator does not see this.
        staged.write_bytes(b"SQLite format 3\x00" + b"\x00" * 4096)
        raise sqlite3.OperationalError(_TORN)

    monkeypatch.setattr(catalog_backup, "_copy", half_write)

    with Catalog(db) as catalog:
        assert catalog.pre_migration_backup is not None
        assert not catalog.pre_migration_backup.taken

    assert not real.exists(), "a torn copy took the name a person would restore from"
    leftovers = [p.name for p in tmp_path.iterdir() if ".partial" in p.name]
    assert leftovers == [], leftovers


def test_the_copy_is_taken_outside_a_write_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ M7: `Connection.backup` HANGS FOREVER when its source connection holds a write
    transaction - it does not raise, so nothing would ever go red for this.

    The guard is therefore on the PRECONDITION rather than on the symptom: a test that waited
    for the hang would hang the suite, which is the twenty-seventh member's "make it executable"
    applied to something whose failure mode is silence.
    """
    db = _behind(tmp_path / "catalog.sqlite")
    seen: list[bool] = []
    real = catalog_backup.copy_before_migration

    def spy(source: sqlite3.Connection, path: Path) -> catalog_backup.BackupOutcome:
        seen.append(source.in_transaction)
        return real(source, path)

    # Patched on the module that DEFINES it, which is also the module `catalog` reaches it
    # through (`catalog_backup.copy_before_migration(...)`, an attribute lookup at call time).
    # §4's third member: a patch aimed at a re-export would stop being connected the moment the
    # call site changed, and would report success either way.
    monkeypatch.setattr(catalog_backup, "copy_before_migration", spy)
    with Catalog(db):
        pass

    assert seen == [False], f"the copy ran inside a write transaction: {seen}"


def test_a_busy_source_is_bounded_rather_than_waited_on_forever(tmp_path: Path) -> None:
    """The deadline is the only thing between a contended catalog and a launch that never ends.

    Driven directly against a permanently-BUSY source, because that state cannot be produced
    through `Catalog` without hanging the suite. The assertion is that it RETURNS.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    source = sqlite3.connect(str(db))
    source.execute("BEGIN IMMEDIATE")  # the exact state that hangs forever
    started = time.monotonic()
    try:
        outcome = catalog_backup.copy_before_migration(source, db, deadline_seconds=0.5)
    finally:
        elapsed = time.monotonic() - started
        source.close()

    assert not outcome.taken
    assert "busy" in outcome.error
    assert elapsed < 10.0, f"the deadline did not bound it ({elapsed:.1f}s)"
    assert not backup_path_for(db).exists()


def test_a_single_step_is_what_makes_the_copy_immune_to_a_concurrent_writer() -> None:
    """⚠ Pins :data:`catalog_backup.SINGLE_STEP` as a VALUE, because chunking it for progress
    reporting is the obvious, reasonable change that breaks it.

    Measured: at ``pages=64`` under a 376 writes/sec external writer, a 123 MB copy committed
    **no page in 300 s**. There is no cheap test for "never finishes", so this asserts the
    constant that avoids it and carries the measurement to whoever changes it.
    """
    assert catalog_backup.SINGLE_STEP == -1, (
        "a positive `pages` makes the backup incremental, and an incremental backup is restarted "
        "by any write from another connection - measured never to finish under a concurrent "
        "writer. See catalog_backup.SINGLE_STEP."
    )


def test_the_copy_never_fires_on_a_catalog_already_at_the_current_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(afv)`: the copy is gated on a chain existing, not on the catalog being non-fresh.

    ⚠ **`fresh` is not the same condition, and the gap is only reachable by racing.**
    `_migrate`'s fast path reads the version **outside** the lock, so an opener can see a behind
    version there, re-read the current one under the lock, find `fresh` false - and arrive at the
    copy with **zero** steps to apply. Four of six concurrent openers did exactly that, and those
    copies are what took `(adl)`'s backward-stamp defect from 7/40 rounds to 28/40.

    ⚠ **THE INTERLEAVE IS CONSTRUCTED, NOT SAMPLED, AND THE FIRST VERSION SAMPLED.** It ran six
    natural openers and asserted that at least one copied - which is a claim about a race, and a
    race is what CPU load perturbs: it went red exactly once, while the browser lane was competing
    for cores, and would not reproduce in 27 attempts afterwards. A guard whose power depends on
    scheduling is one that reports on the machine rather than on the code. So the late opener is
    held at its fast-path read until the other has finished the chain, and one run decides it.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    con = sqlite3.connect(db)
    con.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION - 3}")
    con.commit()
    con.close()

    versions_at_copy: list[int] = []
    real_copy = catalog_backup.copy_before_migration
    real_refuse = catalog_module._refuse_if_newer
    late_thread: dict[str, int] = {}
    late_is_waiting = threading.Event()
    chain_finished = threading.Event()

    def spy(source: sqlite3.Connection, path: Path) -> catalog_backup.BackupOutcome:
        versions_at_copy.append(int(source.execute("PRAGMA user_version").fetchone()[0]))
        return real_copy(source, path)

    def held(version: int) -> None:
        # `_refuse_if_newer` is called immediately after the fast path's UNLOCKED read, which is
        # the one instant where an opener has seen a behind version and not yet taken the lock.
        if threading.get_ident() == late_thread.get("id") and not late_is_waiting.is_set():
            late_is_waiting.set()
            chain_finished.wait(timeout=20)
        real_refuse(version)

    monkeypatch.setattr(catalog_backup, "copy_before_migration", spy)
    monkeypatch.setattr(catalog_module, "_refuse_if_newer", held)

    def opener() -> None:
        with Catalog(db):
            pass

    def late() -> None:
        late_thread["id"] = threading.get_ident()
        opener()

    slow = threading.Thread(target=late)
    slow.start()
    assert late_is_waiting.wait(timeout=20), "the late opener never reached its fast-path read"
    fast = threading.Thread(target=opener)
    fast.start()
    fast.join(timeout=30)
    chain_finished.set()
    slow.join(timeout=30)

    assert versions_at_copy, "no opener took a copy, so the gate was never exercised"
    already_current = [v for v in versions_at_copy if v >= CURRENT_SCHEMA_VERSION]
    assert not already_current, (
        f"a copy was taken on a catalog already at the current version: {versions_at_copy}. "
        "The copy must be gated on `version < CURRENT_SCHEMA_VERSION`, not on `fresh` - the fast "
        "path's read is outside the lock, so an opener can arrive here with nothing to migrate."
    )
