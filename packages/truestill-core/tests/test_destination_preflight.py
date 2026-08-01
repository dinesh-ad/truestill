"""Organize refuses a destination that cannot hold the work, **before** it starts.

**The failure this closes.** Organize had no preflight of any kind. Point it at a FAT32 SD card
with a few 4K videos in the source and it organized nine thousand files, then failed N of them
one ``[Errno 27] File too large`` at a time, at the very end - against a drive reporting 200 GB
free. The errno message is now named (`test_destination_errors`); this file covers the more
valuable half, which is not starting at all.

**The refusal lives in `execute`, not in its callers.** Both the CLI and the app call `execute`,
and a check in either one is a check the other surface silently lacks - which is exactly how
backup's space check ended up app-only and left the CLI unguarded. One home, so a third surface
cannot be added without it.

**Oversized files are named, never skipped.** Skipping them would produce a library quietly
missing the footage the user cared most about, reported as a success.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.destinations.base import Destination, DestinationError
from truestill_core.filesystem import FilesystemFacts
from truestill_core.models import DateSource, Decision, DuplicateKind, DuplicateMatch, FileHashes
from truestill_core.models import Resolution as Res
from truestill_core.organizer import execute

WHEN = datetime(2024, 6, 17, 9, 30)
CAT = CategoryMatch(label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device")


def _resolution(source: Path, *, duplicate: bool = False) -> Res:
    return Res(
        decision=Decision(
            source=source,
            category=CAT,
            captured_at=WHEN,
            date_source=DateSource.EXIF,
            date_tag="EXIF:DateTimeOriginal",
            relative=Path(f"Camera/2024/06/{source.name}"),
        ),
        hashes=FileHashes(sha256="0" * 64, perceptual=None),
        exact_duplicate=DuplicateMatch(
            kind=DuplicateKind.EXACT, matched_path="/fixture/a.jpg", origin="catalog"
        )
        if duplicate
        else None,
        near_duplicate=None,
    )


def _file(directory: Path, name: str, size: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"\xff\xd8" + b"x" * (size - 2))
    return path


def _fat(destination: Path, limit: int) -> LocalDestination:
    """A destination that answers as FAT32 with a small stand-in for the 4 GiB ceiling.

    The limit is injected rather than the size faked: writing a 4 GiB file in a test would cost
    minutes and 4 GiB of disk, and what is under test is the comparison, not the constant. The
    constant itself is pinned separately in `test_filesystem_limits`.
    """

    class _FatDestination(LocalDestination):
        def facts(self) -> FilesystemFacts:
            return FilesystemFacts(filesystem="vfat", max_file_bytes=limit)

    return _FatDestination(destination)


def test_an_oversized_file_refuses_the_run_before_anything_is_written(tmp_path: Path) -> None:
    """The whole point: nine thousand files are not organized first."""
    source = tmp_path / "src"
    small = _file(source, "IMG_0001.jpg", 50)
    big = _file(source, "VID_4K.mp4", 5_000)
    destination = tmp_path / "dest"

    with pytest.raises(DestinationError) as raised:
        execute(
            [_resolution(small), _resolution(big)],
            _fat(destination, limit=1_000),
            apply=True,
        )

    assert "VID_4K.mp4" in str(raised.value), "the file that would fail was not named"
    assert not list(destination.rglob("*.jpg")), "work started despite the refusal"


def test_the_refusal_names_the_file_rather_than_counting_it(tmp_path: Path) -> None:
    """ "3 files are too large" is not something a user can act on."""
    source = tmp_path / "src"
    resolutions = [_resolution(_file(source, f"VID_{i}.mp4", 5_000)) for i in range(3)]

    with pytest.raises(DestinationError) as raised:
        execute(resolutions, _fat(tmp_path / "dest", limit=1_000), apply=True)

    message = str(raised.value)
    for i in range(3):
        assert f"VID_{i}.mp4" in message


def test_an_oversized_file_is_never_silently_skipped(tmp_path: Path) -> None:
    """The tempting alternative - organize the rest, skip the big ones - is the worse bug.

    It reports success while leaving the library missing exactly the footage that mattered.
    So the small file that *could* have been written must not be written either.
    """
    source = tmp_path / "src"
    small = _file(source, "IMG_0001.jpg", 50)
    big = _file(source, "VID_4K.mp4", 5_000)
    destination = tmp_path / "dest"

    with pytest.raises(DestinationError):
        execute([_resolution(small), _resolution(big)], _fat(destination, limit=1_000), apply=True)

    assert not destination.exists() or not any(destination.rglob("*.jpg"))


def test_a_preview_reports_rather_than_refuses(tmp_path: Path) -> None:
    """``apply=False`` writes nothing anyway, so refusing it would only remove the user's
    ability to *see* the problem before deciding. Same shape as backup: report, then refuse."""
    source = tmp_path / "src"
    big = _file(source, "VID_4K.mp4", 5_000)

    results = execute([_resolution(big)], _fat(tmp_path / "dest", limit=1_000), apply=False)

    assert len(results) == 1


def test_a_destination_with_no_limit_proceeds(tmp_path: Path) -> None:
    """Guards the cry-wolf direction: ext4, NTFS and exFAT must be untouched by this."""
    source = tmp_path / "src"
    big = _file(source, "VID_4K.mp4", 5_000)
    destination = tmp_path / "dest"

    results = execute([_resolution(big)], LocalDestination(destination), apply=True)

    assert [r.status.name for r in results] == ["UPLOADED"]
    assert (destination / "Camera/2024/06/VID_4K.mp4").exists()


def test_duplicates_are_not_counted_against_the_limit(tmp_path: Path) -> None:
    """An exact duplicate is never written, so refusing the run over its size would block work
    that would have succeeded - the cry-wolf failure, from the other direction."""
    source = tmp_path / "src"
    big = _file(source, "VID_4K.mp4", 5_000)

    results = execute(
        [_resolution(big, duplicate=True)], _fat(tmp_path / "dest", limit=1_000), apply=True
    )

    assert [r.status.name for r in results] == ["DUPLICATE"]


def test_a_backend_that_cannot_answer_never_refuses(tmp_path: Path) -> None:
    """An rclone remote has no local filesystem to interrogate. The base class answers
    "unknown", and unknown must always mean proceed - a guess here would refuse real work."""

    class _Remote(Destination):
        def describe(self) -> str:
            return "remote:Photos"

        def exists(self, relative_path: str) -> bool:  # noqa: ARG002 - stub backend
            return False

        def upload(self, local: Path, relative_path: str) -> None:
            pass

        def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
            pass

        def list(self) -> list[str]:
            return []

    big = _file(tmp_path / "src", "VID_4K.mp4", 5_000)

    results = execute([_resolution(big)], _Remote(), apply=True)

    assert [r.status.name for r in results] == ["UPLOADED"]
