"""O4: a confirmation survives every whole-disk operation (date-provenance step 3).

`BACKLOG.md` (ii)'s finding, in its own words: *"A hand-move is undone by the next whole-disk
operation ... The user's correction is not merely forgotten - it is actively reverted, which is
worse than not supporting it."* So the obligation is not "confirmations are stored"; it is that
each operation which rewrites the library leaves them standing. Each is tested by name below.

**The fixtures are deliberately messy.** Step 2 measured the real library at 598/600 clean EXIF
via ``DateTimeOriginal`` - which means the tiers that most need rescuing are precisely the ones
that corpus barely contains. Sampling it would have produced fixtures that never exercise the
feature. These are built the other way round: a messenger filename, a filename-only date, an
undated file, and a video whose UTC clock was shifted.

**No baking here.** Step 3 is catalog-only by ruling, so that a bug in it cannot cost a
correction the user already made.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.date_provenance import format_inferred_date_tag
from truestill_core.destinations import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout import DEFAULT_SCHEME, PRESETS, scheme_from_string
from truestill_core.migrate import run_migration
from truestill_core.models import DateSource

#: The date a person supplies. Chosen far from every fixture's machine-derived date so a test
#: cannot pass by coincidence - if a file lands in 2011 it did so because the confirmation won.
CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)
_UUID = "DRIVE-1"


def _messy_library(db: Path, root: Path) -> dict[str, str]:
    """Four files, each on a tier the real corpus barely produces. Returns ``{name: sha256}``.

    Every one of these is a file a user would plausibly want to rescue, and not one of them is
    the clean-EXIF case that dominates the only real library available.
    """
    rows = [
        # A messenger filename: the date is when it was forwarded, never when it was taken.
        ("IMG-20250804-WA0020.jpg", "WhatsApp", None, DateSource.NONE, None),
        # Filename-only: right most of the time, wrong exactly when a name was copied.
        ("20140820_143000_holiday.jpg", "Camera", "2014-08-20T14:30:00", DateSource.FILENAME, None),
        # Nothing at all: the Undated bucket, where a rescue is the only route out.
        ("scan-no-date.jpg", "Saved", None, DateSource.NONE, None),
        # A video whose UTC container stamp was shifted by a proven offset.
        (
            "VID_20140820_190000.mp4",
            "Camera",
            "2014-08-21T00:30:00",
            DateSource.INFERRED_LOCAL,
            format_inferred_date_tag("CreateDate", "filename:VID_", CONFIRMED - CONFIRMED),
        ),
    ]
    shas: dict[str, str] = {}
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Drive")
        for name, category, captured, source, tag in rows:
            relative = f"{category}/2014/{name}" if captured else f"{category}/Undated/{name}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"bytes-of-{name}".encode())
            sha = sha256_file(path)
            shas[name] = sha
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at=captured,
                category=category,
                relative=relative,
                drive_uuid=_UUID,
                date_source=source.value,
                date_tag=tag,
            )
    return shas


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    return db, root, _messy_library(db, root)


def _confirm(db: Path, sha: str) -> None:
    with Catalog(db) as catalog:
        catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")


def _row(db: Path, sha: str) -> sqlite3.Row | None:
    with Catalog(db) as catalog:
        return catalog.find_by_sha256(sha)


# --- the confirmation itself --------------------------------------------------------------


def test_a_confirmation_outranks_the_evidence_it_replaces(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    db, _root, shas = library
    sha = shas["20140820_143000_holiday.jpg"]
    assert _row(db, sha)["date_source"] == DateSource.FILENAME.value

    _confirm(db, sha)

    row = _row(db, sha)
    assert row["date_source"] == DateSource.HUMAN_CONFIRMED.value
    assert row["captured_at"] == CONFIRMED.isoformat()
    assert row["date_tag"] is None, "the machine's evidence no longer explains this date"


def test_confirming_an_undated_file_gives_it_a_date(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """The Undated bucket is where a rescue is the only way out - (ii)'s motivating case."""
    db, _root, shas = library
    sha = shas["scan-no-date.jpg"]
    assert _row(db, sha)["captured_at"] is None

    _confirm(db, sha)
    assert _row(db, sha)["captured_at"] == CONFIRMED.isoformat()


def test_a_person_may_change_their_mind(library: tuple[Path, Path, dict[str, str]]) -> None:
    """Cry-wolf half: the newest human answer wins, including over an older human answer."""
    db, _root, shas = library
    sha = shas["scan-no-date.jpg"]
    _confirm(db, sha)
    later = datetime(2009, 1, 2, 3, 4, 5)
    with Catalog(db) as catalog:
        catalog.confirm_date(sha, later.isoformat())
    assert _row(db, sha)["captured_at"] == later.isoformat()


def test_confirming_one_file_does_not_touch_another(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """Cry-wolf half: a confirmation is per content, not a library-wide setting."""
    db, _root, shas = library
    _confirm(db, shas["scan-no-date.jpg"])
    untouched = _row(db, shas["20140820_143000_holiday.jpg"])
    assert untouched["date_source"] == DateSource.FILENAME.value


# --- O4: it survives every whole-disk operation ---------------------------------------------


def test_o4_survives_migrate_layout(library: tuple[Path, Path, dict[str, str]]) -> None:
    """The operation (ii) names by name: migrate used to re-render a rescued file back."""
    db, root, shas = library
    sha = shas["20140820_143000_holiday.jpg"]
    _confirm(db, sha)

    with Catalog(db) as catalog:
        run_migration(catalog, LocalDestination(root), _UUID, DEFAULT_SCHEME, apply=True)

    row = _row(db, sha)
    assert row["date_source"] == DateSource.HUMAN_CONFIRMED.value
    assert row["captured_at"] == CONFIRMED.isoformat()
    with Catalog(db) as catalog:
        placed = catalog.copy_relative(sha, _UUID)
    assert placed is not None
    assert "2011" in placed, f"re-rendered by the old evidence, not the confirmation: {placed}"


def test_o4_survives_a_relayout_under_a_different_preset(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """A second migration, to a different shape. The date must not revert on the way."""
    db, root, shas = library
    sha = shas["20140820_143000_holiday.jpg"]
    _confirm(db, sha)
    other = scheme_from_string(PRESETS["year-month-event"].timeline)

    with Catalog(db) as catalog:
        run_migration(catalog, LocalDestination(root), _UUID, DEFAULT_SCHEME, apply=True)
        run_migration(catalog, LocalDestination(root), _UUID, other, apply=True)

    assert _row(db, sha)["captured_at"] == CONFIRMED.isoformat()
    with Catalog(db) as catalog:
        assert "2011" in str(catalog.copy_relative(sha, _UUID))


def test_o4_survives_forgetting_the_organized_row(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """The undo-organize case, and the reason confirmations are not a column on ``files``.

    ``forget_organized`` deletes the file row when the last copy goes - correct for the dedup
    index, fatal for a confirmation stored beside it. The user's answer must outlive the record
    of where the file happened to be sitting.
    """
    db, _root, shas = library
    sha = shas["scan-no-date.jpg"]
    _confirm(db, sha)

    with Catalog(db) as catalog:
        catalog.forget_organized(sha, _UUID)
        assert catalog.find_by_sha256(sha) is None, "the fixture must really delete the row"
        assert catalog.confirmed_date(sha) == CONFIRMED.isoformat(), (
            "undo-organize destroyed the user's confirmation"
        )


def test_o4_survives_a_reingest_of_the_same_content(
    library: tuple[Path, Path, dict[str, str]],
) -> None:
    """Re-recording the same content must not silently revert it to machine evidence.

    ``record_uploaded`` upserts on sha256 and refreshes ``date_source`` - correct for an ordinary
    re-run, and exactly the shape that would quietly overwrite a human answer.
    """
    db, _root, shas = library
    sha = shas["20140820_143000_holiday.jpg"]
    _confirm(db, sha)

    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/again.jpg",
            original_name="again.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=1,
            captured_at="2014-08-20T14:30:00",
            category="Camera",
            relative="Camera/2014/again.jpg",
            drive_uuid=_UUID,
            date_source=DateSource.FILENAME.value,
            date_tag=None,
        )
        assert catalog.confirmed_date(sha) == CONFIRMED.isoformat()

    # The table surviving is not enough, and asserting only that is how this nearly shipped
    # broken: measured, the re-ingest reverted the FILE ROW to the 2014 filename evidence while
    # the confirmation sat intact beside it - and the next migrate would have re-rendered by the
    # reverted date. What must survive is the date the library is actually filed under.
    row = _row(db, sha)
    assert row["captured_at"] == CONFIRMED.isoformat(), "a re-run reverted the human answer"
    assert row["date_source"] == DateSource.HUMAN_CONFIRMED.value
