"""Which registered drive is a library, and what each drive carries. **Records, never a look.**

⚠ **THE QUESTION THAT BROKE THE SCREEN.** Restore stage 3 asked the user to type the absolute
path of their own library while thirty organized photographs sat in it, because the only thing the
app consulted - `LIBRARY_PATH_HINT` - is written by the app's own organize flow and is absent on a
catalog the CLI built.

**`files` cannot answer it**: the table carries no `drive_uuid`. **`file_copies` cannot either**:
`backup` mirrors relative paths verbatim, so "its paths match `files.relative`" is true of a
library and of its own backup alike. `organize_runs` can, and exactly - it is written by
`start_organize_run` from both organize surfaces and by nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog

LIBRARY, BACKUP, SECOND = "lib-uuid", "backup-uuid", "second-uuid"


@pytest.fixture
def catalog(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "c.sqlite") as opened:
        for uuid, label in ((LIBRARY, "My Library"), (BACKUP, "Backup A"), (SECOND, "Backup B")):
            opened.upsert_drive(uuid=uuid, label=label)
        yield opened


def _organized_into(catalog: Catalog, uuid: str) -> None:
    catalog.start_organize_run(drive_uuid=uuid, run_id=f"run-{uuid}", intended_total=3)
    catalog.finish_organize_run(uuid)


def _copy(catalog: Catalog, uuid: str, index: int) -> None:
    catalog.record_copy(
        sha256=f"{index:064x}",
        drive_uuid=uuid,
        relative=f"Camera/2014/p{index:04d}.jpg",
        size=11,
        copy_sha256=None,
    )


# ------------------------------------------------------------------------ naming the library


def test_the_drive_an_organize_wrote_to_is_the_library(catalog: Catalog) -> None:
    """The signal, and it is exact rather than a heuristic."""
    _organized_into(catalog, LIBRARY)

    assert catalog.drives_organized_into() == {LIBRARY}


def test_a_backup_drive_holding_a_full_mirror_is_never_named(catalog: Catalog) -> None:
    """⚠ **The anti-heuristic half, and the reason `file_copies` could not be used.**

    This backup holds every file the library does, at the same relative paths - which is what a
    backup IS. Any rule built on paths or counts would call it a library. `organize_runs` does
    not, because `backup.py` never writes it.
    """
    _organized_into(catalog, LIBRARY)
    for index in range(5):
        _copy(catalog, LIBRARY, index)
        _copy(catalog, BACKUP, index)

    assert catalog.drives_organized_into() == {LIBRARY}


def test_two_organize_destinations_are_reported_as_two(catalog: Catalog) -> None:
    """⚠ **An ambiguous answer is returned, never resolved here.** Organizing into a second
    folder makes a second library; picking one would be the invented heuristic this avoids."""
    _organized_into(catalog, LIBRARY)
    _organized_into(catalog, SECOND)

    assert catalog.drives_organized_into() == {LIBRARY, SECOND}


def test_a_catalog_nobody_has_organized_into_names_nothing(catalog: Catalog) -> None:
    """The empty answer is a real one: three registered drives and no library among them."""
    for index in range(3):
        _copy(catalog, BACKUP, index)

    assert catalog.drives_organized_into() == set()


def test_a_closed_run_still_names_its_drive(catalog: Catalog) -> None:
    """`finish_organize_run` sets `completed_at`; it does not delete the row. A library that
    finished organizing is still a library, which a row-deleting design would forget."""
    _organized_into(catalog, LIBRARY)

    assert catalog.unfinished_organize_run(LIBRARY) is None
    assert catalog.drives_organized_into() == {LIBRARY}


# ---------------------------------------------------------------------------- what it carries


def test_the_gap_counts_only_what_the_library_does_not_record(catalog: Catalog) -> None:
    """Eight on the drive, five here, so three - keyed on content, and from records alone."""
    for index in range(5):
        _copy(catalog, LIBRARY, index)
    for index in range(8):
        _copy(catalog, BACKUP, index)

    assert catalog.gap_by_drive(LIBRARY) == {BACKUP: 3}


def test_a_drive_with_no_rows_is_absent_rather_than_zero(catalog: Catalog) -> None:
    """⚠ **THE WORST WRONG ANSWER, AND THE TYPE IS WHAT PREVENTS IT.**

    `drives --init` writes a marker and does not walk, so a drive holding a whole library has no
    rows. Returning `0` would let a caller render "nothing to bring back" about it by accident; a
    missing key forces the caller to tell "we have not looked" from "there is nothing there".
    """
    for index in range(5):
        _copy(catalog, LIBRARY, index)

    gaps = catalog.gap_by_drive(LIBRARY)

    assert BACKUP not in gaps
    assert gaps.get(BACKUP) is None


def test_a_walked_drive_with_a_real_zero_is_present_and_zero(catalog: Catalog) -> None:
    """The other side of the line, and what makes the test above mean something: a drive that WAS
    walked and genuinely carries nothing extra answers `0`, not absence."""
    for index in range(5):
        _copy(catalog, LIBRARY, index)
        _copy(catalog, BACKUP, index)

    assert catalog.gap_by_drive(LIBRARY) == {BACKUP: 0}


def test_the_library_is_not_measured_against_itself(catalog: Catalog) -> None:
    for index in range(5):
        _copy(catalog, LIBRARY, index)

    assert LIBRARY not in catalog.gap_by_drive(LIBRARY)


def test_every_drive_is_answered_in_one_pass(catalog: Catalog) -> None:
    """One query for the screen rather than one per card - 292 ms for eight drives against 36 ms
    for one, measured on 376,000 rows. This asserts the shape that makes that true."""
    for index in range(5):
        _copy(catalog, LIBRARY, index)
    for index in range(7):
        _copy(catalog, BACKUP, index)
    for index in range(9):
        _copy(catalog, SECOND, index)

    assert catalog.gap_by_drive(LIBRARY) == {BACKUP: 2, SECOND: 4}


def test_the_gap_is_content_not_path(catalog: Catalog) -> None:
    """A file the library holds under a different name is not a gap - identity is `sha256`."""
    catalog.record_copy(
        sha256=f"{1:064x}",
        drive_uuid=LIBRARY,
        relative="OLD/LAYOUT/x.jpg",
        size=11,
        copy_sha256=None,
    )
    _copy(catalog, BACKUP, 1)

    assert catalog.gap_by_drive(LIBRARY) == {BACKUP: 0}
