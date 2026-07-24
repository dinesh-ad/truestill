"""Local-filesystem destination.

Used for dry-run previews and as the reference implementation of the interface. Preserves
mtime via ``copy2`` so a capture-date timestamp set on the source propagates through.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from vaeon_core.destinations.base import Destination


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

    def list(self) -> list[str]:
        if not self._root.exists():
            return []
        return [
            str(path.relative_to(self._root))
            for path in sorted(self._root.rglob("*"))
            if path.is_file()
        ]
