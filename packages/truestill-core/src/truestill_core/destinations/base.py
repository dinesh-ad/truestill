"""The storage-backend interface.

Deliberately tiny and free of any rclone or storage-vendor vocabulary. A destination is addressed by
POSIX-style *relative paths* (``Camera/2025/08/foo.jpg``); how those map onto a real
store -- a local directory, an rclone remote, an object-store key -- is the backend's
private business.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from truestill_core.filesystem import DestinationPreflight, FilesystemFacts


class DestinationError(RuntimeError):
    """A destination operation failed. Backends raise a subclass of this."""


class CrossDeviceError(DestinationError):
    """:meth:`Destination.adopt` could not move a file in without rewriting its bytes.

    Distinct from a plain failure because it is *expected* and recoverable: the caller either
    falls back to the verified copy-then-delete path, or -- when the user asked for in-place
    specifically, because they have no room for a copy -- reports it rather than quietly
    consuming the space they said they did not have.
    """


class Destination(ABC):
    """A place organized files can be written to and checked against."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable identifier for reports (e.g. ``remote:Photos/Backup``)."""

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
    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        """Set an uploaded copy's timestamp without touching the source file."""

    @abstractmethod
    def list(self) -> list[str]:
        """Return every relative path currently present at the destination."""

    # -- optional: what this destination can physically hold ------------------------------

    def facts(self) -> FilesystemFacts:
        """What is known about this destination's storage limits.

        The default is **unknown**, which never refuses anything. A remote has no local
        filesystem to interrogate and no FAT32 ceiling to hit, so guessing on its behalf could
        only refuse work that would have succeeded. Backends addressing a real filesystem
        override this.
        """
        return FilesystemFacts(filesystem=None, max_file_bytes=None)

    def preflight(self, sized: Iterable[tuple[Path, int]]) -> DestinationPreflight:
        """Whether this destination can hold ``(path, size)`` work, before any of it starts.

        Sizes are passed in rather than re-derived because the caller already knows them, and
        because a caller reading sizes from a catalog (backup) must be able to use this too.

        The default stands down **completely** rather than half-guessing: a remote's free space
        is not the local disk's, and answering with `shutil.disk_usage` here would refuse an
        upload to a 10 TB remote because the laptop is full.
        """
        need = sum(size for _path, size in sized)
        return DestinationPreflight(
            facts=self.facts(), oversized=(), need_bytes=need, free_bytes=need
        )

    # -- optional: in-place relocation, used only by layout migration ---------------------
    # Backends that can move and re-hash their own files override these. The default refuses,
    # so `truestill migrate-layout` simply reports the backend as unsupported rather than guessing.

    def adopt(self, local: Path, relative_path: str) -> None:  # noqa: ARG002 - base refuses
        """Take ownership of ``local``, placing it at ``relative_path`` without copying bytes.

        The move counterpart of :meth:`upload`. Backends that can relocate a caller's file into
        themselves (a same-filesystem rename, a server-side move) override this; the default
        refuses, so a backend that cannot simply falls back to copy-then-delete.

        Raises :class:`CrossDeviceError` when the move would require rewriting the bytes --
        that outcome is recoverable and the caller decides what to do about it. As with
        :meth:`upload`, the caller guarantees ``relative_path`` is free.
        """
        message = (
            f"{self.describe()} cannot adopt {relative_path!r}: "
            "this destination does not support moving files in"
        )
        raise DestinationError(message)

    def relocate(self, old_relative_path: str, new_relative_path: str) -> None:
        """Copy ``old`` to ``new`` within the destination (does not remove ``old``)."""
        message = (
            f"{self.describe()} cannot relocate {old_relative_path!r} -> {new_relative_path!r}: "
            "this destination does not support layout migration"
        )
        raise DestinationError(message)

    def remove(self, relative_path: str) -> None:
        """Delete the file at ``relative_path`` (no error if already gone)."""
        message = f"{self.describe()} does not support removing {relative_path!r}"
        raise DestinationError(message)

    def checksum(self, relative_path: str) -> str:
        """Return the SHA-256 of the stored file, for verifying a relocated copy."""
        message = f"{self.describe()} cannot checksum {relative_path!r}"
        raise DestinationError(message)
