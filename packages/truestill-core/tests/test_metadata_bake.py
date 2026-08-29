"""Batched metadata baking -- the one path that modifies bytes the user will keep.

The batch made the ingest ~27x faster (255 ms/file -> 9.3 ms/file, measured over 1,203 files),
and the whole reason that is safe to do is that a batch can only ever damage a *staged copy*.
These tests hold that line: every failure mode has to end with the original untouched, nothing
half-written at the destination, and a run that says so out loud rather than reporting success
for a bake that never happened.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import exif, organizer
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.exif import WRITE_BATCH_SIZE, build_metadata_args, read_metadata
from truestill_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    RuleName,
)
from truestill_core.organizer import execute
from truestill_core.takeout import IngestContext, MetadataWrite

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

WHEN = datetime(2019, 4, 3, 8, 15)


def _photos(root: Path, count: int) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    made = []
    for i in range(count):
        path = root / f"IMG_{i:04d}.jpg"
        Image.new("RGB", (48, 32), (i % 256, 40, 90)).save(path, "JPEG")
        made.append(path)
    return made


def _resolution(source: Path, sha: str) -> Resolution:
    decision = Decision(
        source=source,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule=RuleName.DEVICE
        ),
        captured_at=WHEN,
        date_source=DateSource.EXIF,
        date_tag=None,
        relative=Path(f"Camera/{WHEN:%Y}/{WHEN:%m}/{source.name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _ingest(sources: list[Path]) -> IngestContext:
    write = MetadataWrite(taken_at_local=WHEN, gps=None, description="from a sidecar")
    return IngestContext(writes={str(p): write for p in sources})


# --- the batch itself ---------------------------------------------------------------------


def test_a_batch_bakes_every_file_it_is_given(tmp_path: Path) -> None:
    """Correctness first: batching must not turn into 'one file got the metadata'."""
    photos = _photos(tmp_path / "src", 5)
    args = build_metadata_args(taken_at_local=WHEN, description="hello")

    verdicts = exif.write_metadata_batch([(p, args) for p in photos])

    assert verdicts == dict.fromkeys(photos, True)
    for tags in read_metadata(photos).values():
        assert tags["DateTimeOriginal"] == "2019:04:03 08:15:00"


def test_the_batch_spans_chunks_without_losing_a_file(tmp_path: Path) -> None:
    """More files than one process handles: the chunk boundary is where an off-by-one hides."""
    photos = _photos(tmp_path / "src", WRITE_BATCH_SIZE + 3)
    args = build_metadata_args(taken_at_local=WHEN)

    verdicts = exif.write_metadata_batch([(p, args) for p in photos])

    assert len(verdicts) == len(photos)
    assert all(verdicts.values())


def test_a_file_exiftool_cannot_write_is_reported_without_condemning_its_neighbours(
    tmp_path: Path,
) -> None:
    """One bad file in a batch is one failure, not a failed batch and not a silent success."""
    photos = _photos(tmp_path / "src", 3)
    missing = tmp_path / "src" / "not-here.jpg"
    args = build_metadata_args(taken_at_local=WHEN)

    verdicts = exif.write_metadata_batch(
        [(photos[0], args), (missing, args), (photos[1], args), (photos[2], args)]
    )

    assert verdicts[missing] is False
    assert [verdicts[p] for p in photos] == [True, True, True]


def test_a_process_that_dies_mid_batch_is_detected(tmp_path: Path, monkeypatch) -> None:
    """The failure mode the batch introduces, and the reason silence is never read as success.

    A killed exiftool simply stops printing. Every file past that point is *unknown*, and the
    only safe reading of unknown is failed -- reporting them as baked would record metadata
    that is not on disk.
    """
    photos = _photos(tmp_path / "src", 6)
    args = build_metadata_args(taken_at_local=WHEN)
    real_run = subprocess.run

    def truncated(*call_args, **kwargs):
        proc = real_run(*call_args, **kwargs)
        proc.stdout = "    1 image files updated\n    1 image files updated\n"  # died after two
        return proc

    monkeypatch.setattr(exif.binaries, "run", truncated)
    verdicts = exif.write_metadata_batch([(p, args) for p in photos])

    assert [verdicts[p] for p in photos] == [True, True, False, False, False, False]


def test_exiftool_failing_to_launch_fails_every_file_rather_than_raising(
    tmp_path: Path, monkeypatch
) -> None:
    photos = _photos(tmp_path / "src", 3)
    args = build_metadata_args(taken_at_local=WHEN)

    def boom(*_args, **_kwargs):
        raise OSError(1, "no fork for you")

    monkeypatch.setattr(exif.binaries, "run", boom)

    assert exif.write_metadata_batch([(p, args) for p in photos]) == dict.fromkeys(photos, False)


# --- the run that uses it -----------------------------------------------------------------


def test_a_baked_ingest_organizes_every_file_with_its_metadata(tmp_path: Path) -> None:
    photos = _photos(tmp_path / "src", 4)
    dest = tmp_path / "out"
    resolutions = [_resolution(p, f"sha-{i}") for i, p in enumerate(photos)]

    results = execute(
        resolutions, LocalDestination(dest), apply=True, ingest=_ingest(photos), catalog=None
    )

    assert [r.status for r in results] == [ActionStatus.UPLOADED] * 4
    copies = sorted(dest.rglob("*.jpg"))
    assert len(copies) == 4
    for tags in read_metadata(copies).values():
        assert tags["DateTimeOriginal"] == "2019:04:03 08:15:00"


def test_a_failed_bake_leaves_the_original_untouched_and_uploads_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """The honesty requirement, end to end.

    Nothing is written to the destination for a file whose bake could not be confirmed, the
    source keeps its exact bytes, and the run reports FAILED rather than counting it organized.
    """
    photos = _photos(tmp_path / "src", 3)
    before = [p.read_bytes() for p in photos]
    dest = tmp_path / "out"
    resolutions = [_resolution(p, f"sha-{i}") for i, p in enumerate(photos)]

    def nothing_confirmed(*call_args, **_kwargs):
        return subprocess.CompletedProcess(call_args[0], 1, stdout="", stderr="Error: nope")

    monkeypatch.setattr(exif.binaries, "run", nothing_confirmed)
    results = execute(
        resolutions, LocalDestination(dest), apply=True, ingest=_ingest(photos), catalog=None
    )

    assert [r.status for r in results] == [ActionStatus.FAILED] * 3
    assert all("original is untouched" in (r.detail or "") for r in results)
    assert [p.read_bytes() for p in photos] == before  # sources byte-for-byte as they were
    assert list(dest.rglob("*.jpg")) == []  # and nothing half-written at the destination


def test_a_partial_batch_failure_reports_each_file_truthfully(tmp_path: Path, monkeypatch) -> None:
    """A batch that dies part-way must not drag down the files it had already finished."""
    photos = _photos(tmp_path / "src", 4)
    dest = tmp_path / "out"
    resolutions = [_resolution(p, f"sha-{i}") for i, p in enumerate(photos)]
    real_run = subprocess.run

    def truncated(*call_args, **kwargs):
        proc = real_run(*call_args, **kwargs)
        proc.stdout = "    1 image files updated\n    1 image files updated\n"
        return proc

    monkeypatch.setattr(exif.binaries, "run", truncated)
    results = execute(
        resolutions, LocalDestination(dest), apply=True, ingest=_ingest(photos), catalog=None
    )

    assert [r.status for r in results] == [
        ActionStatus.UPLOADED,
        ActionStatus.UPLOADED,
        ActionStatus.FAILED,
        ActionStatus.FAILED,
    ]
    assert len(list(dest.rglob("*.jpg"))) == 2  # exactly the two that were confirmed


def test_staged_copies_do_not_outlive_the_run(tmp_path: Path) -> None:
    """The batch trades disk for speed; the trade is bounded and it is returned."""
    photos = _photos(tmp_path / "src", 5)
    dest = tmp_path / "out"
    staged: list[Path] = []
    resolutions = [_resolution(p, f"sha-{i}") for i, p in enumerate(photos)]

    real_batch = exif.write_metadata_batch

    def remember(items):
        staged.extend(path for path, _ in items)
        return real_batch(items)

    original = organizer.write_metadata_batch
    organizer.write_metadata_batch = remember  # type: ignore[assignment]
    try:
        execute(
            resolutions, LocalDestination(dest), apply=True, ingest=_ingest(photos), catalog=None
        )
    finally:
        organizer.write_metadata_batch = original  # type: ignore[assignment]

    assert staged  # the batch path really ran
    assert not any(p.exists() for p in staged)  # and left nothing behind


def test_every_argfile_block_declares_the_filename_charset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DECLARATION guard, and it says so (`handoff-2026-08-27.md` names the convention).

    The behaviour these two lines buy is only observable on Windows, which no lane runs with a
    hostile fixture: without ``-charset filename=utf8`` exiftool reads the argfile's UTF-8
    filename bytes through the console code page and bakes the wrong file or none. What CAN be
    asserted everywhere is the declaration - every ``-execute`` block leads with the charset
    pair, PER BLOCK, because options apply only to the command their ``-execute`` closes and a
    single leading ``-charset`` would cover the first file alone (verified against a live
    two-block argfile, 2026-08-29). Since `(aif)` the argfile travels on STDIN (``-@ -``) so no
    filename - not even the argfile's own path - crosses argv; the command shape is pinned here
    for the same reason the charset is.
    """
    captured: dict[str, str] = {}

    def snoop(command: list[str | Path], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert [str(part) for part in command[1:]] == ["-@", "-"]
        captured["argfile"] = str(kwargs["input"])
        blocks = captured["argfile"].count("-execute")
        return subprocess.CompletedProcess(
            list(command), 0, "    1 image files updated\n" * blocks, ""
        )

    monkeypatch.setattr(exif.binaries, "run", snoop)
    photos = _photos(tmp_path, 2)

    verdicts = exif.write_metadata_batch(
        [(p, ["-DateTimeOriginal=2019:04:03 08:15:00"]) for p in photos]
    )

    assert all(verdicts.values())
    blocks = [b for b in captured["argfile"].split("-execute") if b.strip()]
    assert len(blocks) == len(photos)
    for block in blocks:
        lines = [line for line in block.strip().splitlines() if line]
        assert lines[:2] == ["-charset", "filename=utf8"], lines
