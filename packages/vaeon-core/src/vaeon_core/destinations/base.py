"""The storage-backend interface.

Deliberately tiny and free of any rclone/pCloud vocabulary. A destination is addressed by
POSIX-style *relative paths* (``Camera/2025/08/foo.jpg``); how those map onto a real
store -- a local directory, an rclone remote, an object-store key -- is the backend's
private business.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class DestinationError(RuntimeError):
    """A destination operation failed. Backends raise a subclass of this."""


class Destination(ABC):
    """A place organized files can be written to and checked against."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable identifier for reports (e.g. ``pcloud:Photos/GoogleBackup``)."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Return whether something already lives at ``relative_path``."""

    @abstractmethod
    def upload(self, local: Path, relative_path: str) -> None:
        """Copy ``local`` to ``relative_path``, creating parent structure as needed.

        Implementations must not overwrite silently; the caller guarantees
        ``relative_path`` is free by consulting :meth:`exists` first.
        """

    @abstractmethod
    def list(self) -> list[str]:
        """Return every relative path currently present at the destination."""
