"""An applied import puts the SIDECAR's date into the file on disk. D17.

⚠ **THIS IS THE REASON THE FEATURE EXISTS, so it is asserted on the bytes rather than on the
call.** Google Takeout does not always write the original timestamp back into the image; the true
capture time is in the sidecar JSON beside it. An `/api/ingest/run` routed through organize's run
**without** `takeout=` would succeed, report a tidy count, and write copies carrying whatever date
the export left - which is the whole defect, silently.

**So every test here reads `DateTimeOriginal` back off the organized copy with `exiftool`**, and
the source is stripped of EXIF first so a passing assertion cannot be the camera's own date
leaking through.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_app import service

#: 2014-06-05 20:26:40 UTC. ⚠ **Derived in the test, never hand-typed**: my own hand-computation
#: of this was 80 minutes out, and a wrong constant here would have failed a correct product.
TRUE_EPOCH = 1402000000


def _expected() -> str:
    return datetime.fromtimestamp(TRUE_EPOCH, UTC).strftime("%Y:%m:%d %H:%M:%S")


def _exif_date(path: Path) -> str:
    return subprocess.run(
        ["exiftool", "-s3", "-DateTimeOriginal", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def undated_takeout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A photograph with NO embedded date, and a sidecar that knows the true one."""
    if shutil.which("exiftool") is None:  # pragma: no cover - exiftool is a documented dependency
        pytest.skip("exiftool is not on PATH; this test reads dates back off the file")
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    media = source / "IMG_0001.jpg"
    Image.new("RGB", (64, 64), (12, 200, 90)).save(media, "JPEG", quality=95)
    subprocess.run(["exiftool", "-overwrite_original", "-q", "-all=", str(media)], check=True)
    assert _exif_date(media) == "", "the fixture kept a date, so a pass below proves nothing"
    (source / f"{media.name}.supplemental-metadata.json").write_text(
        json.dumps({"title": media.name, "photoTakenTime": {"timestamp": str(TRUE_EPOCH)}})
    )
    destination = tmp_path / "Library"
    destination.mkdir()
    return tmp_path / "Takeout", destination, tmp_path / "c.sqlite"


def _organized(destination: Path) -> list[Path]:
    return [p for p in destination.rglob("*.jpg") if p.is_file()]


def test_the_rescued_date_is_in_the_file_on_disk(
    undated_takeout: tuple[Path, Path, Path],
) -> None:
    """**The assertion the feature is for.** Not that the run returned, that the bytes carry it."""
    takeout, destination, db = undated_takeout

    service.ingest_run(takeout, destination, db)(lambda _p: None, threading.Event())

    landed = _organized(destination)
    assert len(landed) == 1, "nothing landed, so the date assertion below would be free"
    assert _exif_date(landed[0]) == _expected()


def test_the_preview_s_claim_is_what_the_run_delivers(
    undated_takeout: tuple[Path, Path, Path],
) -> None:
    """⚠ **The promise-versus-run split, closed on the date axis.**

    The preview counts this file under `dates_photo_taken` - the sidecar tier. If the run wrote a
    file-mtime date instead, the count would still be 1 and the copy would be wrong. So the claim
    and the bytes are compared to each other, not each to a literal.
    """
    takeout, destination, db = undated_takeout

    preview = service.ingest_preview(
        takeout, destination, db, progress=lambda _p: None, cancel=threading.Event()
    )
    service.ingest_run(takeout, destination, db)(lambda _p: None, threading.Event())

    assert preview["dates_photo_taken"] == 1  # type: ignore[typeddict-item]
    assert preview["kept"] == 1  # type: ignore[typeddict-item]
    landed = _organized(destination)
    assert len(landed) == 1, "nothing landed, so the date comparison below is free"
    assert _exif_date(landed[0]) == _expected(), "the run wrote a date the preview did not promise"


def test_an_organize_run_without_sidecars_is_unchanged(tmp_path: Path) -> None:
    """⚠ **The half that proves `takeout=` is doing the work.**

    `organize_run` grew an optional parameter. Without it the behaviour must be exactly what it
    was - so this drives the same undated file through the ordinary organize and asserts the date
    is NOT rescued. If it were, the test above would pass for the wrong reason.
    """
    if shutil.which("exiftool") is None:  # pragma: no cover
        pytest.skip("exiftool is not on PATH")
    source = tmp_path / "Loose"
    source.mkdir()
    media = source / "IMG_0002.jpg"
    Image.new("RGB", (64, 64), (200, 12, 90)).save(media, "JPEG", quality=95)
    subprocess.run(["exiftool", "-overwrite_original", "-q", "-all=", str(media)], check=True)
    (source / f"{media.name}.supplemental-metadata.json").write_text(
        json.dumps({"title": media.name, "photoTakenTime": {"timestamp": str(TRUE_EPOCH)}})
    )
    destination = tmp_path / "Library"
    destination.mkdir()

    service.organize_run(source, destination, tmp_path / "c.sqlite")(
        lambda _p: None, threading.Event()
    )

    landed = _organized(destination)
    assert len(landed) == 1, "nothing landed, so the assertion below is free"
    assert _exif_date(landed[0]) != _expected(), "organize rescued a date without being asked to"


def test_the_sidecar_beats_no_date_but_the_file_keeps_a_good_one(tmp_path: Path) -> None:
    """⚠ **The bake is conditional, and `ingest_context` says so**: *"write a rescued date into a
    copy only when it lacks a good embedded one"*. A file that already knows when it was taken
    must keep that, or an import would overwrite better evidence with worse."""
    if shutil.which("exiftool") is None:  # pragma: no cover
        pytest.skip("exiftool is not on PATH")
    source = tmp_path / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    media = source / "IMG_0003.jpg"
    Image.new("RGB", (64, 64), (90, 12, 200)).save(media, "JPEG", quality=95)
    embedded = "2011:03:04 05:06:07"
    subprocess.run(
        ["exiftool", "-overwrite_original", "-q", f"-DateTimeOriginal={embedded}", str(media)],
        check=True,
    )
    (source / f"{media.name}.supplemental-metadata.json").write_text(
        json.dumps({"title": media.name, "photoTakenTime": {"timestamp": str(TRUE_EPOCH)}})
    )
    destination = tmp_path / "Library"
    destination.mkdir()

    service.ingest_run(tmp_path / "Takeout", destination, tmp_path / "c.sqlite")(
        lambda _p: None, threading.Event()
    )

    landed = _organized(destination)
    assert len(landed) == 1
    assert _exif_date(landed[0]) == embedded, "the sidecar overwrote a date the file already had"


# --------------------------------------------------------- the archive the screen actually hands


def test_an_archive_is_imported_from_its_unpacked_tree(tmp_path: Path) -> None:
    """⚠ **FOUND BY WALKING IT, AND IT IMPORTED NOTHING.**

    The Import screen hands the run the path the user typed, which for the case the screen exists
    for is a **`.zip`**. The preview never sees that - `archive_ingest_run` unpacks first and
    previews the staging tree - so the preview promised eight files and the run called `discover`
    on an archive file, found none, and reported *"0 imported"*. A clean, confident, wrong answer.

    `_unpacked_source` finds what the unpack left, using `pending_staging`, which answers from the
    destination path alone.
    """
    if shutil.which("exiftool") is None:  # pragma: no cover
        pytest.skip("exiftool is not on PATH")
    staged = tmp_path / "Library" / ".truestill-staging" / "part1"
    source = staged / "Takeout" / "Photos from 2014"
    source.mkdir(parents=True)
    media = source / "IMG_0009.jpg"
    Image.new("RGB", (64, 64), (5, 90, 200)).save(media, "JPEG", quality=95)
    subprocess.run(["exiftool", "-overwrite_original", "-q", "-all=", str(media)], check=True)
    (source / f"{media.name}.supplemental-metadata.json").write_text(
        json.dumps({"title": media.name, "photoTakenTime": {"timestamp": str(TRUE_EPOCH)}})
    )
    # The journal is what `pending_staging` reads; it is written beside the tree by the unpack.
    (tmp_path / "Library" / ".truestill-staging" / "part1.json").write_text(
        json.dumps({"staging_root": str(staged), "sources": ["part1.zip"]})
    )
    archive = tmp_path / "part1.zip"
    archive.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # never read: the unpack already happened

    service.ingest_run(archive, tmp_path / "Library", tmp_path / "c.sqlite")(
        lambda _p: None, threading.Event()
    )

    landed = [p for p in _organized(tmp_path / "Library") if ".truestill-staging" not in p.parts]
    assert len(landed) == 1, "the run imported from the archive path instead of the staging tree"
    assert _exif_date(landed[0]) == _expected()


def test_a_plain_folder_is_still_imported_from_itself(
    undated_takeout: tuple[Path, Path, Path],
) -> None:
    """⚠ **The half that stops the resolution swallowing the ordinary case.** An already-extracted
    folder must keep the old single-step behaviour - a directory is returned untouched, and if it
    were not, every non-archive import would look for a staging tree that does not exist."""
    takeout, destination, db = undated_takeout

    service.ingest_run(takeout, destination, db)(lambda _p: None, threading.Event())

    assert len(_organized(destination)) == 1
