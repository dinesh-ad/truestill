"""Batch metadata extraction via the ``exiftool`` binary.

One ``exiftool`` invocation per chunk of files rather than one per file: process
startup dominates runtime otherwise, and a library of 84 GB is tens of thousands of
files. Only the tags the rules actually consult are requested, which keeps the JSON
payload small.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from truestill_core.progress import Phase, Progress, ProgressCallback

EXIFTOOL_BIN = "exiftool"

#: Files handed to exiftool per invocation. Large enough to amortise startup, small
#: enough to stay well clear of ARG_MAX on long paths.
BATCH_SIZE = 200

#: Tags consulted by the categorization and date rules. ``SourceFile`` is always
#: emitted by exiftool and is used to key results back to their paths.
REQUESTED_TAGS: tuple[str, ...] = (
    # categorization
    "SamsungCaptureInfo",
    "Make",
    "Model",
    "LensModel",
    # dates, in the order the resolver prefers them
    "DateTimeOriginal",
    # com.apple.quicktime.creationdate: the ONLY video tag carrying the local recording
    # moment *with* its UTC offset. The CreateDate family below is stored in UTC per the
    # QuickTime spec, so for anything shot away from UTC it names the wrong wall-clock -- and
    # near midnight, the wrong day/month. Requested so the resolver can prefer it.
    "CreationDate",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    # informational, surfaced in reports
    "FileType",
    "MIMEType",
    "ImageWidth",
    "ImageHeight",
)

#: GPS tags, requested with a trailing ``#`` so exiftool emits signed decimal degrees for
#: just these (negative for S/W) without changing the format of any other tag. Used by the
#: event layer to reinforce time-gap boundaries with location jumps.
_NUMERIC_TAGS: tuple[str, ...] = (
    "GPSLatitude",
    "GPSLongitude",
)

_MISSING_MSG = (
    "exiftool was not found on PATH. On Ubuntu install it with: "
    "sudo apt install -y libimage-exiftool-perl"
)


class ExiftoolMissingError(RuntimeError):
    """Raised when the exiftool binary is unavailable."""


def ensure_exiftool() -> str:
    """Return the path to the exiftool binary, or raise if it is not installed."""
    found = shutil.which(EXIFTOOL_BIN)
    if found is None:
        raise ExiftoolMissingError(_MISSING_MSG)
    return found


def _chunked(items: Sequence[Path], size: int) -> Iterator[Sequence[Path]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def write_metadata(
    path: Path,
    *,
    taken_at_local: datetime | None = None,
    gps: tuple[float, float] | None = None,
    description: str = "",
) -> bool:
    """Bake rescued metadata into a file in place, losslessly (no pixel re-encode).

    exiftool rewrites only the metadata segment, so image quality is untouched -- but the
    file's bytes (and hence its hash) change. This is used **only** on organized copies during
    Takeout ingestion; the normal pipeline never calls it. Returns whether exiftool succeeded.
    """
    args: list[str] = ["-overwrite_original", "-q", "-m"]
    if taken_at_local is not None:
        stamp = taken_at_local.strftime("%Y:%m:%d %H:%M:%S")
        args += [
            f"-DateTimeOriginal={stamp}",
            f"-CreateDate={stamp}",
            f"-QuickTime:CreateDate={stamp}",
        ]
    if gps is not None:
        lat, lon = gps
        args += [
            f"-GPSLatitude={abs(lat)}",
            f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
            f"-GPSLongitude={abs(lon)}",
            f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
        ]
    if description:
        args += [f"-Description={description}", f"-ImageDescription={description}"]

    if not args[3:]:  # nothing beyond the flags -> nothing to write
        return True

    binary = ensure_exiftool()
    proc = subprocess.run([binary, *args, str(path)], capture_output=True, text=True, check=False)
    return proc.returncode == 0


def read_metadata(
    paths: Sequence[Path],
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> dict[Path, dict[str, Any]]:
    """Read the requested tags for ``paths``.

    Files that exiftool cannot parse are simply absent from the result; callers treat
    a missing entry as "no metadata", which flows naturally into the Other category
    and the Undated folder.

    ``progress`` is reported per exiftool batch, and ``cancel`` is checked between them. On a
    large library this phase is minutes of work before anything else starts: a run that
    reports nothing until it is over is indistinguishable from one that has hung, and a
    Cancel button that does nothing until the phase ends is indistinguishable from a broken
    one. Cancelling returns what was read so far -- callers treat a missing entry as "no
    metadata", which is already the normal path for an unparseable file.
    """
    if not paths:
        return {}

    binary = ensure_exiftool()
    collected: dict[Path, dict[str, Any]] = {}
    done = 0

    for chunk in _chunked(paths, BATCH_SIZE):
        if cancel is not None and cancel.is_set():
            break
        if progress is not None:
            progress(Progress(done, len(paths), Phase.SCANNING, Path(chunk[0]).name))
        args = [binary, "-json", "-q", "-m", "-charset", "filename=utf8"]
        args += [f"-{tag}" for tag in REQUESTED_TAGS]
        args += [f"-{tag}#" for tag in _NUMERIC_TAGS]  # signed decimal degrees for GPS
        args += [str(path) for path in chunk]

        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        payload = proc.stdout.strip()
        if not payload:
            continue

        try:
            records = json.loads(payload)
        except json.JSONDecodeError:
            continue

        done += len(chunk)
        for record in records:
            source = record.get("SourceFile")
            if source:
                collected[Path(source)] = record

    return collected
