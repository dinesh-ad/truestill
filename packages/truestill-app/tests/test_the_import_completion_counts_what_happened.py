"""What the Import completion card is allowed to say, counted from the finished run. D17.

⚠ **`dates_from_sidecar` IS THE ROW THAT PROVES THE FEATURE WORKED**, so it is the one most worth
getting wrong in a flattering direction. Three ways it could lie, and a test for each: counting
the bake PLAN rather than what was organized, counting a file whose own EXIF was already good, and
counting a duplicate the run skipped. All three would inflate it on a real Takeout, which is full
of repeats and of files Google did write dates back into.

`already_in_library` is the library's answer where `duplicates` is this destination's. On a fresh
second drive a file is honestly both, which is `(aei)`/D14 - and a card that showed only the second
would read as *"it copied them twice"*.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import zipfile
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_app import service

#: 2014-06-05 20:26:40 UTC, as in the sibling suite. Derived there, never hand-typed.
TRUE_EPOCH = 1402000000


def _needs_exiftool() -> None:
    if shutil.which("exiftool") is None:  # pragma: no cover - a documented dependency
        pytest.skip("exiftool is not on PATH; these counts are about dates written to files")


def _photo(path: Path, colour: tuple[int, int, int], *, embedded: str = "") -> None:
    """A jpeg with no date at all, or with one already embedded."""
    Image.new("RGB", (64, 64), colour).save(path, "JPEG", quality=95)
    subprocess.run(["exiftool", "-overwrite_original", "-q", "-all=", str(path)], check=True)
    if embedded:
        subprocess.run(
            ["exiftool", "-overwrite_original", "-q", f"-DateTimeOriginal={embedded}", str(path)],
            check=True,
        )


def _sidecar(media: Path) -> None:
    (media.parent / f"{media.name}.supplemental-metadata.json").write_text(
        json.dumps({"title": media.name, "photoTakenTime": {"timestamp": str(TRUE_EPOCH)}})
    )


def _run(takeout: Path, destination: Path, db: Path) -> dict[str, Any]:
    summary = service.ingest_run(takeout, destination, db)(lambda _p: None, threading.Event())
    return dict(summary)


def test_the_rescued_date_count_is_the_number_of_files_that_got_one(tmp_path: Path) -> None:
    """Two photographs, one sidecar date each - but one already carries its own good EXIF.

    ⚠ **`ingest_context` plans a write for BOTH** (the album/description fields travel regardless),
    so a count taken from `len(ingest.writes)` would say 2. Only one file's capture time was
    rescued, and that is what the card must say.
    """
    _needs_exiftool()
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    rescued, already = source / "a.jpg", source / "b.jpg"
    _photo(rescued, (12, 200, 90))
    _photo(already, (200, 12, 90), embedded="2011:03:04 05:06:07")
    _sidecar(rescued)
    _sidecar(already)
    destination = tmp_path / "Library"
    destination.mkdir()

    summary = _run(tmp_path / "Takeout", destination, tmp_path / "c.sqlite")

    assert summary["organized"] == 2, "both should have been imported, so the count below is real"
    assert summary["dates_from_sidecar"] == 1


def test_a_duplicate_the_run_skipped_is_not_counted_as_a_date_rescued(tmp_path: Path) -> None:
    """⚠ **The inflation a Takeout would cause every single time.** An export holds the same photo
    once per album, so the same rescued date is planned N times. Only the copy that was actually
    organized carries it; the others were never written, and counting them would report more
    rescues than there are files in the library."""
    _needs_exiftool()
    root = tmp_path / "Takeout"
    first = root / "Photos from 2014"
    album = root / "Holiday"
    first.mkdir(parents=True)
    album.mkdir(parents=True)
    _photo(first / "a.jpg", (12, 200, 90))
    _sidecar(first / "a.jpg")
    shutil.copy(first / "a.jpg", album / "a.jpg")
    _sidecar(album / "a.jpg")
    destination = tmp_path / "Library"
    destination.mkdir()

    summary = _run(root, destination, tmp_path / "c.sqlite")

    assert summary["duplicates"] == 1, "the two copies were not recognised, so this proves nothing"
    assert summary["organized"] == 1
    assert summary["dates_from_sidecar"] == 1


def test_no_sidecar_dates_rescued_reports_zero(tmp_path: Path) -> None:
    """The anti-vacuity anchor: the count is not simply the number of files imported."""
    _needs_exiftool()
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    _photo(source / "a.jpg", (12, 200, 90), embedded="2011:03:04 05:06:07")
    _sidecar(source / "a.jpg")
    destination = tmp_path / "Library"
    destination.mkdir()

    summary = _run(tmp_path / "Takeout", destination, tmp_path / "c.sqlite")

    assert summary["organized"] == 1
    assert summary["dates_from_sidecar"] == 0


def test_a_second_drive_is_told_both_answers(tmp_path: Path) -> None:
    """⚠ **`(aei)` and D14 on the completion card.** The same export into a SECOND destination:
    every file is written there, and every file is also already in the library. Both are true, and
    a card that reported only `duplicates` - this destination's answer, correctly 0 - would leave a
    user certain their photographs had been copied twice."""
    _needs_exiftool()
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    _photo(source / "a.jpg", (12, 200, 90))
    _sidecar(source / "a.jpg")
    db = tmp_path / "c.sqlite"
    first, second = tmp_path / "DriveA", tmp_path / "DriveB"
    first.mkdir()
    second.mkdir()

    _run(tmp_path / "Takeout", first, db)
    summary = _run(tmp_path / "Takeout", second, db)

    assert summary["organized"] == 1, "the second drive received nothing, which is `(aei)` itself"
    assert summary["duplicates"] == 0, "this destination held nothing, so nothing was collapsed"
    assert summary["already_in_library"] == 1


def test_an_ordinary_organize_carries_neither_count(tmp_path: Path) -> None:
    """The keys are an IMPORT's, and an organize summary must not grow them - a renderer that
    found `dates_from_sidecar` on an organize would draw a row about a feature that did not run."""
    _needs_exiftool()
    source = tmp_path / "Loose"
    source.mkdir()
    _photo(source / "a.jpg", (12, 200, 90))
    destination = tmp_path / "Library"
    destination.mkdir()

    summary = dict(
        service.organize_run(source, destination, tmp_path / "c.sqlite")(
            lambda _p: None, threading.Event()
        )
    )

    assert summary["organized"] == 1
    assert "dates_from_sidecar" not in summary
    assert "already_in_library" not in summary


# ------------------------------------------------ the tree the report is about, not the one typed


def test_the_preview_reports_the_tree_it_scanned(tmp_path: Path) -> None:
    """A plain folder: the source is itself, which is the case the key must not break."""
    _needs_exiftool()
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    _photo(source / "a.jpg", (12, 200, 90))
    _sidecar(source / "a.jpg")
    destination = tmp_path / "Library"
    destination.mkdir()

    preview = service.ingest_preview(
        tmp_path / "Takeout", destination, tmp_path / "c.sqlite", cancel=threading.Event()
    )

    assert preview["source"] == str(tmp_path / "Takeout")


def test_an_archive_preview_reports_the_staging_tree_not_the_zip(tmp_path: Path) -> None:
    """⚠ **THE HANDOVER THAT STOPS "0 IMPORTED" COMING BACK.**

    The user typed a path to a `.zip`. The report is about the tree that was unpacked out of it,
    and the screen starts the run from THIS - not from the box it read the archive path out of.
    A run given the archive calls `discover()` on a file, finds no photographs, and says so.
    """
    _needs_exiftool()
    staged = tmp_path / "src" / "Takeout" / "Photos from 2014"
    staged.mkdir(parents=True)
    _photo(staged / "a.jpg", (12, 200, 90))
    _sidecar(staged / "a.jpg")
    archives = tmp_path / "Archives"
    archives.mkdir()
    with zipfile.ZipFile(archives / "takeout-001.zip", "w") as zf:
        for path in sorted((tmp_path / "src").rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(tmp_path / "src"))
    destination = tmp_path / "Library"
    destination.mkdir()

    report = service.archive_ingest_run(archives, destination, tmp_path / "c.sqlite")(
        lambda _p: None, threading.Event()
    )

    assert report["files"] == 1, "the archive was not unpacked, so the source below proves nothing"
    assert report["source"] != str(archives)
    assert Path(report["source"]).is_dir()
    assert ".truestill-staging" in Path(report["source"]).parts
