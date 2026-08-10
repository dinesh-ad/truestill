"""The custody claim carries the date it was last checked - `(abg)` Stage 0.

**The defect this closes is not a wrong number, it is a number with no age.** `library_status`
counts `file_copies` rows and never consults `last_verified`, though the column exists on both
`drives` and `file_copies` and is already shown per drive. So *"kept in N places"* appears with
nothing beside it, and it is a claim the system cannot back: a row is a true statement about the
moment it was written, read as a true statement about now.

**Nothing here looks at a disk.** The dates come from the `catalog.list_drives()` call
`library_status` already makes, so this is carrying data that exists to the place the claim is
made - not new tracking, and not a new query.

**Freshness is reported ALWAYS, never only when it is bad.** Showing a date only once it is stale
teaches a reader that its absence means fresh, which is the same defect one level up. A date that
only gets older cannot mislead; a silence can.

**Why one never-checked drive removes the date entirely.** A claim is only as fresh as its
weakest leg. If two places hold the library and one has never been looked at, there is no date
the sentence *"in 2 places, last checked X"* could honestly carry - so the date is absent and the
drive is named instead. Naming it matters: the name is the only clue to what happened.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app import service
from truestill_core.catalog import Catalog


def _seed(db: Path, drives: dict[str, str | None], *, files: int = 2) -> None:
    """A catalog with one copy of each file on every named drive.

    `drives` maps label -> `last_verified` ISO string, or None for a drive never checked.
    """
    with Catalog(db) as catalog:
        for index, (label, verified) in enumerate(drives.items()):
            uuid = f"D{index}"
            catalog.upsert_drive(uuid=uuid, label=label)
            for n in range(files):
                catalog.record_uploaded(
                    source_path=f"/src/{n}.jpg",
                    original_name=f"{n}.jpg",
                    sha256=f"sha{n}",
                    copy_sha256=f"sha{n}",
                    perceptual=None,
                    size=10,
                    captured_at=None,
                    category="Camera",
                    relative=f"Camera/{n}.jpg",
                    drive_uuid=uuid,
                )
            if verified is not None:
                catalog.set_drive_verified(uuid, verified)


def test_the_claim_carries_the_oldest_check_across_the_places_it_counts(tmp_path: Path) -> None:
    """The OLDEST, not the newest. "In 2 places, last checked yesterday" would be false when one
    of the two was last looked at a year ago - the reassurance is bounded by the weaker leg."""
    db = tmp_path / "c.sqlite"
    _seed(db, {"Cabinet": "2026-07-28T13:00:00+00:00", "Output": "2026-08-01T09:00:00+00:00"})

    status = service.library_status(db)

    assert status["custody_checked_at"] == "2026-07-28T13:00:00+00:00"
    assert status["never_checked_drives"] == []


def test_one_never_checked_place_removes_the_date_and_names_the_drive(tmp_path: Path) -> None:
    """The Morrowkeep shape, from the real catalog: a drive holding 395 copies and never verified.

    No date is offered, because none would be true of the whole claim, and the drive is named.
    """
    db = tmp_path / "c.sqlite"
    _seed(db, {"Cabinet": "2026-07-28T13:00:00+00:00", "Morrowkeep": None})

    status = service.library_status(db)

    assert status["custody_checked_at"] is None
    assert status["never_checked_drives"] == ["Morrowkeep"]


def test_a_drive_holding_nothing_does_not_drag_the_date_down(tmp_path: Path) -> None:
    """A registered drive with no copies is not one of the places the claim is about, so it can
    neither supply the date nor withhold it. `library_status` already filters on `file_count`;
    this pins that the freshness read uses the same set rather than every row in `drives`."""
    db = tmp_path / "c.sqlite"
    _seed(db, {"Cabinet": "2026-07-28T13:00:00+00:00"})
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="EMPTY", label="Spare, never used")

    status = service.library_status(db)

    assert status["custody_checked_at"] == "2026-07-28T13:00:00+00:00"
    assert status["never_checked_drives"] == []


def test_a_library_with_no_places_offers_no_date_and_names_nobody(tmp_path: Path) -> None:
    """An honest zero. Nothing to stand behind, and nothing to apologise for either."""
    db = tmp_path / "c.sqlite"
    with Catalog(db):
        pass

    status = service.library_status(db)

    assert status["custody_checked_at"] is None
    assert status["never_checked_drives"] == []
