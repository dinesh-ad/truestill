"""Local-filesystem destination.

Used for dry-run previews and as the reference implementation of the interface. Preserves
source metadata via ``copy2``; capture-date timestamps are applied to the destination copy.

Filesystem failures surface as :class:`DestinationError` (the ABC contract), never as raw
``OSError``, so callers like ``migrate._matches`` can treat every backend uniformly.
"""

from __future__ import annotations

import errno
import os
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from stat import S_ISREG

from truestill_core.destinations.base import (
    CrossDeviceError,
    Destination,
    DestinationDevice,
    DestinationError,
    check_contained,
)
from truestill_core.drive_unwritable import (
    explain_unwritable_drive,
    metadata_not_preserved_note,
)
from truestill_core.filesystem import (
    DestinationPreflight,
    FilesystemFacts,
    facts_for,
    preflight_destination,
)
from truestill_core.hashing import sha256_file
from truestill_core.path_reach import Reach, reach
from truestill_core.safe_copy import CopyOutcome, copy_leaving_nothing

#: ``EFBIG``. Raised when a file exceeds what the filesystem can store - on FAT32, anything from
#: 4 GiB up. Named separately because the bare message, "File too large" against a drive with
#: 200 GB free, reads as Truestill being broken rather than as the drive being FAT32.
_FILE_TOO_LARGE = errno.EFBIG


def _upload_failure(local: Path, target: Path, relative_path: str, outcome: CopyOutcome) -> str:
    """The sentence a user reads when a copy fails, with the FAT32 case named rather than passed
    through as an errno.

    ``target`` is the **full** destination path, not the relative one: the filesystem is a
    property of where the file is being written, and asking about a relative path would
    interrogate the current working directory instead.
    """
    if outcome.leftover is not None:
        # The cleanup could not run either - usually the same fault that produced the partial.
        # A user who watched 800 MB cross a slow link is told what is on their disk and where,
        # rather than left to find it with `rescan`.
        left = (
            f" {outcome.leftover_bytes:,} bytes of it are still at {outcome.leftover}, "
            "and could not be removed."
        )
    else:
        left = ""
    exc = outcome.error
    if exc is not None and exc.errno == _FILE_TOO_LARGE:
        facts = facts_for(target.parent)
        formatted = f" ({facts.filesystem})" if facts.known else ""
        return (
            f"{local.name} is too large for this drive{formatted}. Drives formatted FAT32 "
            f"cannot hold a single file of 4 GB or more, however much free space they show. "
            f"Copy this file to a drive formatted exFAT or NTFS, or reformat this one.{left}"
        )
    # ⚠ **TWO §9 VIOLATIONS LIVED IN THIS ONE LINE**, and the rule against each was already
    # written down elsewhere. `(aep)`
    #
    # 1. *"upload"* is **backend vocabulary**. It is honest inside the code, where
    #    `Destination.upload` covers rclone remotes, and false on screen: it names an event that
    #    did not happen and contradicts the promise that files never leave the machine.
    #    `cli._print_execution` states this in a comment eighteen lines above the `print` that
    #    emitted it.
    # 2. The **raw errno reached the user**. `[Errno 13] Permission denied: '/.../dest3/Saved'` is
    #    an errno, a path the user did not name, and no advice. The `EFBIG` branch above strips it
    #    and is pinned for that; this fall-through passed `{exc}` through untouched.
    #
    # The reads have carried `models.unreadable_label` for this since `(aac)`; the writes had no
    # equivalent. **`drive_unwritable` is that equivalent and already existed** - `(aek)` built it
    # for the two writes that reach a user's own drive, and it is the product's only errno table
    # on purpose, so the fix is to REACH it rather than to write a second one here.
    if exc is None:
        # Unreachable from `upload`, which asserts an error before calling - kept because the
        # honest answer to "no reason was recorded" is to say so rather than invent one. The same
        # choice `run_record.stop_block` makes about a run that stopped without saying why.
        return (
            f"could not copy {local.name!r} to {relative_path!r}, and no reason was recorded{left}"
        )
    # `{local.name!r}`, quoted, so `cli._reason_key` collapses one condition to one reason (`(aiv)`).
    return (
        f"could not copy {local.name!r} to {relative_path!r}: {explain_unwritable_drive(exc)}{left}"
    )


class LocalDestination(Destination):
    """Writes into a directory tree rooted at ``root``."""

    def __init__(self, root: Path) -> None:
        self._root = root
        #: Latched on the first write. A drive that disappears mid-run must not have its folder
        #: tree rebuilt on the local disk -- see `DestinationDevice`.
        self._device = DestinationDevice()

    def describe(self) -> str:
        return f"local:{self._root}"

    def local_root(self) -> Path:
        """The tree this backend writes into - the ground a long run stands on."""
        return self._root

    def _make_parent(self, target: Path) -> None:
        """Create ``target``'s folder, unless the drive we started on has gone.

        Every creating path goes through here rather than calling ``mkdir`` itself, so the
        guard cannot reach one write path and miss its twin.
        """
        self._device.check(self._root)
        target.parent.mkdir(parents=True, exist_ok=True)

    def _full(self, relative_path: str) -> Path:
        """The absolute path for ``relative_path``, refused if it could leave the root.

        The check lives here rather than at each caller because ``_full`` is the single place
        this backend turns a relative path into a real one -- ``exists``, ``upload``,
        ``set_timestamp``, ``adopt``, ``relocate`` and ``remove`` all come through it, so one
        guard covers every write instead of six that have to be kept in step.
        """
        check_contained(relative_path)
        return self._root / relative_path

    def facts(self) -> FilesystemFacts:
        """What the destination filesystem can hold. Detected once, per call site."""
        return facts_for(self._root)

    def preflight(self, sized: Iterable[tuple[Path, int]]) -> DestinationPreflight:
        return preflight_destination(sized, self._root, facts=self.facts())

    def exists(self, relative_path: str) -> bool:
        """Whether the destination already holds this path. Refusal is raised, never reported.

        ⚠ **`reach`, not `exists()`.** This deliberately raises rather than answering `False`,
        because a destination that will not describe itself has not established that the slot is
        free - and the caller's next move is to write into it. On Python 3.14 `Path.exists()`
        stopped raising on ``EACCES``, so this `except` stopped firing and the write path was told
        the slot was empty. `(aey)`
        """
        found = reach(self._full(relative_path))
        if found is Reach.REFUSED:
            message = f"cannot probe {relative_path!r}: the filesystem refused to describe it"
            raise DestinationError(message)
        return found is not Reach.MISSING

    def upload(self, local: Path, relative_path: str) -> str | None:
        target = self._full(relative_path)
        try:
            self._make_parent(target)
        except OSError as exc:
            # The same two violations as `_upload_failure`'s fall-through, on the sibling path
            # that fails **before** any bytes move: making the folder. Worded from the one table
            # rather than restated, or the two would drift the first time either was corrected.
            message = (
                f"could not make the folder for {relative_path!r}: {explain_unwritable_drive(exc)}"
            )
            raise DestinationError(message) from exc
        # The bytes take this name only once they are all there - `(abu)`, `(acj)`. The copy
        # goes to a sibling and is renamed on, so a failure cannot leave a truncated file wearing
        # an organized name. Nothing here has to decide whether a file at the target is ours,
        # because the target is never written except by the rename.
        outcome = copy_leaving_nothing(local, target)
        if not outcome.ok:
            assert outcome.error is not None
            raise DestinationError(
                _upload_failure(local, target, relative_path, outcome)
            ) from outcome.error
        if outcome.metadata_error is not None:
            # ⚠ **Returned, not raised, and that is the whole of `(aie)`.** The bytes are at
            # `target` and verify against the source; only `copystat` was refused. Raising here
            # would put a complete photograph on the failure path, where the caller deletes it.
            return metadata_not_preserved_note(local.name, relative_path, outcome.metadata_error)
        return None

    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        stamp = captured_at.timestamp()
        try:
            os.utime(self._full(relative_path), (stamp, stamp))
        except OSError as exc:
            message = f"cannot set timestamp on {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def adopt(self, local: Path, relative_path: str) -> None:
        """Move ``local`` in with a rename, or raise :class:`CrossDeviceError`.

        **What "atomic" means here, and where it stops.** The rename is atomic with respect to
        other processes on every filesystem truestill runs on: nothing ever observes the file at
        neither path. It is atomic across a **crash** only where the filesystem journals its
        metadata - ext4, APFS, NTFS, btrfs. FAT32 and exFAT journal nothing, so a power cut
        during the directory-entry update can leave the entry in neither place with the clusters
        orphaned. The undo journal (``inplace_moves``) is what covers that case, not the rename.

        **The never-overwrite invariant does not come from this call.** POSIX ``os.rename``
        *silently destroys* an existing destination (measured: no error, no warning); Windows
        raises instead. The guarantee lives in ``organizer._free_relative``, which resolves
        collisions by content hash before this is ever reached. There is a TOCTOU window
        between that check and this rename -- empty for truestill itself, whose execute loop is
        sequential and single-threaded, but not against another process on the machine.
        Closing it properly needs ``renameat2(RENAME_NOREPLACE)``, which is Linux-only and
        absent from the stdlib.

        Device identity is never predicted -- ``st_dev`` can agree across btrfs subvolumes and
        bind mounts where a rename still fails. The kernel is asked, and its answer is final.
        """
        target = self._full(relative_path)
        try:
            self._make_parent(target)
            local.rename(target)
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                message = f"{local} and {target} are on different filesystems"
                raise CrossDeviceError(message) from exc
            message = f"cannot adopt into {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def relocate(self, old_relative_path: str, new_relative_path: str) -> None:
        source = self._full(old_relative_path)
        if not source.is_file():
            message = f"cannot relocate missing copy: {old_relative_path}"
            raise DestinationError(message)
        target = self._full(new_relative_path)
        try:
            self._make_parent(target)
        except OSError as exc:
            message = f"cannot relocate {old_relative_path!r} -> {new_relative_path!r}: {exc}"
            raise DestinationError(message) from exc
        # Still overwrites a copy left by an interrupted run - that is why the target may
        # legitimately exist here, and it is now the rename that does it rather than a truncating
        # copy. `Path.replace` is what makes that work on Windows too; see `StagedCopy.commit`.
        outcome = copy_leaving_nothing(source, target)
        if not outcome.ok:
            assert outcome.error is not None
            left = (
                f" {outcome.leftover_bytes:,} bytes are still at {outcome.leftover} and could "
                "not be removed."
                if outcome.leftover is not None
                else ""
            )
            message = (
                f"cannot relocate {old_relative_path!r} -> {new_relative_path!r}: "
                f"{outcome.error}{left}"
            )
            raise DestinationError(message) from outcome.error

    def remove(self, relative_path: str) -> None:
        try:
            self._full(relative_path).unlink(missing_ok=True)
        except OSError as exc:
            message = f"cannot remove {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def checksum(self, relative_path: str) -> str:
        try:
            return sha256_file(self._full(relative_path))
        except OSError as exc:
            message = f"cannot checksum {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def sizes(self) -> Mapping[str, int]:
        """Relative path -> byte size, from the walk that :meth:`list` already does.

        ⚠ **The stat is not extra.** ``rglob`` + ``is_file()`` stats every entry to answer
        "is this a file"; ``st_size`` comes out of the same call. `(aja)`

        **A file that cannot be stat'd is omitted rather than guessed at**, which reads to a
        caller as "no evidence for this path" - the same answer as absence, and the safe one:
        it can only cause a re-copy, never a skip.
        """
        found: dict[str, int] = {}
        try:
            if not self._root.exists():
                return found
            for path in self._root.rglob("*"):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if S_ISREG(stat.st_mode):
                    found[path.relative_to(self._root).as_posix()] = stat.st_size
        except OSError:
            return found
        return found

    def list(self) -> list[str]:
        try:
            if not self._root.exists():
                return []
            # POSIX-separated to honour the Destination contract on every OS (matches the rclone
            # backend); the same relative form upload()/exists() accept.
            return [
                path.relative_to(self._root).as_posix()
                for path in sorted(self._root.rglob("*"))
                if path.is_file()
            ]
        except OSError as exc:
            message = f"cannot list {self._root}: {exc}"
            raise DestinationError(message) from exc
