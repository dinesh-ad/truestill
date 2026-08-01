"""Everything a user must be able to decline **before** an archive ingest writes anything ((jj)).

One report, assembled from header reads only, that either clears the way or refuses with the
reason named. Preview-then-confirm, the same discipline as every other path that touches
someone's disk - and here it matters more than usual, because the alternative is discovering the
problem 190 GB into 200.

**Nothing in this module writes, creates a directory, or extracts.** It answers *"may this
proceed, and what will it cost"*, so a user can say no while saying no is still free.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from truestill_core.archive_set import (
    ArchiveInspection,
    ArchiveSet,
    discover_archive_set,
    inspect_archive_set,
    space_for,
)


class ArchiveRefusal(StrEnum):
    """Why an ingest may not start. Each is a distinct thing the user can act on."""

    #: Nothing was selected. Reported rather than succeeding vacuously - "nothing happened" must
    #: never be the report for "you chose nothing".
    NO_ARCHIVES = "no_archives"
    #: A gap in a numbered set. The one that would otherwise produce a library with a hole in it.
    MISSING_PART = "missing_part"
    #: Needs a password. `zipfile` supports legacy ZipCrypto only, never AES, so this is a
    #: refusal with a plain sentence rather than a prompt that would fail confusingly anyway.
    ENCRYPTED = "encrypted"
    #: An archive inside the archive. Refused outright: recursive extraction is unbounded depth
    #: on untrusted input and the Takeout case never needs it.
    NESTED_ARCHIVE = "nested_archive"
    #: A part that could not be opened at all - truncated, corrupt, or not really a zip.
    UNREADABLE = "unreadable"
    #: The destination drive cannot hold what the set claims it will unpack to.
    NOT_ENOUGH_SPACE = "not_enough_space"


@dataclass(frozen=True, slots=True)
class ArchivePrecheck:
    """The whole answer: what it will cost, and every reason it may not proceed."""

    archive_set: ArchiveSet
    inspection: ArchiveInspection
    #: **The archive's own claim**, never a measurement truestill made. See `archive_set`.
    claimed_bytes: int
    free_bytes: int
    media_entries: int
    refusals: tuple[ArchiveRefusal, ...]
    #: What a person reads. Every refusal names the specific entry or part, because
    #: "contains another archive" without saying which one is not actionable.
    detail: str

    @property
    def may_proceed(self) -> bool:
        return not self.refusals


def _describe(
    archive_set: ArchiveSet, inspection: ArchiveInspection, claimed: int, free: int
) -> tuple[tuple[ArchiveRefusal, ...], str]:
    refusals: list[ArchiveRefusal] = []
    lines: list[str] = []

    if not archive_set.parts:
        return (
            (ArchiveRefusal.NO_ARCHIVES,),
            "No archives were selected, so there is nothing to unpack.",
        )

    if archive_set.missing_numbers:
        refusals.append(ArchiveRefusal.MISSING_PART)
        missing = ", ".join(str(n) for n in archive_set.missing_numbers)
        lines.append(
            f"This download is missing part {missing} of {len(archive_set.parts)} found. "
            "Photos and their dates can be split across parts, so unpacking without it would "
            "quietly leave some photos without their real date. Download the missing part first."
        )
    if inspection.unreadable:
        refusals.append(ArchiveRefusal.UNREADABLE)
        lines.append(f"These files could not be opened: {', '.join(inspection.unreadable)}.")
    if inspection.encrypted:
        refusals.append(ArchiveRefusal.ENCRYPTED)
        lines.append(
            f"This archive needs a password: {', '.join(inspection.encrypted[:5])}. "
            "Truestill cannot open password-protected archives - unpack it yourself first."
        )
    if inspection.nested_archives:
        refusals.append(ArchiveRefusal.NESTED_ARCHIVE)
        lines.append(
            f"This archive contains another archive, which Truestill does not open: "
            f"{', '.join(inspection.nested_archives[:5])}. Unpack that one yourself first."
        )
    if free < claimed:
        refusals.append(ArchiveRefusal.NOT_ENOUGH_SPACE)
        lines.append(
            f"Not enough room: the archives claim about {claimed:,} bytes and this drive has "
            f"{free:,} free."
        )

    if not refusals:
        lines.append(
            f"{inspection.media_entries:,} photos and videos in {len(archive_set.parts)} "
            f"file(s). The archives claim about {claimed:,} bytes once unpacked - that is the "
            f"archives' own claim, not a measurement - and this drive has {free:,} free."
        )
    return tuple(refusals), " ".join(lines)


def precheck_archives(paths: Sequence[Path], destination: Path) -> ArchivePrecheck:
    """Read the set's headers and report. **Writes nothing, extracts nothing.**

    ``destination`` is used only to ask its drive how much room is free - it is not created, so
    declining costs the user nothing at all.
    """
    archive_set = discover_archive_set(list(paths))
    inspection = inspect_archive_set(archive_set)
    space = space_for(inspection, destination if destination.exists() else _nearest(destination))
    refusals, detail = _describe(archive_set, inspection, space.claimed_bytes, space.free_bytes)
    return ArchivePrecheck(
        archive_set=archive_set,
        inspection=inspection,
        claimed_bytes=space.claimed_bytes,
        free_bytes=space.free_bytes,
        media_entries=inspection.media_entries,
        refusals=refusals,
        detail=detail,
    )


def _nearest(path: Path) -> Path:
    """The closest existing ancestor, so a not-yet-created destination can still be measured.

    Asking `disk_usage` about a path that does not exist raises; walking up finds the drive the
    destination *will* be on, which is the question actually being asked.
    """
    for candidate in [path, *path.parents]:
        if candidate.exists():
            return candidate
    return Path(path.anchor or ".")
