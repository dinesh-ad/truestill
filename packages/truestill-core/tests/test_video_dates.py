"""End-to-end: a real QuickTime video's local recording date survives the exiftool read.

Guards the whole chain -- ``read_metadata`` must actually fetch ``CreationDate`` and the
resolver must file by the local wall-clock, not the UTC container tags.

**This used to need ffmpeg to mint the container, and therefore skipped on every CI runner on
all three platforms** - the only video test in the repo, never once executed where it would be
checked. The container is now a committed 1.5 KB fixture (`fixtures/tiny-1frame.mp4`), so the
only remaining dependency is exiftool, which CI installs.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.dates import resolve_capture_datetime
from truestill_core.exif import read_metadata
from truestill_core.models import DateSource

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")

#: The smallest valid QuickTime container, committed so these tests never skip. See
#: `fixtures/README.md` for how to regenerate it.
FIXTURE = Path(__file__).parent / "fixtures" / "tiny-1frame.mp4"


def _apple_video(path: Path) -> None:
    """A 1-frame MP4 tagged like an iPhone clip: UTC container dates + local CreationDate."""
    shutil.copy2(FIXTURE, path)
    subprocess.run(
        [
            "exiftool",
            "-q",
            "-overwrite_original",
            "-QuickTime:CreateDate=2023:08:19 20:00:00",  # UTC, per the QuickTime spec
            "-QuickTime:MediaCreateDate=2023:08:19 20:00:00",
            "-QuickTime:TrackCreateDate=2023:08:19 20:00:00",
            "-Keys:CreationDate=2023:08:20 01:30:00+05:30",  # true local moment + offset
            str(path),
        ],
        check=True,
    )


def test_real_video_files_by_local_creationdate(tmp_path: Path) -> None:
    video = tmp_path / "IMG_1234.mov"
    _apple_video(video)

    meta = read_metadata([video])
    assert video in meta
    assert meta[video].get("CreationDate", "").startswith("2023:08:20 01:30:00")

    when, source, tag = resolve_capture_datetime(video, meta[video])
    assert when == datetime(2023, 8, 20, 1, 30, 0)  # local day, not the UTC 08-19
    assert source is DateSource.EXIF
    assert tag == "CreationDate"
