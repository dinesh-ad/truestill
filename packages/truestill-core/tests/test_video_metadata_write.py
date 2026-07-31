"""truestill's own metadata **write**, exercised on a real video container.

**This coverage did not exist - on any platform, skipped or otherwise.** The shipped Takeout
ingest writes videos today: `build_metadata_args` emits ``-QuickTime:CreateDate``, and
`_ingest_context` builds a `MetadataWrite` for **any** file with a Takeout sidecar, with no
media-type filter. Yet `test_metadata_bake.py` and `test_execute_matrix.py` contain zero video
references, and the repo's only video test covered *dating* (reading), not writing. So a write
to a user's video files ran through a path nothing asserted.

**Why videos are the higher-risk case**, and why this is worth its own file: QuickTime/MP4
writing rearranges an atom tree rather than patching a header, and MakerNotes carry offsets
exiftool has to relocate. Neither has an analogue in the JPEG path that
`test_metadata_bake.py` already covers, so JPEG coverage is not evidence about video.

What this pins is the contract truestill relies on, not exiftool's internals: the write is
confirmed, the bytes change, the container stays readable, the tag comes back, and **no
``_original`` sidecar is left behind** - `(bbb)` made truestill refuse those as media, so one
appearing here would litter a user's drive with files the product then ignores.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.exif import build_metadata_args, read_metadata, write_metadata_batch
from truestill_core.hashing import sha256_file

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

FIXTURE = Path(__file__).parent / "fixtures" / "tiny-1frame.mp4"
TAKEN = datetime(2014, 8, 16, 10, 46, 26)


@pytest.fixture
def video(tmp_path: Path) -> Path:
    target = tmp_path / "VID_20140816.mp4"
    shutil.copy2(FIXTURE, target)
    return target


def test_a_video_write_is_confirmed_by_exiftool(video: Path) -> None:
    """The verdict must be a real confirmation, not silence read as success.

    `write_metadata_batch` reports a file absent from a short reply as **failed**; this asserts
    the positive case on the container type that had none.
    """
    args = build_metadata_args(taken_at_local=TAKEN)
    assert args, "the arg builder produced no write for a dated video"

    verdicts = write_metadata_batch([(video, args)])

    assert verdicts == {video: True}


def test_a_video_write_changes_the_bytes_and_keeps_it_readable(video: Path) -> None:
    """A bake that changed nothing, or produced an unreadable file, would both pass a verdict."""
    before = sha256_file(video)

    write_metadata_batch([(video, build_metadata_args(taken_at_local=TAKEN))])

    assert sha256_file(video) != before, "the write reported success but changed no bytes"
    meta = read_metadata([video])
    assert video in meta, "the container is no longer readable after the write"
    assert meta[video].get("CreateDate", "").startswith("2014:08:16 10:46:26")


def test_a_video_write_leaves_no_original_sidecar(video: Path) -> None:
    """`(bbb)`: truestill refuses ``*_original`` as media, so producing one would litter a drive.

    The protection is `-overwrite_original` in `exif._WRITE_FLAGS`. Asserted here rather than
    trusted, because it is applied by `build_metadata_args` and a future caller that assembles
    args itself would lose it silently.
    """
    write_metadata_batch([(video, build_metadata_args(taken_at_local=TAKEN))])

    siblings = sorted(p.name for p in video.parent.iterdir())
    assert siblings == [video.name], f"a sidecar was left beside the video: {siblings}"


def test_the_original_survives_a_write_to_a_copy(video: Path, tmp_path: Path) -> None:
    """Copy-only (§1): baking a copy must not touch the file it was copied from."""
    source = tmp_path / "source.mp4"
    shutil.copy2(FIXTURE, source)
    before = sha256_file(source)

    write_metadata_batch([(video, build_metadata_args(taken_at_local=TAKEN))])

    assert sha256_file(source) == before
