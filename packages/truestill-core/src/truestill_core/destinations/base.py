"""The storage-backend interface.

Deliberately tiny and free of any rclone or storage-vendor vocabulary. A destination is addressed by
POSIX-style *relative paths* (``Camera/2025/08/foo.jpg``); how those map onto a real
store -- a local directory, an rclone remote, an object-store key -- is the backend's
private business.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

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


def device_of(path: Path) -> int | None:
    """The filesystem device id for ``path``, or ``None`` when it cannot be read.

    Read through this one function so a test can inject a change no test could stage for real:
    dropping an actual mount needs privileges and a real cloud client.
    """
    try:
        return path.stat().st_dev
    except OSError:
        return None


class DestinationDevice:
    """Latches the destination root's filesystem, and refuses to build on a different one.

    **The failure this exists for.** A cloud FUSE mount that drops under load leaves its
    mountpoint as an ordinary empty directory. Writes into it succeed, and because every write
    path calls ``mkdir(parents=True, exist_ok=True)`` first, Truestill would **rebuild the whole
    library tree on the local disk** and fill it - the exact outcome observed on a real
    migration. Refusing to *create* is what stops that, so the guard sits in front of the
    ``mkdir`` rather than in front of the copy.

    **Why the device and not the mount table.** The same migration found a dead mount lingering
    in the table with no process behind it, listing nothing - so the table can say "mounted"
    when it is not. A mount *is* a filesystem, so losing it changes the root's device id. It
    also works for a destination that was never a registered drive, which a marker cannot.

    **The baseline latches on the first real sighting**, not at construction: organizing into a
    folder Truestill is about to create is ordinary, and there is nothing to compare against
    until the folder exists. Once a device is seen, any later disagreement - including the root
    becoming unreadable - is refused. ``None`` is a changed answer, not an absence of opinion.
    """

    def __init__(self) -> None:
        self._baseline: int | None = None

    @property
    def baseline(self) -> int | None:
        """The device this destination was first seen on, or ``None`` before the first sighting."""
        return self._baseline

    def check(self, root: Path) -> None:
        """Raise :class:`DestinationError` if ``root`` is no longer the filesystem we started on."""
        current = device_of(root)
        if self._baseline is None:
            self._baseline = current
            return
        if current == self._baseline:
            return
        message = (
            f"{root} is no longer the drive this run started on -- it looks like the drive was "
            f"disconnected or unmounted. Nothing was written for this file, and Truestill did "
            f"not re-create the folders on this computer's own disk, which would have filled "
            f"it. Reconnect the drive and run again; Truestill continues from where it stopped."
        )
        raise DestinationError(message)


def check_contained(relative_path: str) -> None:
    """Raise unless ``relative_path`` can only ever land inside the destination root.

    A backend joins this onto its root, and neither of the two ways of doing that defends
    itself: ``Path.__truediv__`` **replaces** the left side entirely when the right is
    absolute, and an f-string join carries ``..`` straight through. Until now the invariant
    held only because every relative path truestill builds ends in a ``Path.name`` from a
    filesystem walk, which is always one safe component - a property of today's callers rather
    than of the destination, and therefore one refactor from being false.

    **Lexical on purpose, and this is a deliberate departure from the usual advice.** The
    standard remedy is ``resolve()`` then ``is_relative_to()``. That would be wrong here:
    ``resolve()`` follows symlinks, so a library with a year folder symlinked onto a second
    disk resolves outside its own root and would be **falsely refused** - breaking a real
    setup to defend against a threat we do not have. The relative path is generated by us from
    a filesystem walk, never supplied by an untrusted caller, so the question is "could this
    string escape a join", which is answerable without touching the disk. No ``stat``, no
    symlink resolution, and the same verdict on every platform for the same input.

    Both separators are examined regardless of host, because a path built on Linux can be
    written to a drive read on Windows: ``PureWindowsPath`` treats ``\\`` as a separator and
    ``C:x`` as drive-relative, and a check that only ran ``PurePosixPath`` would pass both.
    """
    for flavour in (PurePosixPath, PureWindowsPath):
        candidate = flavour(relative_path)
        if candidate.is_absolute() or candidate.anchor or candidate.drive:
            message = f"destination path {relative_path!r} is not relative; refusing to write"
            raise DestinationError(message)
        if any(part == ".." for part in candidate.parts):
            message = f"destination path {relative_path!r} would leave the destination root"
            raise DestinationError(message)


class Destination(ABC):
    """A place organized files can be written to and checked against."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable identifier for reports (e.g. ``remote:Photos/Backup``)."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Return whether something already lives at ``relative_path``."""

    @abstractmethod
    def upload(self, local: Path, relative_path: str) -> str | None:
        """Copy ``local`` to ``relative_path``, creating parent structure as needed.

        Implementations must not overwrite silently; the caller guarantees
        ``relative_path`` is free by consulting :meth:`exists` first.

        ⚠ **Returns a warning, never a status.** ``None`` is the ordinary answer and means the
        copy is complete. A string means **the copy is complete too** and something about it is
        worth saying out loud - today, only that the destination refused its timestamps or
        permissions (`(aie)`). A backend that cannot fail this way returns ``None`` and needs no
        branch. **Failure is still an exception**: a return value that could mean either would
        put the decision back in every caller, which is what
        :class:`~truestill_core.destinations.base.DestinationError` exists to prevent.
        """

    @abstractmethod
    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        """Set an uploaded copy's timestamp without touching the source file."""

    @abstractmethod
    def list(self) -> list[str]:
        """Return every relative path currently present at the destination."""

    # -- optional: how big is each file that is there? -------------------------------------

    def sizes(self) -> Mapping[str, int] | None:
        """Relative path -> byte size for everything present, or ``None`` when unknown.

        ⚠ **This is free where it is available, which is why it exists.** A backend that can
        enumerate paths has already stat'd them to know they are files - ``rescan``'s PLACED rule
        costs out that walk at ~14 s for 33,000 files against ~15 h to hash the same library - so
        carrying ``st_size`` out of the stat that already happened adds nothing.

        **``None`` means "I cannot answer cheaply", never "everything is fine".** Callers must
        treat it as no evidence and keep the behaviour they had. `(aja)`
        """
        return None

    # -- optional: is there local ground under this destination to watch? -----------------

    def local_root(self) -> Path | None:
        """The local filesystem path this destination writes into, or ``None``.

        Used by a long run to notice the drive going away underneath it. The default is
        ``None`` - **stand down completely**, the same bargain :meth:`preflight` makes and for
        the same reason: a remote has no local filesystem, so it has no device id to lose, and
        the only thing a guess could do on its behalf is stop work that would have succeeded.
        Backends addressing a real filesystem override this.
        """
        return None

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
