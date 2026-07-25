"""End-to-end: a real QuickTime video's local recording date survives the exiftool read.

Guards the whole chain -- ``read_metadata`` must actually fetch ``CreationDate`` and the
resolver must file by the local wall-clock, not the UTC container tags. Needs ffmpeg (to mint a
valid MP4 container) and exiftool (to write the tags); skips where either is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from vaeon_core.dates import resolve_capture_datetime
from vaeon_core.exif import read_metadata
from vaeon_core.models import DateSource

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("exiftool") is None,
    reason="needs ffmpeg + exiftool",
)


def _apple_video(path: Path) -> None:
    """A 1-frame MP4 tagged like an iPhone clip: UTC container dates + local CreationDate."""
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:d=1",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
    )
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
