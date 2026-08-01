"""Read what a pile of archives claims about itself, before committing to unpacking it ((jj)).

Google Takeout does not hand anyone a folder. It hands them
``takeout-20260801T000000Z-001.zip`` through ``-017.zip``, and what a Takeout refugee actually
has is that pile. Two facts about it can be established by reading central directories alone,
and both are ruinous to discover late:

* **a missing part** - sidecar matching is per-folder and a ``Photos from 2014`` folder can
  straddle two archives, so a set missing ``-009`` yields a library with a hole in it. Silently:
  every individual archive extracts perfectly well.
* **not enough disk** - failing at 190 GB of 200 is not a smaller version of the same problem.

**Nothing here extracts anything.** These functions read headers, so the answer arrives in
seconds and before any commitment. Extraction, and the running byte counter that is the only
real defence against a zip bomb, live elsewhere.

**Complexity: O(entries across the set)**, one central-directory read per archive. No entry is
decompressed and no file is written.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from truestill_core.organizer import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

#: ``<stem>-<NNN>.zip`` - how Takeout splits one export across many files. The stem is everything
#: before the final numeric group, so two unrelated downloads in one folder stay two sources.
_PART = re.compile(r"^(?P<stem>.+)-(?P<number>\d{2,4})$")

#: Extensions truestill will not open **inside** an archive. Recursive extraction is unbounded
#: depth on untrusted input, and the Takeout case never needs it - see `(jj)`.
NESTED_ARCHIVE_EXTENSIONS = frozenset({".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2", ".xz"})

#: What counts as worth extracting. Anything else (JSON sidecars, HTML indexes) still extracts,
#: but this is the number a person can act on - a Takeout is mostly sidecars, so "12,000 entries"
#: tells them nothing.
_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

#: Set on a zip entry that needs a password. `zipfile` supports legacy ZipCrypto only, never AES,
#: so even *with* a password an AES archive fails confusingly - which is why this is a refusal
#: with a plain sentence rather than a prompt.
_ENCRYPTED_FLAG = 0x1


@dataclass(frozen=True, slots=True)
class ArchivePart:
    """One file of a possibly-numbered set."""

    path: Path
    #: ``None`` for a lone unnumbered archive, which is a complete set of one.
    number: int | None


@dataclass(frozen=True, slots=True)
class ArchiveSet:
    """One logical source: the parts of a single export, and what is missing from it."""

    stem: str
    parts: tuple[ArchivePart, ...]
    #: Numbers absent from an otherwise-contiguous run. The whole point of reading headers first.
    missing_numbers: tuple[int, ...] = ()
    #: Every set discovered from the given paths, including this one. Populated by
    #: :func:`discover_archive_set` so a caller that handed over a mixed folder can see that it
    #: was mixed rather than silently ingesting the first group.
    sets: tuple[ArchiveSet, ...] = field(default=(), repr=False)

    @property
    def is_complete(self) -> bool:
        return not self.missing_numbers


@dataclass(frozen=True, slots=True)
class ArchiveInspection:
    """What the set claims about itself, plus the two refusals visible from headers."""

    #: **The archive's own claim, never an enforcement input.** It is the header's declared
    #: uncompressed size, which whoever built the archive chose. It is what the user is *shown*;
    #: what actually stops a zip bomb is a running byte counter during extraction.
    claimed_bytes: int
    entries: int
    #: Photos, videos and audio only. A Takeout is mostly JSON, so this is the actionable number.
    media_entries: int
    #: Entry names that need a password. Detected from the header flag, so it costs nothing.
    encrypted: tuple[str, ...] = ()
    #: Entry names that are themselves archives. Refused rather than descended into.
    nested_archives: tuple[str, ...] = ()
    #: Archives that could not be read at all - corrupt, truncated, or not really a zip.
    unreadable: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SpaceCheck:
    """Whether the destination drive can hold what the set claims it will unpack to."""

    claimed_bytes: int
    free_bytes: int
    enough: bool


def _split_part(path: Path) -> tuple[str, int | None]:
    match = _PART.match(path.stem)
    if match is None:
        return path.stem, None
    return match.group("stem"), int(match.group("number"))


def discover_archive_set(paths: Sequence[Path]) -> ArchiveSet:
    """Group ``paths`` into logical sets and return the largest, with its gaps identified.

    Grouping is by **stem**, so two unrelated downloads sitting in one folder stay two sources
    rather than being merged into one set with imagined missing parts. Every set found is carried
    on :attr:`ArchiveSet.sets`, because "you pointed at a folder containing two exports" is
    something the caller has to be able to say.
    """
    grouped: dict[str, list[ArchivePart]] = {}
    for path in paths:
        stem, number = _split_part(path)
        grouped.setdefault(stem, []).append(ArchivePart(path=path, number=number))

    built: list[ArchiveSet] = []
    for stem, parts in sorted(grouped.items()):
        ordered = tuple(sorted(parts, key=lambda p: (p.number is None, p.number or 0, p.path.name)))
        numbers = sorted(p.number for p in ordered if p.number is not None)
        missing: tuple[int, ...] = ()
        if numbers:
            # Gaps within the observed run only. A set starting at -003 is not assumed to be
            # missing -001 and -002: the user may have downloaded a subset deliberately, and
            # inventing absent parts would be crying wolf on a legitimate choice.
            missing = tuple(n for n in range(numbers[0], numbers[-1] + 1) if n not in set(numbers))
        built.append(ArchiveSet(stem=stem, parts=ordered, missing_numbers=missing))

    if not built:
        return ArchiveSet(stem="", parts=(), sets=())
    largest = max(built, key=lambda s: len(s.parts))
    return ArchiveSet(
        stem=largest.stem,
        parts=largest.parts,
        missing_numbers=largest.missing_numbers,
        sets=tuple(built),
    )


def inspect_archive_set(archive_set: ArchiveSet) -> ArchiveInspection:
    """Read every part's central directory. Decompresses nothing, writes nothing."""
    claimed = 0
    entries = 0
    media = 0
    encrypted: list[str] = []
    nested: list[str] = []
    unreadable: list[str] = []

    for part in archive_set.parts:
        try:
            with zipfile.ZipFile(part.path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    entries += 1
                    claimed += info.file_size
                    suffix = Path(info.filename).suffix.lower()
                    if suffix in _MEDIA_EXTENSIONS:
                        media += 1
                    if suffix in NESTED_ARCHIVE_EXTENSIONS:
                        nested.append(info.filename)
                    if info.flag_bits & _ENCRYPTED_FLAG:
                        encrypted.append(info.filename)
        except (zipfile.BadZipFile, OSError):
            # A part that cannot be opened is a finding, not an exception to propagate: the
            # caller is reporting on a set and needs to name which member is unusable.
            unreadable.append(part.path.name)

    return ArchiveInspection(
        claimed_bytes=claimed,
        entries=entries,
        media_entries=media,
        encrypted=tuple(encrypted),
        nested_archives=tuple(nested),
        unreadable=tuple(unreadable),
    )


def space_for(
    inspection: ArchiveInspection, destination: Path, *, free_bytes: int | None = None
) -> SpaceCheck:
    """Whether ``destination``'s drive can hold what the set claims.

    Staging goes on the destination drive rather than the system temp directory, so this is a
    question about the drive the user already chose - and on many machines ``/tmp`` is a tmpfs or
    a small partition, where a 200 GB export fails in the least informative way available.

    ``free_bytes`` is injectable so the refusal path can be tested without filling a disk.
    """
    free = shutil.disk_usage(destination).free if free_bytes is None else free_bytes
    return SpaceCheck(
        claimed_bytes=inspection.claimed_bytes,
        free_bytes=free,
        enough=free >= inspection.claimed_bytes,
    )
