"""Unpack an archive set into staging, refusing rather than rewriting, and survivably ((jj)).

**Extraction is forced, not chosen.** exiftool is a subprocess that needs a real file, and
hashing, EXIF reading and copying all assume one - so a pure stream cannot feed the pipeline.
The design question was never whether to extract but *where, with what protections*.

**The journal is written and flushed BEFORE any byte of the staging tree exists.** The other
order leaves files the journal does not know about, which is the orphaned-200 GB case wearing a
different hat: an unattributable directory on the drive the user just filled. Everything written
lives under the journalled root, so "a crash left something" always has an answer.

**Entry names are refused, never rewritten.** `zipfile.extractall` silently turns ``../../x``
into ``x`` - safe, but lossy. A Takeout does not contain such a name, so its presence is a signal
worth reporting. Streaming forces our own validation anyway: the running byte counter needs
`open()` per entry, so ``extractall``'s sanitising is not on this path at all.

**The counter aborts on the REAL running total, never the declared one** - see
:func:`staging_budget` for where the budget comes from and why.

**Complexity: O(bytes extracted)**, streamed in fixed chunks. Nothing is read whole into memory.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from truestill_core.archive_set import ArchiveSet

#: Directory under the destination that holds every staging tree. On the destination drive
#: rather than the system temp directory: on many machines ``/tmp`` is a tmpfs or a small
#: partition, where a 200 GB export fails in the least informative way available - and staging
#: beside the library means the organize step can rename rather than copy.
STAGING_DIRNAME = ".truestill-staging"

#: Read/write size. Large enough to keep syscall overhead off a 200 GB export, small enough that
#: the byte counter stops a bomb promptly rather than after a huge buffer.
CHUNK_BYTES = 1024 * 1024

#: Kept free when sizing the budget, so a refused export leaves a usable machine rather than a
#: full disk. A refusal that bricks the desktop is not a safety feature.
SPACE_RESERVE_BYTES = 1024 * 1024 * 1024

#: How far past its own claim an archive may expand before it is treated as a bomb. This works
#: **because** the attacker must under-claim to get past the space precondition
#: (`archive_set.space_for`): claiming honestly means refusal up front, so under-claiming and
#: over-expanding is the only route left - and it is exactly what this catches. The slack covers
#: ordinary header imprecision, not a factor of a thousand.
CLAIM_TOLERANCE = 1.10


class ExtractionRefusedError(RuntimeError):
    """Raised when an archive asks for something truestill will not do."""


@dataclass(frozen=True, slots=True)
class StagingRecord:
    """One journalled staging tree, readable by a process that never saw the extraction."""

    journal_path: Path
    staging_root: Path
    source_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    staging_root: Path
    files_written: int
    bytes_written: int


def staging_budget(destination: Path, *, claimed_bytes: int) -> int:
    """How many bytes an extraction may write before it is aborted.

    **Stated rather than picked silently, because each candidate is defensible and they are not
    equivalent.** A fixed constant is wrong for both a 1 GB and a 500 GB export. A multiple of
    the claimed size alone is attacker-influenced, since the claim is a header field. So the
    budget is the *lower* of two independent limits:

    * **free space now, minus a reserve** - the physical truth, which no archive can influence,
      and the reserve keeps the machine usable when an export is refused;
    * **the claim plus a small tolerance** - which is meaningful precisely *because* an honest
      claim is refused up front by the space precondition when it does not fit. Under-claiming is
      the only way past that gate, and over-expanding is then the signal.

    Either alone has a gap: free space would let a bomb fill a large disk, and the claim ratio
    would be meaningless without the up-front gate. Together they close each other's.
    """
    free = shutil.disk_usage(destination).free
    physical = max(0, free - SPACE_RESERVE_BYTES)
    declared = int(claimed_bytes * CLAIM_TOLERANCE)
    return min(physical, declared)


def _validate_entry_name(name: str) -> PurePosixPath:
    """The name an entry may be written under, or a refusal naming it.

    Refuses rather than sanitising: truestill is not trying to salvage a hostile archive, and a
    silently rewritten path is a name the user was never told about.
    """
    if name.startswith(("/", "\\")):
        message = f"{name!r} is an absolute path, which truestill will not extract"
        raise ExtractionRefusedError(message)
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        message = f"{name!r} points outside the folder it is being extracted into"
        raise ExtractionRefusedError(message)
    # Windows drive-relative and UNC forms, which PurePosixPath does not recognise as absolute.
    if ":" in relative.parts[0] if relative.parts else False:
        message = f"{name!r} names a drive, which truestill will not extract"
        raise ExtractionRefusedError(message)
    return relative


def _refuse_symlink(info: zipfile.ZipInfo) -> None:
    """`zipfile` happens to write symlink entries as ordinary files; we refuse them instead.

    Relying on that accident would mean a future Python could turn a refused entry into a link
    that writes through to somewhere else - so it is a decision here rather than a coincidence
    elsewhere. `test_archive_extract` pins the stdlib behaviour separately.
    """
    if stat.S_ISLNK(info.external_attr >> 16):
        message = f"{info.filename!r} is a shortcut, which truestill will not extract"
        raise ExtractionRefusedError(message)


def _write_journal(destination: Path, archive_set: ArchiveSet) -> StagingRecord:
    """Record the staging tree **before** it holds anything, and flush it to disk.

    ``fsync`` rather than a plain close: a crash between the write and the flush would leave
    exactly the state this exists to prevent - bytes on disk that no journal describes.
    """
    root = destination / STAGING_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    run = root / archive_set.stem
    journal = root / f"{archive_set.stem}.json"
    payload = {
        "staging_root": str(run),
        "sources": [part.path.name for part in archive_set.parts],
    }
    with journal.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    return StagingRecord(
        journal_path=journal,
        staging_root=run,
        source_names=tuple(part.path.name for part in archive_set.parts),
    )


def pending_staging(destination: Path) -> list[StagingRecord]:
    """Staging trees a previous run left behind, found from the destination path alone.

    Deliberately needs nothing but the path: a state only the original process could interpret is
    not recovery. A fresh process - the next launch, after a power cut - calls this and can both
    name what is there and clear it.
    """
    root = destination / STAGING_DIRNAME
    if not root.is_dir():
        return []
    records: list[StagingRecord] = []
    for journal in sorted(root.glob("*.json")):
        try:
            payload = json.loads(journal.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records.append(
            StagingRecord(
                journal_path=journal,
                staging_root=Path(str(payload["staging_root"])),
                source_names=tuple(str(name) for name in payload.get("sources", [])),
            )
        )
    return records


def clear_staging(record: StagingRecord) -> None:
    """Remove a staging tree and its journal. The tree goes first.

    If the journal went first, a crash between the two would leave the tree unattributable
    again - the same ordering argument as writing the journal before the bytes, in reverse.
    """
    shutil.rmtree(record.staging_root, ignore_errors=True)
    record.journal_path.unlink(missing_ok=True)


def extract_archive_set(
    archive_set: ArchiveSet,
    destination: Path,
    *,
    budget_bytes: int | None = None,
    on_entry: Callable[[Path], None] | None = None,
) -> ExtractionResult:
    """Extract every part into one merged staging tree under ``destination``.

    **One tree for the whole set**, because sidecar matching is per-folder and a
    ``Photos from 2014`` folder can straddle two archives - merging first is what makes the
    existing `takeout.scan_takeout` work unchanged.
    """
    record = _write_journal(destination, archive_set)
    record.staging_root.mkdir(parents=True, exist_ok=True)

    claimed = 0
    for part in archive_set.parts:
        with zipfile.ZipFile(part.path) as archive:
            claimed += sum(info.file_size for info in archive.infolist() if not info.is_dir())
    budget = (
        staging_budget(destination, claimed_bytes=claimed) if budget_bytes is None else budget_bytes
    )

    written = 0
    files = 0
    for part in archive_set.parts:
        with zipfile.ZipFile(part.path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                _refuse_symlink(info)
                relative = _validate_entry_name(info.filename)
                target = record.staging_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)

                # Written to a sibling and renamed: an aborted run must never leave a truncated
                # JPEG where a whole one belongs, because a truncated file still hashes.
                partial = target.with_name(target.name + ".partial")
                with archive.open(info) as source, partial.open("wb") as sink:
                    while chunk := source.read(CHUNK_BYTES):
                        written += len(chunk)
                        if written > budget:
                            partial.unlink(missing_ok=True)
                            message = (
                                f"{part.path.name} expands to more than the "
                                f"{budget} bytes this extraction is allowed - refusing rather "
                                f"than filling the disk"
                            )
                            raise ExtractionRefusedError(message)
                        sink.write(chunk)
                partial.replace(target)
                files += 1
                if on_entry is not None:
                    on_entry(target)

    return ExtractionResult(
        staging_root=record.staging_root, files_written=files, bytes_written=written
    )
