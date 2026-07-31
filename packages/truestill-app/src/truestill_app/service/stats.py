"""Library stats: custody-first aggregates from catalog-only SQL."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from truestill_core.catalog import Catalog
from truestill_core.date_explain import explain, explain_evidence
from truestill_core.organizer import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


class DateProvenanceRow(TypedDict):
    """One tier's share of the library, with the evidence behind it."""

    label: str
    detail: str
    files: int
    review: bool
    #: The specific tag/offset that won, when there is one. ``None`` for tiers with no tag.
    evidence: str | None
    #: True for the "not recorded" group. Flagged explicitly so a renderer cannot compute its
    #: share against a total that excludes it - which would print a confident, wrong percentage
    #: for the one group that exists to say "we do not know".
    not_recorded: bool


class DateProvenance(TypedDict):
    """The (n) honesty view: how this library's dates were determined.

    ``recorded`` is the total the percentages are of, and it EXCLUDES the not-recorded group -
    a share of a population that includes "unknown" is not a share of anything.
    """

    rows: list[DateProvenanceRow]
    total: int
    recorded: int
    not_recorded: int


class LibraryStatsDrive(TypedDict):
    label: str
    files: int
    size: int
    last_verified: str | None


class LibraryStatsSafety(TypedDict):
    total_files: int
    total_size: int
    photos: int
    videos: int
    audio: int
    files_on_two_plus_drives: int
    files_on_one_drive: int
    files_on_zero_drives: int
    zero_drive_samples: list[str]
    never_verified_files: int
    drives: list[LibraryStatsDrive]


class LibraryStatsUndatedSample(TypedDict):
    name: str
    source_path: str
    relative: str


class LibraryStatsCompleteness(TypedDict):
    undated_files: int
    undated_samples: list[LibraryStatsUndatedSample]
    timeline_files: int
    side_bin_files: int
    near_duplicates_flagged: int
    exact_duplicates_found: None
    exact_duplicates_omission_reason: str


class LibraryStatsYear(TypedDict):
    year: str
    count: int


class LibraryStatsShape(TypedDict):
    by_year: list[LibraryStatsYear]
    by_format: dict[str, int]
    oldest_capture: str | None
    newest_capture: str | None


class LibraryStats(TypedDict):
    safety: LibraryStatsSafety
    completeness: LibraryStatsCompleteness
    shape: LibraryStatsShape
    #: (n) the honesty view: how this library's dates were determined.
    dates: DateProvenance
    complexity: str


def _date_provenance(catalog: Catalog) -> DateProvenance:
    """Group the persisted provenance into rows a person can read. Read-only, one query.

    Rows are merged by tier and the evidence strings collected per tier, because a user asks
    "how were my dates determined" before "which of the four EXIF tags won" - the tag is the
    second question, so it rides along on the row rather than fragmenting it.
    """
    by_source: dict[str | None, int] = {}
    evidence: dict[str | None, list[str]] = {}
    for row in catalog.stats_date_provenance():
        source = row["date_source"]
        by_source[source] = by_source.get(source, 0) + int(row["files"])
        detail = explain_evidence(source, row["date_tag"])
        if detail is not None:
            evidence.setdefault(source, []).append(detail)

    total = sum(by_source.values())
    not_recorded = by_source.get(None, 0)
    rows: list[DateProvenanceRow] = []
    for source, files in sorted(by_source.items(), key=lambda kv: -kv[1]):
        explanation = explain(source)
        seen = evidence.get(source, [])
        rows.append(
            {
                "label": explanation.label,
                "detail": explanation.detail,
                "files": files,
                # Not-recorded is never review-worthy: it is the ordinary state of every library
                # organized before v13, and flagging it would alarm someone whose dates are fine.
                "review": explanation.review,
                "evidence": ", ".join(sorted(set(seen))[:4]) if seen else None,
                "not_recorded": source is None,
            }
        )
    return {
        "rows": rows,
        "total": total,
        "recorded": total - not_recorded,
        "not_recorded": not_recorded,
    }


def library_stats(db: Path) -> LibraryStats:
    """Custody-first library stats from catalog-only aggregates.

    Complexity: O(n) aggregate scans over ``files``/``file_copies`` plus grouped rollups for
    years and formats. No file reads, no hashing, no exiftool, and no per-file Python loops.
    """
    with Catalog(db) as catalog:
        summary = catalog.stats_summary()
        year_rows = catalog.stats_by_year()
        drives = catalog.list_drives()
        near_flagged = catalog.stats_near_duplicate_flagged_count()
        undated_samples = catalog.stats_undated_samples(limit=12)
        format_counts = catalog.stats_counts_by_format(MEDIA_EXTENSIONS)
        zero_drive_samples = catalog.stats_zero_drive_samples(limit=12)
        dates = _date_provenance(catalog)

    image_exts = {ext.lstrip(".").lower() for ext in IMAGE_EXTENSIONS}
    video_exts = {ext.lstrip(".").lower() for ext in VIDEO_EXTENSIONS}
    audio_exts = {ext.lstrip(".").lower() for ext in AUDIO_EXTENSIONS}
    photos = sum(count for ext, count in format_counts.items() if ext in image_exts)
    videos = sum(count for ext, count in format_counts.items() if ext in video_exts)
    audio = sum(count for ext, count in format_counts.items() if ext in audio_exts)

    return {
        "safety": {
            "total_files": int(summary["total_files"]),
            "total_size": int(summary["total_size"] or 0),
            "photos": photos,
            "videos": videos,
            "audio": audio,
            "files_on_two_plus_drives": int(summary["files_on_two_plus_drives"] or 0),
            "files_on_one_drive": int(summary["files_on_one_drive"] or 0),
            "files_on_zero_drives": int(summary["files_on_zero_drives"] or 0),
            "zero_drive_samples": zero_drive_samples,
            "never_verified_files": int(summary["never_verified_files"] or 0),
            "drives": [
                {
                    "label": str(row["label"]),
                    "files": int(row["file_count"] or 0),
                    "size": int(row["total_size"] or 0),
                    "last_verified": row["last_verified"],
                }
                for row in drives
            ],
        },
        "completeness": {
            "undated_files": int(summary["undated_files"] or 0),
            "undated_samples": [
                {
                    "name": str(row["original_name"] or Path(str(row["source_path"])).name),
                    "source_path": str(row["source_path"]),
                    "relative": str(row["relative"]),
                }
                for row in undated_samples
            ],
            "timeline_files": int(summary["timeline_files"] or 0),
            "side_bin_files": int(summary["side_bin_files"] or 0),
            "near_duplicates_flagged": near_flagged,
            # Exact duplicates are intentionally omitted: skipped exact dupes are not persisted
            # in the catalog, and recomputing them would require a fresh source scan.
            "exact_duplicates_found": None,
            "exact_duplicates_omission_reason": (
                "Exact-duplicate skips are not stored in the catalog; computing this would require "
                "a new scan outside the read-only stats contract."
            ),
        },
        "shape": {
            "by_year": [
                {"year": str(row["year"]), "count": int(row["count"])} for row in year_rows
            ],
            "by_format": format_counts,
            "oldest_capture": summary["oldest_capture"],
            "newest_capture": summary["newest_capture"],
        },
        "dates": dates,
        "complexity": "O(n) aggregate SQL over catalog tables; grouped rollups only.",
    }
