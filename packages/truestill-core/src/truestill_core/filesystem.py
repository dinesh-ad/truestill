"""What the destination filesystem can actually hold.

**The failure this closes.** FAT32 cannot store a file of 4 GiB or more, and 4K phone video
crosses that routinely - FAT32 is still the default on SD cards and small USB sticks. Before
this, such a file produced ``[Errno 27] File too large`` against a drive showing 200 GB free,
whose only reasonable reading is that Truestill is broken. And organize had **no preflight at
all**, so a library with a few big videos organized nine thousand files and *then* failed N of
them, one errno at a time, at the end.

**Where detection works, and where it honestly does not.** ``/proc/mounts`` on Linux and
``GetVolumeInformationW`` on Windows are cheap, need no subprocess, and name the filesystem
exactly. macOS exposes it only via `statfs`'s ``f_fstypename`` or a subprocess; neither is worth
a per-run cost, so **macOS returns unknown**. Unknown is a real answer rather than a guessed one,
and it never refuses anything - the improved error message covers that platform.

**The mapping is deliberately narrow.** Only the FAT family reports a limit. A wrong limit would
refuse work that would have succeeded, which is worse than the bug being fixed.

**Complexity: O(mount lines)** on Linux, one syscall on Windows, and one ``stat`` per candidate
file in the preflight.
"""

from __future__ import annotations

import ctypes
import shutil
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: The largest file FAT32 can store: 4 GiB **minus one byte**. A file of exactly 4 GiB does not
#: fit, which is why the comparison is ``>`` against this value rather than ``>=`` against 4 GiB.
FAT32_MAX_FILE_BYTES = 4 * 1024**3 - 1

#: How many oversized files are named before the list is truncated. Enough to see the pattern
#: without a wall of text; the count of the rest is always stated.
_NAMED_LIMIT = 5

#: How the FAT family spells itself. Linux reports ``vfat`` or ``msdos``; Windows reports
#: ``FAT32`` or ``FAT``. All of them mean the same 4 GiB ceiling.
_FAT_NAMES = frozenset({"vfat", "msdos", "fat", "fat32", "fat16", "fat12"})


@dataclass(frozen=True, slots=True)
class FilesystemFacts:
    """What is known about a destination. ``None`` everywhere means "could not tell"."""

    #: The filesystem name as the OS reports it, or ``None`` when it cannot be determined.
    filesystem: str | None
    #: Largest file this filesystem can hold, or ``None`` for "no limit worth enforcing".
    max_file_bytes: int | None

    @property
    def known(self) -> bool:
        return self.filesystem is not None


#: Filesystems that store no per-file access control of any kind. FAT32 and exFAT have neither
#: POSIX permission bits nor Windows ACLs, so a file on one is readable by every account on the
#: machine whatever mode was requested when it was created.
_NO_ACCESS_CONTROL = _FAT_NAMES | {"exfat"}


def stores_access_control(name: str | None) -> bool:
    """Whether this filesystem can keep a file to one user.

    **Unknown means yes.** Same rule as `max_file_bytes_for`: a guess that says "no" would warn
    every user of an undetectable filesystem that their credentials are exposed, and a security
    warning that fires when nothing is wrong is worse than none - it teaches people to ignore
    the one that matters.
    """
    return name is None or name.strip().lower() not in _NO_ACCESS_CONTROL


def fat_family(name: str | None) -> bool:
    """Whether ``name`` is one of FAT32's spellings across the platforms that report it."""
    return name is not None and name.strip().lower() in _FAT_NAMES


def max_file_bytes_for(name: str | None) -> int | None:
    """The per-file ceiling for a filesystem name, or ``None`` when there is none to enforce.

    exFAT is explicitly *not* limited: it was created to lift FAT32's cap and handles files far
    beyond anything a camera produces. Treating it as FAT would refuse work that succeeds.
    """
    return FAT32_MAX_FILE_BYTES if fat_family(name) else None


def parse_proc_mounts(contents: str, target: Path) -> str | None:
    """Filesystem type for ``target`` from ``/proc/mounts`` contents.

    **Longest matching mount point wins.** A file under ``/media/big/deeper`` is on that mount,
    not on the ``/`` that also matches it - taking the first match would report the root
    filesystem for every removable drive and defeat the whole check.
    """
    best: tuple[int, str] | None = None
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) < 3:  # noqa: PLR2004 - device, mount point, type
            continue
        mount, fstype = fields[1], fields[2]
        try:
            mount_path = Path(mount)
            if target == mount_path or mount_path in target.parents:
                depth = len(mount_path.parts)
                if best is None or depth > best[0]:
                    best = (depth, fstype)
        except (OSError, ValueError):  # pragma: no cover - malformed mount line
            continue
    return best[1] if best else None


def _windows_filesystem(target: Path) -> str | None:  # pragma: no cover - Windows only
    """The volume's filesystem name via ``GetVolumeInformationW``. No subprocess.

    The platform guard is *inside* the function, not only at the call site: mypy narrows on
    ``sys.platform`` lexically, and `ctypes.WinDLL` does not exist off Windows. Guarding only at
    the caller type-checks the body on Linux and fails - the same lesson `packaging/` taught when
    it joined the type fence.
    """
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    drive = Path(target.anchor or target)
    buffer = ctypes.create_unicode_buffer(256)
    ok = kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(str(drive)), None, 0, None, None, None, buffer, ctypes.sizeof(buffer)
    )
    return buffer.value or None if ok else None


def facts_for(target: Path) -> FilesystemFacts:
    """What is known about ``target``'s filesystem. Never raises; unknown is a valid answer."""
    name: str | None = None
    try:
        resolved = target if target.exists() else _nearest_existing(target)
        if sys.platform == "win32":
            name = _windows_filesystem(resolved)
        elif sys.platform.startswith("linux"):
            name = parse_proc_mounts(Path("/proc/mounts").read_text(encoding="utf-8"), resolved)
        # macOS and anything else: unknown. See the module docstring - a guess here would be
        # worse than silence, because a wrong limit refuses work that would have succeeded.
    except OSError:
        name = None
    return FilesystemFacts(filesystem=name, max_file_bytes=max_file_bytes_for(name))


def _nearest_existing(path: Path) -> Path:
    for candidate in [path, *path.parents]:
        if candidate.exists():
            return candidate
    return Path(path.anchor or ".")


def sizes_of(paths: Iterable[Path]) -> list[tuple[Path, int]]:
    """``(path, size)`` for each readable path; unreadable ones are **skipped, not raised**.

    A preflight that fails is worse than one that misses a file: it blocks the entire run over
    something the copy itself would have reported per-file anyway.
    """
    sized: list[tuple[Path, int]] = []
    for path in paths:
        try:
            sized.append((path, path.stat().st_size))
        except OSError:
            continue
    return sized


def oversized_for(
    sized: Iterable[tuple[Path, int]], facts: FilesystemFacts
) -> Sequence[tuple[Path, int]]:
    """Files that cannot be written to this destination, **named** with their sizes.

    Named rather than counted: *"3 files are too large"* is not something a user can act on, and
    the files that trip this are exactly the footage the user cared most about.

    Takes sizes rather than paths so that a caller which **already knows them** does not stat the
    disk again. That is not hypothetical: backup's space check reads its sizes from catalog rows,
    and a path-only signature here would have forced it to grow a second copy of this logic.
    """
    limit = facts.max_file_bytes
    if limit is None:
        return []
    return [(path, size) for path, size in sized if size > limit]


@dataclass(frozen=True, slots=True)
class DestinationPreflight:
    """Whether a destination can hold this work, answered **before** any of it starts.

    Organize had no preflight at all, which is why a library with a few 4K videos organized nine
    thousand files and then failed N of them one errno at a time. Backup already had this shape -
    report in the preview, refuse at apply - but its version lives in the app service layer, so
    the CLI never got it. This one lives in core precisely so **both surfaces share one
    mechanism** rather than growing a second.
    """

    facts: FilesystemFacts
    #: ``(path, size)`` for every file too large for this filesystem. Named, never counted.
    oversized: tuple[tuple[Path, int], ...]
    need_bytes: int
    free_bytes: int

    @property
    def enough_space(self) -> bool:
        return self.free_bytes >= self.need_bytes

    @property
    def may_proceed(self) -> bool:
        return not self.oversized and self.enough_space

    def detail(self) -> str:
        """The sentence a user reads. Oversized files are named, because "3 files are too large"
        is not something anyone can act on."""
        if self.oversized:
            named = ", ".join(
                f"{path.name} ({size / 1024**3:.1f} GB)"
                for path, size in self.oversized[:_NAMED_LIMIT]
            )
            extra = len(self.oversized) - _NAMED_LIMIT
            more = f" and {extra} more" if extra > 0 else ""
            where = f" ({self.facts.filesystem})" if self.facts.known else ""
            return (
                f"These files are too large for this drive{where}: {named}{more}. Drives "
                f"formatted FAT32 cannot hold a single file of 4 GB or more, however much free "
                f"space they show. Use a drive formatted exFAT or NTFS for these."
            )
        if not self.enough_space:
            return (
                f"Not enough room: this needs about {self.need_bytes / 1024**3:.1f} GB and the "
                f"drive has {self.free_bytes / 1024**3:.1f} GB free."
            )
        return ""


def preflight_destination(
    sized: Iterable[tuple[Path, int]],
    destination: Path,
    *,
    facts: FilesystemFacts | None = None,
) -> DestinationPreflight:
    """Can this destination hold this work? Reads the filesystem; writes nothing.

    ``facts`` is injectable so a caller that already determined them - or a test pinning the
    comparison rather than the 4 GiB constant - does not repeat the detection.
    """
    work = list(sized)
    known = facts if facts is not None else facts_for(destination)
    try:
        free = shutil.disk_usage(_nearest_existing(destination)).free
    except OSError:  # pragma: no cover - an unreachable destination fails later, and louder
        free = 0
    need = sum(size for _path, size in work)
    return DestinationPreflight(
        facts=known,
        oversized=tuple(oversized_for(work, known)),
        need_bytes=need,
        # An unmeasurable destination must not be reported as full: it fails later, and louder,
        # with the real reason rather than a space figure nobody could obtain.
        free_bytes=free or need,
    )
