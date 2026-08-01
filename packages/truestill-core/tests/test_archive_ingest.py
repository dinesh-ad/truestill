"""Archives reach the existing Takeout pipeline unchanged, and the multi-part claim is proven.

**The correctness question the whole set-based design exists for.** `scan_takeout` matches each
media file to its JSON sidecar **per folder**, because Google never cross-references sidecars
across directories. Google also splits one export across many numbered archives, and it splits
them **by size, not by folder** - so ``Photos from 2014/IMG_0001.jpg`` can be in ``-001.zip``
while ``Photos from 2014/IMG_0001.jpg.json`` is in ``-002.zip``.

Extract them one at a time and each archive is internally consistent, each scan succeeds, and the
photo silently loses its real capture date. Merging every part into **one** staging tree first is
what makes the folder whole again - and this asserts that rather than assuming it, with a folder
that genuinely straddles a part boundary.

Nothing here changes `scan_takeout`. That it needs no change *is the claim being tested*.
"""

from __future__ import annotations

import json
import threading
import zipfile
from pathlib import Path

import pytest
from truestill_core.archive_extract import clear_staging, extract_archive_set, pending_staging
from truestill_core.archive_ingest import ArchiveRefusal, precheck_archives
from truestill_core.archive_set import discover_archive_set
from truestill_core.takeout import scan_takeout

_SIDECAR = json.dumps(
    {"photoTakenTime": {"timestamp": "1403000000"}, "description": "from the sidecar"}
).encode()


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    return _zip(directory / f"takeout-20260801T000000Z-{number:03d}.zip", entries)


def test_a_folder_straddling_two_parts_still_matches_its_sidecars(tmp_path: Path) -> None:
    """THE multi-part test: the photo is in part 1, its sidecar is in part 2.

    Google splits by size rather than by folder, so this is the ordinary case and not a corner.
    Extracted separately, each part scans cleanly and the date is silently lost.
    """
    folder = "Takeout/Google Photos/Photos from 2014"
    _part(tmp_path, 1, {f"{folder}/IMG_0001.jpg": b"\xff\xd8jpegbytes"})
    _part(tmp_path, 2, {f"{folder}/IMG_0001.jpg.json": _SIDECAR})

    found = discover_archive_set(sorted(tmp_path.glob("*.zip")))
    result = extract_archive_set(found, tmp_path / "dest")
    scan = scan_takeout(result.staging_root)

    photo = result.staging_root / folder / "IMG_0001.jpg"
    assert photo in scan.sidecars, "the sidecar in the next part was not matched"
    assert scan.sidecars[photo].description == "from the sidecar"
    assert scan.missing_sidecar == []


def test_extracting_the_parts_separately_is_what_loses_the_date(tmp_path: Path) -> None:
    """Cry-wolf half, and the reason the test above is not decoration.

    Proves the failure is real: scan each part's own tree and the photo has no sidecar. If this
    ever stops failing, the merge is no longer doing anything and the test above proves nothing.
    """
    folder = "Takeout/Google Photos/Photos from 2014"
    _part(tmp_path, 1, {f"{folder}/IMG_0001.jpg": b"\xff\xd8jpegbytes"})
    _part(tmp_path, 2, {f"{folder}/IMG_0001.jpg.json": _SIDECAR})

    one = extract_archive_set(discover_archive_set([tmp_path / _name(1)]), tmp_path / "d1")
    scan = scan_takeout(one.staging_root)

    assert scan.sidecars == {}, "the split did not actually separate the photo from its sidecar"
    assert len(scan.missing_sidecar) == 1


def _name(number: int) -> str:
    return f"takeout-20260801T000000Z-{number:03d}.zip"


def test_album_membership_survives_the_merge(tmp_path: Path) -> None:
    """Albums are folders, so the same straddle risk applies to album names."""
    _part(tmp_path, 1, {"Takeout/Google Photos/Wayanad 2014/IMG_1.jpg": b"\xff\xd8a"})
    _part(tmp_path, 2, {"Takeout/Google Photos/Wayanad 2014/IMG_2.jpg": b"\xff\xd8b"})

    found = discover_archive_set(sorted(tmp_path.glob("*.zip")))
    result = extract_archive_set(found, tmp_path / "dest")
    scan = scan_takeout(result.staging_root)

    albums = set(scan.albums.values())
    assert albums == {"Wayanad 2014"}
    assert len(scan.albums) == 2, "a file from the second part lost its album"


# --- the preconditions, before anything is written ---------------------------------------


def test_a_missing_part_is_refused_before_extraction(tmp_path: Path) -> None:
    for number in (1, 2, 4):
        _part(tmp_path, number, {f"Takeout/a/IMG_{number}.jpg": b"\xff\xd8x"})

    report = precheck_archives(sorted(tmp_path.glob("*.zip")), tmp_path / "dest")

    assert ArchiveRefusal.MISSING_PART in report.refusals
    assert "3" in report.detail
    assert report.may_proceed is False


def test_encrypted_and_nested_entries_are_named_in_the_refusal(tmp_path: Path) -> None:
    """Named by entry: "contains another archive" is useless without saying which one."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x", "a/inner.zip": b"PK"})

    report = precheck_archives([tmp_path / "photos.zip"], tmp_path / "dest")

    assert ArchiveRefusal.NESTED_ARCHIVE in report.refusals
    assert "a/inner.zip" in report.detail
    assert report.may_proceed is False


def test_the_space_figure_is_labelled_as_the_archives_own_claim(tmp_path: Path) -> None:
    """The user must not read a header field as a measurement truestill made."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8" + b"x" * 500})

    report = precheck_archives([tmp_path / "photos.zip"], tmp_path / "dest")

    assert report.claimed_bytes == 502
    assert "claim" in report.detail.lower()
    assert report.may_proceed is True


def test_nothing_is_written_by_a_precheck(tmp_path: Path) -> None:
    """A user must be able to decline before anything touches their disk."""
    _zip(tmp_path / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x"})
    destination = tmp_path / "dest"

    precheck_archives([tmp_path / "photos.zip"], destination)

    assert not destination.exists()


# --- cancel ------------------------------------------------------------------------------


def test_cancel_leaves_the_ordinary_resumable_state(tmp_path: Path) -> None:
    """Not a special case: cancel stops the loop and the journal already describes the tree.

    The same state a crash leaves, reached deliberately - so recovery has one path rather than
    one for crashes and another for the button.
    """
    entries = {f"Takeout/a/IMG_{i:03d}.jpg": b"\xff\xd8" + bytes([i]) * 100 for i in range(20)}
    _zip(tmp_path / "photos.zip", entries)
    found = discover_archive_set([tmp_path / "photos.zip"])
    destination = tmp_path / "dest"
    cancel = threading.Event()

    def stop_after_three(_path: Path) -> None:
        if len(list((destination / ".truestill-staging").rglob("*.jpg"))) >= 3:
            cancel.set()

    result = extract_archive_set(found, destination, cancel=cancel, on_entry=stop_after_three)

    assert result.cancelled is True
    assert result.files_written < 20, "cancel did not stop the extraction"

    leftover = pending_staging(destination)
    assert leftover, "cancel left a tree the next run cannot attribute"
    clear_staging(leftover[0])
    assert pending_staging(destination) == []


def test_progress_reports_the_phase_a_user_reads(tmp_path: Path) -> None:
    """Unpacking is its own phase: it is the slow part and must not look like a frozen scan."""
    _zip(tmp_path / "photos.zip", {f"a/IMG_{i}.jpg": b"\xff\xd8x" for i in range(5)})
    found = discover_archive_set([tmp_path / "photos.zip"])
    phases: list[str] = []

    extract_archive_set(
        found, tmp_path / "dest", progress=lambda update: phases.append(update.phase)
    )

    assert phases, "extraction reported no progress at all"
    assert set(phases) == {"unpacking"}


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_selection_is_refused_rather_than_silently_doing_nothing(
    tmp_path: Path, bad: str
) -> None:
    """Cry-wolf's opposite: "nothing happened" must not be the report for "you selected nothing"."""
    report = precheck_archives([], tmp_path / "dest")

    assert report.may_proceed is False
    assert ArchiveRefusal.NO_ARCHIVES in report.refusals
    assert bad in report.detail or report.detail
