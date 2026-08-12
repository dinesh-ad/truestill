"""Camera and GPS metadata is kept, not read once and thrown away (`BACKLOG.md` ``(kk)``).

Both halves were the same defect: the tags are read during an organize run, used for the
categorisation decision and the trip jump-cut, and then never written anywhere durable. Measured
before building - a photo stamped with distinctive device strings left **zero** trace in the
catalog, and 2,238 of 2,300 files in the real corpus (97%) had gone through that path.

**No new exiftool tag is requested**, so `tags_fingerprint` is unchanged and no cached metadata
is invalidated: `Make`, `Model`, `LensModel` were already requested for categorisation, and
`GPSLatitude` / `GPSLongitude` already for the event jump-cut. This is a column, not a pass.
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import (
    _MIGRATIONS,
    CURRENT_SCHEMA_VERSION,
    Catalog,
    _add_capture_columns,
)
from truestill_core.exif import _NUMERIC_TAGS, REQUESTED_TAGS, tags_fingerprint

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _photo(path: Path, *, gps: tuple[float, float] | None, device: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "navy").save(path, "JPEG")
    args = ["exiftool", "-overwrite_original", "-q", "-m", "-DateTimeOriginal=2026:05:01 10:00:00"]
    if device:
        args += ["-Make=TestCam", "-Model=X100", "-LensModel=TestLens 23mm"]
    if gps is not None:
        lat, lon = gps
        args += [
            f"-GPSLatitude={abs(lat)}",
            f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
            f"-GPSLongitude={abs(lon)}",
            f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
        ]
    subprocess.run([*args, str(path)], check=True)


def _organize(src: Path, dest: Path, db: Path) -> None:
    assert main(["organize", str(src), str(dest), "--apply", "--db", str(db)]) == 0


def _row(db: Path) -> dict[str, object]:
    with Catalog(db) as catalog:
        rows = catalog._conn.execute("SELECT * FROM files").fetchall()
    assert len(rows) == 1, f"fixture expects one file, got {len(rows)}"
    return dict(rows[0])


def test_the_device_that_took_the_photo_is_kept(tmp_path: Path) -> None:
    """The reported defect: read for the Camera decision, then discarded."""
    src = tmp_path / "src"
    _photo(src / "IMG_0001.jpg", gps=(48.8584, 2.2945))
    _organize(src, tmp_path / "out", tmp_path / "c.sqlite")

    row = _row(tmp_path / "c.sqlite")

    assert row["camera_make"] == "TestCam"
    assert row["camera_model"] == "X100"
    assert row["lens_model"] == "TestLens 23mm"


def test_coordinates_are_kept_with_their_sign(tmp_path: Path) -> None:
    """Southern and western hemispheres. Getting the sign wrong puts a photo on the wrong side
    of the planet, and exiftool's ``#`` suffix is what makes the value signed - verified, not
    assumed."""
    src = tmp_path / "src"
    _photo(src / "IMG_0001.jpg", gps=(-33.8688, -151.2093))
    _organize(src, tmp_path / "out", tmp_path / "c.sqlite")

    row = _row(tmp_path / "c.sqlite")

    assert row["gps_latitude"] == pytest.approx(-33.8688)
    assert row["gps_longitude"] == pytest.approx(-151.2093)


def test_null_island_is_stored_as_zero_and_not_as_missing(tmp_path: Path) -> None:
    """The truthiness trap, and the reason `isinstance` is used instead of `if lat:`.

    exiftool returns integer ``0`` for a photo at 0N 0E, which is **falsy**. A plain ``if lat:``
    drops it, and the row then claims the photo has no location at all - the overloaded-sentinel
    family this repo already paid for once in `(aac)`.
    """
    src = tmp_path / "src"
    _photo(src / "IMG_0001.jpg", gps=(0.0, 0.0))
    _organize(src, tmp_path / "out", tmp_path / "c.sqlite")

    row = _row(tmp_path / "c.sqlite")

    assert row["gps_latitude"] == 0.0
    assert row["gps_longitude"] == 0.0
    assert row["gps_latitude"] is not None, "0.0 is a location; NULL means we do not have one"


def test_a_photo_with_no_gps_is_null_and_distinguishable_from_null_island(
    tmp_path: Path,
) -> None:
    """Absent and 0,0 must be two different answers, in SQL as well as in Python."""
    src = tmp_path / "src"
    _photo(src / "IMG_0001.jpg", gps=None)
    db = tmp_path / "c.sqlite"
    _organize(src, tmp_path / "out", db)

    row = _row(db)
    assert row["gps_latitude"] is None
    assert row["gps_longitude"] is None

    with Catalog(db) as catalog:
        located = catalog._conn.execute(
            "SELECT COUNT(*) FROM files WHERE gps_latitude IS NOT NULL"
        ).fetchone()[0]
    assert located == 0, "a NULL row must not answer a 'has a location' query"


def test_a_file_with_no_device_stores_null_and_categorises_as_before(tmp_path: Path) -> None:
    """Cry-wolf half. Absence of Make/Model is itself a signal (`categorize.py`), and the
    columns must not invent a value for it or change where the file lands."""
    src = tmp_path / "src"
    _photo(src / "screenshot.jpg", gps=None, device=False)
    _organize(src, tmp_path / "out", tmp_path / "c.sqlite")

    row = _row(tmp_path / "c.sqlite")

    assert row["camera_make"] is None
    assert row["camera_model"] is None
    assert row["lens_model"] is None
    assert row["category"] != "Camera", "no capture metadata: the device rule must not fire"


def test_no_new_exiftool_tag_was_requested() -> None:
    """Ruling 1, made checkable rather than trusted.

    The metadata cache is keyed partly on this fingerprint, so adding any tag to the request
    invalidates every cached row and forces a cold exiftool pass over the whole library - the
    exact cost profile the previous commit spent itself removing. Every tag this feature stores
    was already being requested.
    """
    for tag in ("Make", "Model", "LensModel"):
        assert tag in REQUESTED_TAGS
    for tag in ("GPSLatitude", "GPSLongitude"):
        assert tag in _NUMERIC_TAGS
    assert "GPSAltitude" not in REQUESTED_TAGS
    assert "GPSAltitude" not in _NUMERIC_TAGS
    # CHANGED ONCE, DELIBERATELY, 2026-08-12 - `efc0b42a315be9a9` -> `cff9bb9b374bc122` by adding
    # `RIFF:DateCreated` for `(acm)`. This assertion did its job: the addition tripped it, and the
    # cost was weighed rather than discovered later.
    #
    # **What it costs:** every cached metadata row is invalidated once, so the next run per library
    # pays a cold exiftool pass - ~2.2 ms/file measured (`PERFORMANCE.md`), so ~5 s on the
    # 2,275-file reference library. One time, per library, at upgrade.
    #
    # **What it buys:** of the two AVIs across both sample corpora, **one carries a date in RIFF
    # `DateCreated` and nowhere else** and was landing in `Undated/`. The rate is per-AVI, not
    # one-in-1,322 files, which is what turned this from a curiosity into a format that half-fails.
    #
    # Scoped to `RIFF:` on purpose - a bare `DateCreated` is an IPTC field on stills meaning
    # something else, and the corpora hold malformed ones (`2010:00:00`).
    assert tags_fingerprint(REQUESTED_TAGS, _NUMERIC_TAGS) == "cff9bb9b374bc122", (
        "the requested tag set changed; every cached metadata row is now invalid and the next "
        "run pays a full cold exiftool pass. That may be right, but it is never incidental"
    )


def test_the_schema_version_moved_with_the_columns() -> None:
    """Anti-vacuity: columns added without a version bump leave older databases unupgraded.

    Asserts the capture columns arrived AT v17, not that v17 is the newest version. The original
    wrote `== 17` when 17 happened to be the latest, so the next migration failed a test about a
    change it had not touched.
    """
    assert dict(_MIGRATIONS)[17] is _add_capture_columns
    assert CURRENT_SCHEMA_VERSION >= 17


def test_a_v16_catalog_upgrades_and_its_existing_rows_survive_as_null(tmp_path: Path) -> None:
    """The migration, on a database that predates the columns.

    An existing row must come through with NULLs rather than blocking the upgrade or being
    invented for - there is no backfill, deliberately: recovering the values means re-reading
    the file, which is a decision of its own and not something a schema migration does quietly.
    """
    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL, relative TEXT NOT NULL, upload_status TEXT NOT NULL,
            processed_at TEXT NOT NULL
        );
        INSERT INTO files (source_path, sha256, category, relative, upload_status, processed_at)
        VALUES ('/old/a.jpg', 'sha-a', 'Camera', 'Camera/a.jpg', 'uploaded', '2026-01-01');
        PRAGMA user_version = 16;
        """
    )
    conn.commit()
    conn.close()

    with Catalog(db) as catalog:
        version = int(catalog._conn.execute("PRAGMA user_version").fetchone()[0])
        row = dict(catalog._conn.execute("SELECT * FROM files").fetchone())

    # The point is that a v16 file is brought fully current, whatever current is today.
    assert version == CURRENT_SCHEMA_VERSION
    assert row["sha256"] == "sha-a", "the pre-existing row must survive the upgrade"
    for column in ("camera_make", "camera_model", "lens_model", "gps_latitude", "gps_longitude"):
        assert row[column] is None


def test_the_migration_is_idempotent_on_a_catalog_that_already_has_the_columns() -> None:
    """`_columns_of` guards each ADD COLUMN; running it twice must not raise."""
    with contextlib.closing(sqlite3.connect(":memory:")) as conn:
        # `_columns_of` reads rows by name, as `Catalog` configures.
        conn.row_factory = sqlite3.Row
        conn.executescript("CREATE TABLE files (id INTEGER PRIMARY KEY); PRAGMA user_version = 16;")
        _add_capture_columns(conn)
        _add_capture_columns(conn)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(files)")}

    assert {"camera_make", "gps_latitude"} <= columns
