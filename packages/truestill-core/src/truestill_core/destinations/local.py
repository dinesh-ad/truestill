"""Local-filesystem destination.

Used for dry-run previews and as the reference implementation of the interface. Preserves
source metadata via ``copy2``; capture-date timestamps are applied to the destination copy.

Filesystem failures surface as :class:`DestinationError` (the ABC contract), never as raw
``OSError``, so callers like ``migrate._matches`` can treat every backend uniformly.
"""

from __future__ import annotations

import errno
import os
import shutil
from datetime import datetime
from pathlib import Path

from truestill_core.destinations.base import CrossDeviceError, Destination, DestinationError
from truestill_core.hashing import sha256_file


class LocalDestination(Destination):
    """Writes into a directory tree rooted at ``root``."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def describe(self) -> str:
        return f"local:{self._root}"

    def _full(self, relative_path: str) -> Path:
        return self._root / relative_path

    def exists(self, relative_path: str) -> bool:
        try:
            return self._full(relative_path).exists()
        except OSError as exc:
            message = f"cannot probe {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def upload(self, local: Path, relative_path: str) -> None:
        target = self._full(relative_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, target)
        except OSError as exc:
            message = f"cannot upload to {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        stamp = captured_at.timestamp()
        try:
            os.utime(self._full(relative_path), (stamp, stamp))
        except OSError as exc:
            message = f"cannot set timestamp on {relative_path!r}: {exc}"
            raise DestinationError(message) from exc

    def adopt(self, local: Path, relative_path: str) -> None:
        """Move ``local`` in with an atomic rename, or raise :class:`CrossDeviceError`.

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
            target.parent.mkdir(parents=True, exist_ok=True)
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
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)  # overwrites a partial copy left by an interrupted run
        except OSError as exc:
            message = f"cannot relocate {old_relative_path!r} -> {new_relative_path!r}: {exc}"
            raise DestinationError(message) from exc

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
