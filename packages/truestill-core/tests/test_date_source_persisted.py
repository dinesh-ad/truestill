"""``DateSource`` is persisted, not resolved and discarded (date-provenance step 1).

Every organize run already resolves *where* a date came from and then throws it away at write
time. `date-layering-gap-check.md` §5 recorded that as a structural gap - PhotoPrism keeps the
same information in a ``TakenSrc`` field - and items (n) and (ii) both need it durable. This is
that column, and nothing else: no surface, no tier, no confirmation.

Two properties are worth more than the round-trip, and both are pinned below.

**A pre-existing row keeps NULL, and NULL means "not recorded", never a guess.** A library
organized before this shipped has no retrievable provenance - the evidence chain ran months ago
against files that may since have moved. Backfilling a plausible value would make the honesty
view (n) confidently wrong about exactly the files it is least able to check, which is worse
than admitting the gap.

**The stored value is the resolver's own verdict**, not a re-derivation. Storing a second
opinion computed at write time would let the column and the placement disagree.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from truestill_core.catalog import CURRENT_SCHEMA_VERSION, Catalog
from truestill_core.categorize import build_rules
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.hashing import DEFAULT_PHASH_THRESHOLD, sha256_file
from truestill_core.models import DateSource
from truestill_core.organizer import execute, plan, resolve


def _record(catalog: Catalog, sha: str, *, source: str | None) -> None:
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
        original_name=f"{sha}.jpg",
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=10,
        captured_at=datetime(2014, 8, 20, 14, 30).isoformat(),
        category="Camera",
        relative=f"2014/2014-08/{sha}.jpg",
        date_source=source,
    )


def test_a_recorded_file_keeps_the_source_its_date_came_from(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _record(catalog, "a" * 8, source=DateSource.EXIF.value)
        _record(catalog, "b" * 8, source=DateSource.FILENAME.value)

        assert catalog.find_by_sha256("a" * 8)["date_source"] == "exif"
        assert catalog.find_by_sha256("b" * 8)["date_source"] == "filename"


def test_every_date_source_member_round_trips(tmp_path: Path) -> None:
    """The column stores the enum's own values, so a new tier needs no schema change.

    Written as a sweep rather than a sample because the next member added to `DateSource` is
    `HUMAN_CONFIRMED` (step 3), and it must land in this column without a migration.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        for i, member in enumerate(DateSource):
            sha = f"{i:064x}"
            _record(catalog, sha, source=member.value)
            assert catalog.find_by_sha256(sha)["date_source"] == member.value


def test_an_unrecorded_source_stays_null_rather_than_becoming_a_guess(tmp_path: Path) -> None:
    """NULL is a distinct, honest answer: "organized before this was recorded"."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _record(catalog, "c" * 8, source=None)
        assert catalog.find_by_sha256("c" * 8)["date_source"] is None


def test_re_recording_the_same_content_updates_the_source(tmp_path: Path) -> None:
    """``record_uploaded`` upserts on sha256; a re-run must refresh provenance with the rest.

    A stale source surviving a re-organize would make (n) describe the previous run.
    """
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _record(catalog, "d" * 8, source=DateSource.FILENAME.value)
        _record(catalog, "d" * 8, source=DateSource.EXIF.value)
        assert catalog.find_by_sha256("d" * 8)["date_source"] == "exif"


# --- migration ---------------------------------------------------------------------------


def _make_v12_catalog(path: Path) -> None:
    """A v12 catalog with one row: the shape shipped before provenance was persisted."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, original_name TEXT,
            sha256 TEXT NOT NULL UNIQUE, copy_sha256 TEXT, perceptual TEXT, size INTEGER,
            captured_at TEXT, category TEXT NOT NULL, relative TEXT NOT NULL,
            event_id INTEGER, upload_status TEXT NOT NULL, processed_at TEXT NOT NULL,
            uploaded_at TEXT
        );
        INSERT INTO files (source_path, sha256, category, relative, upload_status, processed_at)
        VALUES ('/src/legacy.jpg', 'legacy-sha', 'Camera', '2014/legacy.jpg', 'uploaded', 'then');
        PRAGMA user_version = 12;
        """
    )
    conn.commit()
    conn.close()


def test_a_v12_catalog_gains_the_column_without_losing_a_row(tmp_path: Path) -> None:
    db = tmp_path / "v12.sqlite"
    _make_v12_catalog(db)

    with Catalog(db) as catalog:
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        row = catalog.find_by_sha256("legacy-sha")
        assert row is not None, "the migration must not lose pre-existing rows"
        assert row["relative"] == "2014/legacy.jpg"
        assert row["date_source"] is None, "a legacy row's provenance is unknown, not assumed"


def test_the_migration_is_idempotent(tmp_path: Path) -> None:
    """Migrations are re-run on every open; a second pass must not fail or clobber.

    `IMPLEMENTATION_STANDARDS.md` §3 requires ordered, idempotent migrations - and this one adds
    a column, which is the shape that raises on a second ALTER if written carelessly.
    """
    db = tmp_path / "v12.sqlite"
    _make_v12_catalog(db)

    with Catalog(db) as catalog:
        _record(catalog, "e" * 8, source=DateSource.TAKEOUT.value)
    with Catalog(db) as catalog:  # re-open: _migrate runs again
        assert catalog.schema_version == CURRENT_SCHEMA_VERSION
        assert catalog.find_by_sha256("e" * 8)["date_source"] == "takeout"
        assert catalog.find_by_sha256("legacy-sha") is not None


# --- the write path actually carries it ---------------------------------------------------


def test_an_organize_run_persists_the_source_the_resolver_chose(tmp_path: Path) -> None:
    """End to end through `execute`, because a column nothing writes is not a feature.

    Uses a filename-dated file: the resolver reaches `FILENAME`, which is a tier no other part
    of this test could produce by accident, so a hardcoded default would fail here.
    """

    source = tmp_path / "src"
    source.mkdir()
    photo = source / "20140820_143000_holiday.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xdb" + b"payload")
    db = tmp_path / "c.sqlite"
    destination = tmp_path / "out"

    decisions = plan([photo], {}, build_rules())
    assert decisions[0].date_source is DateSource.FILENAME, (
        "fixture must exercise the filename tier"
    )

    with Catalog(db) as catalog:
        resolutions = resolve(decisions, DedupIndex(DEFAULT_PHASH_THRESHOLD))
        execute(resolutions, LocalDestination(destination), catalog, apply=True)
        # Looked up by content hash rather than through `organized_files`, which selects four
        # columns for the drive-attach path and must not be widened to suit a test.
        row = catalog.find_by_sha256(sha256_file(photo))
        assert row is not None, "the run must have recorded the file"
        assert row["date_source"] == DateSource.FILENAME.value
