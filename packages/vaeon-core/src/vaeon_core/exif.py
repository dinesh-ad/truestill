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
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

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


def read_metadata(paths: Sequence[Path]) -> dict[Path, dict[str, Any]]:
    """Read the requested tags for ``paths``.

    Files that exiftool cannot parse are simply absent from the result; callers treat
    a missing entry as "no metadata", which flows naturally into the Other category
    and the Undated folder.
    """
    if not paths:
        return {}

    binary = ensure_exiftool()
    collected: dict[Path, dict[str, Any]] = {}

    for chunk in _chunked(paths, BATCH_SIZE):
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

        for record in records:
            source = record.get("SourceFile")
            if source:
                collected[Path(source)] = record

    return collected
