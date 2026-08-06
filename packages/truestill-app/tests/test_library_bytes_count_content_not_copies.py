"""Backing your library up must not make it report as bigger.

`library_status` computed `bytes` as `sum(d["total_size"] for d in drives)` - the sum over every
DRIVE. One library on two drives therefore reported twice its size, and the panel said 5.2 GB
while Stats said 4.9 GB about the same 1,997 photos. The gap was 296,509,852 bytes: exactly the
backup drive.

"Your library" is the distinct content. A second copy is custody, not volume - it is what the
`places` and `single_copy` numbers beside it are for.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PIL import Image
from truestill_app import service
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker


def _photo(path: Path, seed: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), ((seed * 37) % 256, (seed * 91) % 256, (seed * 13) % 256)).save(
        path, "JPEG", quality=95
    )
    return path


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path]:
    """Three photos organized onto one drive, then backed up to a second."""
    src, a, b, db = tmp_path / "src", tmp_path / "A", tmp_path / "B", tmp_path / "c.sqlite"
    for i in range(3):
        _photo(src / f"IMG_{i}.jpg", i)
    service.organize_run(src, a, db, mode="copy")(lambda _p: None, threading.Event())
    b.mkdir()
    create_marker(b, "BackupB")
    service.backup_run(a, b, db)(lambda _p: None, threading.Event())
    return db, a


def test_a_backed_up_library_does_not_report_twice_its_size(library: tuple[Path, Path]) -> None:
    """THE DEFECT. Two drives held the same three photos and `bytes` was the sum of both."""
    db, _ = library
    status = service.library_status(db)

    with Catalog(db) as catalog:
        content = catalog.total_content_bytes()

    assert status["places"] == 2, "the fixture did not produce two drives"
    assert status["bytes"] == content, (
        f"library bytes {status['bytes']} is not the distinct content {content} - "
        "it is counting copies"
    )


def test_the_number_is_the_same_one_stats_reports(library: tuple[Path, Path]) -> None:
    """The two surfaces disagreed in front of the user; they must read one number."""
    db, _ = library

    assert service.library_status(db)["bytes"] == service.library_stats(db)["safety"]["total_size"]


def test_a_single_drive_library_is_unchanged(tmp_path: Path) -> None:
    """CRY-WOLF HALF: with one drive the old sum was already right, so the fix must not move it."""
    src, a, db = tmp_path / "src", tmp_path / "A", tmp_path / "c.sqlite"
    for i in range(3):
        _photo(src / f"IMG_{i}.jpg", i)
    service.organize_run(src, a, db, mode="copy")(lambda _p: None, threading.Event())

    status = service.library_status(db)
    with Catalog(db) as catalog:
        assert status["bytes"] == catalog.total_content_bytes()
    assert status["bytes"] > 0, "the fixture organized nothing"


def test_an_empty_catalog_reports_no_bytes(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.total_content_bytes() == 0
