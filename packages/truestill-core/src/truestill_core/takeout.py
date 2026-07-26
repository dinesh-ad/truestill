"""Google Takeout intake -- pure pre-processing that sits in front of the pipeline.

Takeout scatters each photo's real metadata into a JSON *sidecar*, ships albums as folders
of byte-identical duplicate copies, and names the sidecars inconsistently. This module makes
sense of that without forking any organize/dedup logic: it matches each media file to its
sidecar, parses the authoritative fields, and reports album membership. See
``docs/takeout-format.md`` for the format research this encodes.

Nothing here mutates files or reads pixels. Timestamps are parsed as timezone-aware UTC
(``photoTakenTime`` is epoch-UTC with no local offset) and converted to local wall-clock
exactly once, by the caller, via :func:`local_naive`.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# --- parsed sidecar --------------------------------------------------------------------

GeoPoint = tuple[float, float]


@dataclass(frozen=True, slots=True)
class TakeoutSidecar:
    """The fields we rescue from one Takeout JSON. Times are timezone-aware UTC."""

    taken_at: datetime | None  # photoTakenTime -- authoritative capture time
    created_at: datetime | None  # creationTime -- upload time, approximate fallback
    gps: GeoPoint | None
    description: str = ""


def _epoch_utc(obj: Any) -> datetime | None:
    """Parse a Takeout ``{"timestamp": "<epoch-seconds>"}`` object as aware UTC.

    Explicitly ``tz=UTC`` -- never the naive form, which would silently localize and invite
    a double-conversion when we later shift to the user's timezone.
    """
    if not isinstance(obj, dict):
        return None
    ts = obj.get("timestamp")
    if not isinstance(ts, str | int | float):
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _geo(data: dict[str, Any]) -> GeoPoint | None:
    """GPS from ``geoDataExif`` then ``geoData``. All-zero means absent (not Null Island)."""
    for key in ("geoDataExif", "geoData"):
        block = data.get(key)
        if not isinstance(block, dict):
            continue
        lat, lon = block.get("latitude"), block.get("longitude")
        if isinstance(lat, int | float) and isinstance(lon, int | float) and (lat or lon):
            return (float(lat), float(lon))
    return None


def parse_sidecar(path: Path) -> TakeoutSidecar | None:
    """Parse a sidecar JSON, or None if it is unreadable/not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    description = data.get("description")
    return TakeoutSidecar(
        taken_at=_epoch_utc(data.get("photoTakenTime")),
        created_at=_epoch_utc(data.get("creationTime")),
        gps=_geo(data),
        description=description if isinstance(description, str) else "",
    )


def local_naive(aware_utc: datetime, offset: timedelta | None) -> datetime:
    """Convert an aware-UTC datetime to a naive local wall-clock time, in one conversion.

    ``offset`` None means "treat the UTC clock as the wall clock" (documented default). Any
    real offset shifts once via :meth:`datetime.astimezone`; the result is naive to match the
    rest of vaeon's date model. Near midnight this can move the calendar day -- surfaced in
    the ingest report rather than hidden.
    """
    target = timezone(offset) if offset is not None else UTC
    return aware_utc.astimezone(target).replace(tzinfo=None)


# --- sidecar matching ------------------------------------------------------------------

# A supplemental sidecar, including truncated forms (Google clips the total filename length)
# and a relocated "(n)" duplicate suffix: e.g. foo.jpg.supplemental-metadata.json,
# foo.jpg.supplemental-metada.json, foo.jpg.supplemental-metadata(1).json.
_SUPP_RE = re.compile(r"^(?P<base>.+?)\.supp[a-z-]*(?P<paren>\(\d+\))?\.json$", re.IGNORECASE)

# A media filename carrying Google's "(n)" duplicate suffix before the extension: foo(1).jpg.
_DUP_RE = re.compile(r"^(?P<stem>.*)\((?P<n>\d+)\)(?P<ext>\.[^.]+)$")

_EDITED_SUFFIXES = ("-edited", "-bearbeitet", "-modifié", "-ha editado", "-editado")


def _strip_edited(stem: str) -> str:
    lowered = stem.casefold()
    for suffix in _EDITED_SUFFIXES:
        if lowered.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _media_bases(media_name: str) -> list[str]:
    """Candidate 'base names' a sidecar might be keyed on, best-first.

    Covers: the full name, the extension-stripped stem, their ``-edited``-stripped forms, and
    the relocated ``(n)`` duplicate form (media ``foo(1).jpg`` -> sidecar base ``foo.jpg(1)``).
    """
    dot = media_name.rfind(".")
    stem, ext = (media_name[:dot], media_name[dot:]) if dot > 0 else (media_name, "")
    base_stem = _strip_edited(stem)
    base_full = base_stem + ext
    bases = [media_name, base_full, stem, base_stem]

    dup = _DUP_RE.match(base_full)
    if dup:
        bases.append(f"{dup['stem']}{dup['ext']}({dup['n']})")
    return _dedupe(bases)


class SidecarIndex:
    """All sidecars in one folder, indexed for O(1) lookup by any media file in that folder."""

    def __init__(self, json_names: Iterable[str]) -> None:
        self._exact: set[str] = set()
        self._supplemental: dict[str, str] = {}
        for name in json_names:
            self._exact.add(name)
            match = _SUPP_RE.match(name)
            if match:
                self._supplemental[match["base"] + (match["paren"] or "")] = name

    def find(self, media_name: str) -> str | None:
        """Return the sidecar filename for ``media_name``, or None if there is none."""
        bases = _media_bases(media_name)
        for base in bases:
            candidate = f"{base}.json"
            if candidate in self._exact:
                return candidate
        for base in bases:
            supplemental = self._supplemental.get(base)
            if supplemental is not None:
                return supplemental
        return None


# --- folder scan -----------------------------------------------------------------------

_YEAR_FOLDER_RE = re.compile(r"^Photos from \d{4}$")
_MEDIA_SUFFIXES = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".heic",
        ".heif",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
        ".dng",
        ".raw",
        ".cr2",
        ".cr3",
        ".nef",
        ".arw",
        ".mp4",
        ".mov",
        ".m4v",
        ".3gp",
        ".avi",
        ".mkv",
        ".webm",
        ".mts",
    }
)


def is_year_folder(name: str) -> bool:
    """True for Google's ``Photos from YYYY`` folders (as opposed to album folders)."""
    return bool(_YEAR_FOLDER_RE.match(name))


@dataclass(slots=True)
class TakeoutScan:
    """Result of scanning an extracted Takeout tree."""

    #: media file -> parsed sidecar (only files that matched a readable sidecar)
    sidecars: dict[Path, TakeoutSidecar] = field(default_factory=dict)
    #: media file -> album name, for files found inside an album folder
    albums: dict[Path, str] = field(default_factory=dict)
    #: media files with no sidecar match, for honest reporting
    missing_sidecar: list[Path] = field(default_factory=list)


def scan_takeout(root: Path) -> TakeoutScan:
    """Walk an extracted Takeout directory, matching sidecars and noting album membership.

    Matching is per-folder (Google never cross-references sidecars across folders). Album
    folders are any directory that is not a ``Photos from YYYY`` folder; their name is the
    album title.
    """
    scan = TakeoutScan()
    for folder, _dirs, filenames in os.walk(root):
        folder_path = Path(folder)
        index = SidecarIndex(n for n in filenames if n.lower().endswith(".json"))
        album = None if is_year_folder(folder_path.name) else folder_path.name

        for name in filenames:
            media = folder_path / name
            if media.suffix.lower() not in _MEDIA_SUFFIXES:
                continue
            if album is not None:
                scan.albums[media] = album
            sidecar_name = index.find(name)
            if sidecar_name is None:
                scan.missing_sidecar.append(media)
                continue
            parsed = parse_sidecar(folder_path / sidecar_name)
            if parsed is not None:
                scan.sidecars[media] = parsed
            else:
                scan.missing_sidecar.append(media)
    return scan


# --- ingest execution context ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetadataWrite:
    """Metadata to bake into an organized copy via exiftool (Takeout ingestion only)."""

    taken_at_local: datetime | None
    gps: GeoPoint | None
    description: str = ""

    @property
    def has_content(self) -> bool:
        return self.taken_at_local is not None or self.gps is not None or bool(self.description)


@dataclass(frozen=True, slots=True)
class IngestContext:
    """Per-run ingestion side-inputs to :func:`truestill_core.organizer.execute`.

    Keyed by source path (``str``). ``writes`` requests baking rescued metadata into the copy
    (which makes the copy differ from the byte-identical source -- scoped to ingestion only);
    ``albums`` records album membership per source copy for aggregation across duplicates.
    """

    writes: dict[str, MetadataWrite] = field(default_factory=dict)
    albums: dict[str, str] = field(default_factory=dict)
