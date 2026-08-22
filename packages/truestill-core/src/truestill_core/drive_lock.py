"""One mutating operation per drive, across processes. `(aaw)`

**Measured, not reasoned.** Two `organize --apply` runs against one destination lose organized
copies: 2 of 9 attempts on real photographs lost **99** and **45**, proven by content - a file whose
bytes are byte-exactly the other run's while this run's report claims it ``uploaded``.

⚠ **Unique staging (`safe_copy.staging_path`) shipped first and did not finish the job; it made the
outcome worse.** Against the same reproduction: before it, 4 of 5 attempts hit and the loser failed
loudly with ``ENOENT``; after it, **5 of 5 hit, both processes exit 0, and nothing is said**. It
removed the shared staging file and with it the only signal. What remains is last-write-wins on a
contested name - bookkeeping in copy mode, and **irreversible loss under ``--move``/``--in-place``**,
the modes a user reaches when they have no room for a second copy. That is what this prevents.

## The rule, and it is a rule rather than a special case

**Wait when the contended state is bounded and short; refuse when it is not.** A held drive lock is
seconds to hours, so waiting on it is a command that appears to hang with no way to know how long -
it **refuses**, naming the holder. Catalog creation is transient by construction, milliseconds -
`catalog_startup` **waits** there, with a bound. The next contended state gets the test rather than
the precedent.

## Kernel-enforced, with no PID liveness check and no TTL

``fcntl.flock(LOCK_EX | LOCK_NB)`` on POSIX, ``msvcrt.locking(LK_NBLCK)`` on Windows. The decisive
property is that **the OS releases these when the process dies** - SIGKILL, crash, or power loss -
so *"the user is locked out of their own library"* is a state this cannot reach, and there is no
stale lock to detect or clear. A PID check would require us to judge liveness and could be wrong in
the direction of stranding the user; a TTL solves only the cross-machine case that is out of scope.

**PID, host and operation are written INSIDE the locked file**, as advisory content for the refusal
message only. **The flock is the truth**; that text is a courtesy and is never trusted.

⚠ **The lock file lives in the data dir, never on the drive.** Advisory locking is least reliable on
exactly the FUSE and network mounts a photo library sits on, a stale file on the user's own drive is
the thing they delete by hand, and the drive marker is stable identity rather than a high-churn
runtime file. Single-machine scope is therefore deliberate: two machines sharing one cloud mount is
**a documented limit, not a defended case** - no mechanism is reliable there, and saying so beats
pretending.

## Why hand-rolled rather than ``filelock``

``filelock`` is in the lockfile only via ``virtualenv``, i.e. dev-side, so adopting it is a genuine
new runtime dependency - and **it does not solve FUSE** (same OS primitives), while its
``SoftFileLock`` fallback strands a stale lock on a dead process, the exact failure this refuses.
The ``psutil`` precedent in "Settled technical stances" is the one that governs.

## ⚠ The FD is the lock, which is why this is not only a context manager

Both primitives bind the lock to the **file descriptor**: closing the file releases it, silently.
The CLI holds it across a ``with`` block, but the app starts a job on a worker thread and returns -
so :meth:`DriveLock.acquire` and :meth:`DriveLock.release` exist to let ownership outlive the
function that took it, and `test_the_lock_outlives_the_function_that_took_it` is the guard.
"""

from __future__ import annotations

import hashlib
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from truestill_core.app_paths import lock_path_for
from truestill_core.drive import drive_identity

# ⚠ **The primitive is defined per platform, not chosen inside one function**, and that is a
# type-checking fact rather than a style choice. `mypy` narrows `sys.platform` and analyses only
# the branch that matches the host, so a module that imports `fcntl` in an `else` and mentions it
# anywhere fails on Windows with *"Name `fcntl` is not defined"* - which the Windows lane caught
# and a Linux `make check` cannot. Defining the functions inside each branch keeps every
# reference next to its own import.
#: The byte Windows actually locks, chosen far past any claim we write. `(aaw)`
#:
#: ⚠ **Windows locks are MANDATORY, not advisory**, so a locked byte cannot be READ by anyone
#: else - and the claim (pid, host, operation) lives at offset 0 precisely so the other process
#: can read it to name the holder. Locking byte 0 made the refusal anonymous on Windows and
#: nowhere else; the Windows lane caught it. Locking a sentinel far beyond the text leaves the
#: text readable while the exclusion is unchanged, which is the ordinary way to do this on a
#: platform without advisory locks.
_SENTINEL_BYTE = 1 << 30

if sys.platform == "win32":  # pragma: no cover - exercised on the Windows lane only
    import msvcrt

    def _take(fd: int) -> None:
        """Claim ``fd`` exclusively without waiting. Raises ``OSError`` when someone holds it."""
        os.lseek(fd, _SENTINEL_BYTE, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _give_up(fd: int) -> None:
        """Release ``fd``'s claim. Closing it would do this too; the pair stays legible."""
        os.lseek(fd, _SENTINEL_BYTE, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _take(fd: int) -> None:
        """Claim ``fd`` exclusively without waiting. Raises ``OSError`` when someone holds it."""
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _give_up(fd: int) -> None:
        """Release ``fd``'s claim. Closing it would do this too; the pair stays legible."""
        fcntl.flock(fd, fcntl.LOCK_UN)


@dataclass(frozen=True, slots=True)
class LockHolder:
    """Who says they hold the drive. **Advisory: read from the file, never trusted.**"""

    pid: int
    host: str
    operation: str

    def describe(self) -> str:
        """One clause naming the holder, for a refusal a person can act on."""
        return f"{self.operation} (process {self.pid} on {self.host})"


class DriveBusyError(Exception):
    """Another live process holds this drive.

    ⚠ **A refusal always means a LIVE holder**, because the lock is kernel-enforced: a crashed
    process leaves nothing to force past. That is why there is no ``--force`` - it could only ever
    override a *running* operation, which is the one thing it must not do. The escape hatch is
    naming the holder so a user with a genuinely hung process deals with the process.
    """

    def __init__(self, label: str, holder: LockHolder | None) -> None:
        self.label = label
        self.holder = holder
        who = f" It is running {holder.describe()}." if holder is not None else ""
        super().__init__(
            f"Another Truestill operation is using '{label}' right now.{who} "
            "Wait for it to finish, or stop that process, and run this again."
        )


def _lock_file_for(key: str) -> Path:
    """Where this drive's lock lives. **Hashed, because a drive key is not a filename.**

    A ``path:`` key contains separators and a ``uuid:`` key contains a colon, which Windows refuses
    outright. The digest is not security - it is a filename - so its only requirement is that two
    different keys do not collide.
    """
    return lock_path_for(hashlib.sha256(key.encode("utf-8")).hexdigest()[:32])


def _read_holder(path: Path) -> LockHolder | None:
    """Whatever the holder wrote about itself, or ``None`` when it says nothing usable.

    Never raises and never guesses: a half-written line, an empty file (the holder took the lock
    and has not written yet) and a foreign file all mean *"no usable claim"*, and a refusal without
    a name is still a correct refusal.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            pid, host, operation = fh.read().split("\n", 2)
        return LockHolder(pid=int(pid), host=host, operation=operation.strip())
    except (OSError, ValueError):
        return None


class DriveLock:
    """An exclusive claim on one drive for one mutating operation.

    Use it as a context manager where the operation is synchronous, or
    :meth:`acquire`/:meth:`release` where ownership must outlive the acquiring call.
    """

    def __init__(self, key: str, label: str, *, operation: str) -> None:
        self._key = key
        self._label = label
        self._operation = operation
        self._path = _lock_file_for(key)
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        """The lock file. Exposed for tests and for saying where a refusal came from."""
        return self._path

    @property
    def held(self) -> bool:
        """Whether this object currently owns the lock."""
        return self._fd is not None

    def acquire(self) -> None:
        """Take the lock or raise :class:`DriveBusyError`. **Never blocks.**"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _take(fd)
        except OSError as exc:
            holder = _read_holder(self._path)
            os.close(fd)
            raise DriveBusyError(self._label, holder) from exc
        self._fd = fd
        # Written AFTER the lock is held, so what is in the file always belongs to the holder.
        # ⚠ Seek back to the start first: taking the lock moved the descriptor to the sentinel
        # byte on Windows, and writing from there would put the claim a gigabyte into the file
        # where no other process would look for it.
        os.lseek(fd, 0, os.SEEK_SET)
        # Truncate: a shorter claim must not leave the tail of a longer one behind.
        os.ftruncate(fd, 0)
        claim = f"{os.getpid()}\n{socket.gethostname()}\n{self._operation}\n"
        os.write(fd, claim.encode("utf-8"))
        os.fsync(fd)

    def release(self) -> None:
        """Give the lock up. A no-op when it is not held, and never raises."""
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            os.ftruncate(fd, 0)
            _give_up(fd)
        except OSError:
            # Closing the descriptor releases the lock either way, which is the whole point of
            # binding it to the FD. Failing to tidy must not fail an operation that succeeded.
            pass
        finally:
            os.close(fd)

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def lock_for(root: Path, *, operation: str) -> DriveLock:
    """The lock for the drive at ``root``. One spelling of the key, from `drive.drive_identity`."""
    identity = drive_identity(root)
    return DriveLock(identity.key, identity.label, operation=operation)
