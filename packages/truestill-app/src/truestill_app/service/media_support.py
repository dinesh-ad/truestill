"""Shared photo/video/audio tallies from file names.

Used by Drives, library custody status, Backup, and Organize summaries.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from truestill_core.organizer import media_kind


class MediaBreakdown(TypedDict):
    """Photo / video / audio counts plus per-extension tallies."""

    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]


def media_breakdown(names: Iterable[str]) -> MediaBreakdown:
    """Split file names into photos / videos / audio counts and per-extension formats."""
    plural = {"photo": "photos", "video": "videos", "audio": "audio"}
    counts = {"photos": 0, "videos": 0, "audio": 0}
    fmt: dict[str, Counter[str]] = {"photos": Counter(), "videos": Counter(), "audio": Counter()}
    for name in names:
        kind = media_kind(name)
        if kind is None:
            continue
        group = plural[kind]
        counts[group] += 1
        fmt[group][Path(name).suffix.lower().lstrip(".")] += 1
    return {
        "photos": counts["photos"],
        "videos": counts["videos"],
        "audio": counts["audio"],
        "by_format": {g: dict(c.most_common()) for g, c in fmt.items()},
    }
