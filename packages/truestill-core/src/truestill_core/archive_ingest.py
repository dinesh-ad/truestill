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
from truestill_core.filesystem import FilesystemFacts, facts_for

#: How many oversized entries are named before the list is truncated. The rest are counted, the
#: same shape `DestinationPreflight.detail` uses - one habit, not two.
_NAMED_ENTRIES = 5


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
    #: A single member is larger than the destination filesystem can store - FAT32's 4 GiB
    #: ceiling, which 4K video crosses routinely. Caught here because extraction writes to that
    #: drive *before* organize does, so organize's own preflight never gets a turn.
    OVERSIZED_ENTRY = "oversized_entry"


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


def _oversized_line(entries: tuple[tuple[str, int], ...], facts: FilesystemFacts) -> str:
    """Name the members that will not fit, with the count of any beyond the display cap.

    Named rather than counted, and worded the same way `DestinationPreflight.detail` words it:
    a user who meets this through an ingest and through an organize should not have to work out
    that they are the same problem.
    """
    named = ", ".join(
        f"{name} ({size / 1024**3:.1f} GB)" for name, size in entries[:_NAMED_ENTRIES]
    )
    extra = len(entries) - _NAMED_ENTRIES
    more = f" and {extra} more" if extra > 0 else ""
    where = f" ({facts.filesystem})" if facts.known else ""
    return (
        f"These files are too large for this drive{where}: {named}{more}. Drives formatted "
        f"FAT32 cannot hold a single file of 4 GB or more, however much free space they show. "
        f"Unpack to a drive formatted exFAT or NTFS instead."
    )


def _describe(
    archive_set: ArchiveSet,
    inspection: ArchiveInspection,
    claimed: int,
    free: int,
    facts: FilesystemFacts,
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
    if inspection.oversized_entries:
        refusals.append(ArchiveRefusal.OVERSIZED_ENTRY)
        lines.append(_oversized_line(inspection.oversized_entries, facts))
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


#: Every suffix `discover_archive_set` can open. Used to decide whether the thing a user pointed
#: at is "a folder of archives" or "an already-extracted tree".
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tgz", ".tbz2", ".txz", ".tar.gz", ".tar.bz2", ".tar.xz")


def archives_at(path: Path) -> list[Path]:
    """The archive set the user meant, from the one path they gave.

    **One home for "what did the user point at", shared by the CLI and the app**, because a
    surface that resolves this differently from its twin is the drift this repo keeps catching.

    The gesture differs by surface and the *invariant* does not: **the user never enumerates
    parts.** Forgetting one would not fail - it would succeed and quietly leave those photos
    undated - so neither surface ever asks for a list.

    * a **directory** yields the archives inside it (the app's folder picker, and a CLI user who
      points at their Downloads folder);
    * a **file** yields its siblings of the same format (a CLI user who tab-completes one part).

    Returns ``[]`` when there are no archives, which is how a caller distinguishes "a folder of
    archives" from "an already-extracted Takeout tree" without guessing.
    """
    if path.is_dir():
        candidates = sorted(child for child in path.iterdir() if child.is_file())
    elif path.is_file():
        candidates = sorted(sibling for sibling in path.parent.iterdir() if sibling.is_file())
    else:
        return []
    return [c for c in candidates if c.name.lower().endswith(ARCHIVE_SUFFIXES)]


def precheck_archives(paths: Sequence[Path], destination: Path) -> ArchivePrecheck:
    """Read the set's headers and report. **Writes nothing, extracts nothing.**

    ``destination`` is used only to ask its drive two questions - how much room is free, and
    what it can hold in a single file. It is not created, so declining costs the user nothing.

    **The per-file limit is asked here rather than left to organize.** Extraction writes a
    staging tree to this drive *before* organize sees anything, so organize's own preflight
    never gets a turn: a 5 GB video inside the zip would fail part way through the unpack, with
    most of the tree already written. Asking now costs nothing, because the header walk that
    totals the claim already reads each entry's declared size.
    """
    archive_set = discover_archive_set(list(paths))
    facts = facts_for(destination)
    inspection = inspect_archive_set(archive_set, max_file_bytes=facts.max_file_bytes)
    space = space_for(inspection, destination if destination.exists() else _nearest(destination))
    refusals, detail = _describe(
        archive_set, inspection, space.claimed_bytes, space.free_bytes, facts
    )
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
