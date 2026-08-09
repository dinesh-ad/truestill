"""The trigger: a catalog opened by a surface saves its decisions when it closes.

**The flag is "wrote anything", not "wrote a decision", and that is deliberate.** Classifying
writes means maintaining a list of which ones count, and the day someone adds a decision table and
forgets the list, the save goes quiet with nothing saying so. `organize` and `rescan` refreshing
the document is not a cost: the refreshed stamp is what the staleness line reads.

**Tests keep using bare `Catalog(...)`, so no test can ever fire a drive write.** That is not
carefulness, it is the shape of the design - §4 asks for impossible rather than unlikely, and this
one came out that way rather than being remembered.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Self

import pytest
from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog
from truestill_core.decisions import (
    DECISIONS_NAME,
    DECISIONS_SAVED_AT_KEY,
    DriveSave,
    SaveOutcome,
)
from truestill_core.drive import DriveMarker, drive_path_hint, write_marker

_UUID = "19411f16-8a00-4873-9b32-04c595eebbe1"


class _CommandError(Exception):
    """A command blowing up part way through, as commands do."""


def _drive(catalog: Catalog, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_marker(root, DriveMarker(uuid=_UUID, label="Output", created="2026-01-01T00:00:00+00:00"))
    catalog.upsert_drive(uuid=_UUID, label="Output")
    catalog.set_setting(drive_path_hint(_UUID), str(root))
    return root


def _already_upgraded(catalog: Catalog) -> None:
    """Take the upgrade write out of the picture, so a test can see the ordinary trigger alone."""
    catalog.set_setting(DECISIONS_SAVED_AT_KEY, "2026-08-01T00:00:00+00:00")


class _Renames:
    """Counts atomic replaces, which is one per document actually written."""

    def __init__(self) -> None:
        self.count = 0

    def __enter__(self) -> Self:
        self._real = Path.replace

        def watch(inner: Path, target: object) -> object:
            if inner.name.startswith(DECISIONS_NAME):
                self.count += 1
            return self._real(inner, target)  # type: ignore[arg-type]

        Path.replace = watch  # type: ignore[assignment,method-assign]
        return self

    def __exit__(self, *_: object) -> None:
        Path.replace = self._real  # type: ignore[method-assign]


def test_a_command_that_changed_nothing_writes_nothing(tmp_path: Path) -> None:
    """A read-only command must not touch a drive. The flag is the whole cost: no drives are
    queried, no marker is read, nothing is stat-ed."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)

    with _Renames() as renames, open_catalog(db) as catalog:
        catalog.count()  # a read, the ordinary shape of `status` or `where`

    assert renames.count == 0
    assert not (root / DECISIONS_NAME).exists()


def test_a_command_that_wrote_saves_exactly_once_per_drive(tmp_path: Path) -> None:
    """ONE COMMAND, ONE WRITE. The save records its own outcome through the catalog, which sets
    the same flag it just acted on - harmless today, a loop the day someone moves the fire point.
    The flag is cleared after the save for that reason, and this is what pins it."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)

    with _Renames() as renames, open_catalog(db) as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-15",
            days=["2014-08-14", "2014-08-15"],
        )

    assert renames.count == 1, f"{renames.count} writes for one command"
    assert (root / DECISIONS_NAME).exists()


def test_a_command_that_failed_saves_nothing(tmp_path: Path) -> None:
    """Clean exit only. A command that raised part way through is not a moment to publish its
    catalog's state to every drive the user owns."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)

    def a_command_that_blows_up() -> None:
        with open_catalog(db) as catalog:
            catalog.record_skip("b" * 64)
            raise _CommandError

    with pytest.raises(_CommandError):
        a_command_that_blows_up()

    assert not (root / DECISIONS_NAME).exists()


def test_the_upgrade_write_happens_before_the_body_runs(tmp_path: Path) -> None:
    """EARLY, NOT LATE. A user whose first post-upgrade command is a risky one is protected
    before it, not after - and the body is what might raise."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        setup.record_skip("b" * 64)  # a decision that predates the feature

    seen: list[bool] = []
    with open_catalog(db) as catalog:
        seen.append((root / DECISIONS_NAME).exists())
        assert catalog.count() == 0

    assert seen == [True], "the upgrade write did not happen before the body"


def test_the_upgrade_write_does_not_leave_the_catalog_looking_dirty(tmp_path: Path) -> None:
    """CRY-WOLF HALF of the flag clearing. The upgrade write records itself through the catalog,
    so without a clear it would look like the body wrote and fire a second, identical save."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        setup.record_skip("b" * 64)

    with _Renames() as renames, open_catalog(db) as catalog:
        catalog.count()  # the body changes nothing

    assert renames.count == 1, f"the upgrade write fired {renames.count} times"


def test_a_transaction_that_rolled_back_does_not_count_as_a_write(tmp_path: Path) -> None:
    """A rolled-back transaction changed nothing and must not look as though it did - otherwise
    every refused write would push an identical document to every drive the user owns."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],
        )
        catalog.mark_clean()

        with pytest.raises(sqlite3.IntegrityError):
            catalog.create_trip(  # 2014-08-14 is already claimed; trip_days.day is a primary key
                name="Goa",
                slug="goa",
                start_date="2014-08-14",
                end_date="2014-08-14",
                days=["2014-08-14"],
            )

        assert not catalog.dirty, "a refused write marked the catalog as changed"


# --- failures outlive the command that produced them ---------------------------------------


def test_a_failed_save_is_recorded_where_a_surface_can_find_it(tmp_path: Path) -> None:
    """A line printed after a command is gone the moment the user scrolls, and the whole lesson
    from the Adobe threads is that a backup nobody can see is one nobody has."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)

    # A directory where the document goes, rather than a read-only drive: `chmod` on a directory
    # is a no-op on Windows, so a permission-based obstruction would leave this property proven
    # on two platforms out of three.
    (root / DECISIONS_NAME).mkdir()

    with open_catalog(db) as catalog:
        catalog.record_skip("b" * 64)

    with Catalog(db) as after:
        assert after.get_setting(f"decisions.problem.{_UUID}")


def test_a_recorded_problem_is_cleared_by_the_next_success(tmp_path: Path) -> None:
    """A stale problem is its own defect: it tells the user their decisions are not being saved
    when they are, which is the staleness failure pointed the other way."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)
        setup.set_setting(f"decisions.problem.{_UUID}", "the drive is read-only")

    with open_catalog(db) as catalog:
        catalog.record_skip("b" * 64)

    with Catalog(db) as after:
        assert not after.get_setting(f"decisions.problem.{_UUID}")


def test_the_surface_is_told_what_happened_rather_than_core_printing_it(tmp_path: Path) -> None:
    """Core owns no interaction (§2). The CLI prints the failure, the app stores it for its drive
    card, and neither is decided here - so the outcomes are handed back rather than rendered."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "drive"
    with Catalog(db) as setup:
        _drive(setup, root)
        _already_upgraded(setup)

    told: list[tuple[str, SaveOutcome, bool]] = []

    def remember(results: tuple[DriveSave, ...], *, upgrade: bool) -> None:
        told.extend((r.label, r.outcome, upgrade) for r in results)

    with open_catalog(db, report=remember) as catalog:
        catalog.record_skip("b" * 64)

    assert told == [("Output", SaveOutcome.WRITTEN, False)], (
        "the ordinary save was reported as the once-per-catalog first one"
    )
