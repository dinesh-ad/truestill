"""rclone-backed destination.

Wraps the ``rclone`` CLI, so any remote rclone supports -- pCloud, Dropbox, S3, SFTP,
Google Drive -- is usable through the same :class:`Destination` interface without this
project knowing anything provider-specific. The remote is given as an rclone spec such as
``remote:Photos/Backup``.

Files are written with ``copyto`` and their capture-date mtime is set with ``touch --no-create``.
There is deliberately no code path here that can remove data at the remote.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from truestill_core import binaries
from truestill_core.destinations.base import Destination, DestinationError


class RcloneError(DestinationError):
    """An rclone invocation failed."""


class RcloneDestination(Destination):
    """Reads and writes an rclone remote via the ``rclone`` binary."""

    def __init__(self, remote: str, *, binary: str = "rclone") -> None:
        resolved = shutil.which(binary)
        if resolved is None:
            message = f"rclone binary not found on PATH (looked for {binary!r})"
            raise RcloneError(message)
        self._bin = resolved
        self._remote = remote.rstrip("/")
        self._listing: set[str] | None = None  # lazily cached recursive listing

    def describe(self) -> str:
        return self._remote

    def _target(self, relative_path: str) -> str:
        return f"{self._remote}/{relative_path}"

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        proc = binaries.run(
            [self._bin, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            message = f"rclone {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
            raise RcloneError(message)
        return proc

    def list(self) -> list[str]:
        """Return every file at the remote (recursive), cached after the first call."""
        if self._listing is None:
            proc = self._run("lsf", "-R", "--files-only", self._remote)
            self._listing = {line for line in proc.stdout.splitlines() if line}
        return sorted(self._listing)

    def exists(self, relative_path: str) -> bool:
        # Prefer the cached listing to avoid a round-trip per file.
        if self._listing is not None:
            return relative_path in self._listing
        proc = self._run("lsf", self._target(relative_path))
        return bool(proc.stdout.strip())

    def upload(self, local: Path, relative_path: str) -> None:
        """``None`` always: `rclone copyto` sets modtimes itself and reports a refusal as a
        non-zero exit, which `_run` already turns into a `DestinationError`. There is no
        arrived-without-its-timestamps state to report here. `(aie)`"""
        self._run("copyto", str(local), self._target(relative_path))
        if self._listing is not None:
            self._listing.add(relative_path)

    def set_timestamp(self, relative_path: str, captured_at: datetime) -> None:
        stamp = captured_at.timestamp()
        utc = datetime.fromtimestamp(stamp, tz=UTC)
        self._run(
            "touch",
            "--no-create",
            "--timestamp",
            utc.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            self._target(relative_path),
        )
