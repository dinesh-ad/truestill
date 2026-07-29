"""Local-filesystem destination.

Used for dry-run previews and as the reference implementation of the interface. Preserves
source metadata via ``copy2``; capture-date timestamps are applied to the destination copy.
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
        return self._full(relative_path).exists()

    def upload(self, local: Path, relative_path: str) -> None:
        target = self._full(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local, target)

    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        stamp = captured_at.timestamp()
        os.utime(self._full(relative_path), (stamp, stamp))

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
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            local.rename(target)
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                message = f"{local} and {target} are on different filesystems"
                raise CrossDeviceError(message) from exc
            raise

    def relocate(self, old_relative_path: str, new_relative_path: str) -> None:
        source = self._full(old_relative_path)
        if not source.is_file():
            message = f"cannot relocate missing copy: {old_relative_path}"
            raise DestinationError(message)
        target = self._full(new_relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)  # overwrites a partial copy left by an interrupted run

    def remove(self, relative_path: str) -> None:
        self._full(relative_path).unlink(missing_ok=True)

    def checksum(self, relative_path: str) -> str:
        return sha256_file(self._full(relative_path))

    def list(self) -> list[str]:
        if not self._root.exists():
            return []
        # POSIX-separated to honour the Destination contract on every OS (matches the rclone
        # backend); the same relative form upload()/exists() accept.
        return [
            path.relative_to(self._root).as_posix()
            for path in sorted(self._root.rglob("*"))
            if path.is_file()
        ]
