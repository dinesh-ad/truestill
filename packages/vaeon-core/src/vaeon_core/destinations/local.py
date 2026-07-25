"""Local-filesystem destination.

Used for dry-run previews and as the reference implementation of the interface. Preserves
mtime via ``copy2`` so a capture-date timestamp set on the source propagates through.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from vaeon_core.destinations.base import Destination, DestinationError
from vaeon_core.hashing import sha256_file


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
