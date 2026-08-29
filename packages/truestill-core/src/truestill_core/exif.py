"""Batch metadata extraction via the ``exiftool`` binary.

One ``exiftool`` invocation per chunk of files rather than one per file: process
startup dominates runtime otherwise, and a library of 84 GB is tens of thousands of
files. Only the tags the rules actually consult are requested, which keeps the JSON
payload small.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from truestill_core import binaries
from truestill_core.binaries import is_bundled_install, resolve_binary
from truestill_core.hash_cache import HashCache, tags_fingerprint
from truestill_core.progress import Phase, Progress, ProgressCallback

EXIFTOOL_BIN = "exiftool"

#: Points at one specific exiftool build, overriding both the bundled copy and PATH. The escape
#: hatch for a user who needs a particular version; set to a nonexistent file it resolves to
#: nothing rather than silently falling back to a different binary.
EXIFTOOL_BIN_ENV = "TRUESTILL_EXIFTOOL"

#: Files handed to exiftool per invocation. Large enough to amortise startup, small
#: enough to stay well clear of ARG_MAX on long paths.
BATCH_SIZE = 200

#: Tags consulted by the categorization and date rules. ``SourceFile`` is always
#: emitted by exiftool and is used to key results back to their paths.
REQUESTED_TAGS: tuple[str, ...] = (
    # categorization
    "SamsungCaptureInfo",
    "Make",
    "Model",
    "LensModel",
    # dates, in the order the resolver prefers them
    "DateTimeOriginal",
    # com.apple.quicktime.creationdate: the ONLY video tag carrying the local recording
    # moment *with* its UTC offset. The CreateDate family below is stored in UTC per the
    # QuickTime spec, so for anything shot away from UTC it names the wrong wall-clock -- and
    # near midnight, the wrong day/month. Requested so the resolver can prefer it.
    "CreationDate",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    # RIFF/AVI only, and the group prefix is load-bearing (`(acm)`). `DateCreated` is **also** an
    # IPTC field on stills, where it means something else and where the corpora hold malformed
    # values like `2010:00:00` - so an unscoped request would feed the resolver a value it was
    # never designed to weigh. `-RIFF:DateCreated` returns nothing on a still that carries the
    # IPTC one, verified against a real file; exiftool still keys the result plainly as
    # `DateCreated`, which is what the resolver reads.
    #
    # Worth it despite adding a tag: of the two AVIs in the corpora, **one carries this and
    # nothing else**, so the rate is per-AVI rather than one-in-1,322.
    "RIFF:DateCreated",
    # Video UTC ladder (backlog (uu)): MakerNotes zone, GPS UTC proof, clip length.
    # Unexercised on the soak corpus for GPS; requested so the rung can fire when present.
    "TimeZone",
    "GPSDateStamp",
    "GPSTimeStamp",
    "Duration",
    # informational, surfaced in reports
    "FileType",
    "MIMEType",
    "ImageWidth",
    "ImageHeight",
)

#: GPS tags, requested with a trailing ``#`` so exiftool emits signed decimal degrees for
#: just these (negative for S/W) without changing the format of any other tag. Used by the
#: event layer to reinforce time-gap boundaries with location jumps.
_NUMERIC_TAGS: tuple[str, ...] = (
    "GPSLatitude",
    "GPSLongitude",
    # Orientation, as the INTEGER 1-8 rather than exiftool's prose. Plainly it returns
    # `"Rotate 90 CW"`, which is a sentence to parse and a format to depend on; `#` gives the
    # EXIF value itself. Requested because `ImageWidth`/`ImageHeight` are the STORED dimensions
    # and 31.7% of a real corpus carries a tag that transposes them - so without this, a payload
    # built from those two disagrees with the pixels `thumbnails.render` produces.
    "Orientation",
    # HEIF's OTHER way of recording the same turn (`(aeu)`): the container's `irot` property,
    # which exiftool exposes as `Rotation` and `#` gives as 0-3 quarter turns. libheif APPLIES it
    # while decoding and ignores EXIF, so a file that records the turn only here decodes upright
    # while `Orientation` reads 1 - and a shape built from `Orientation` alone called
    # `HMD_Nokia_8.3_5G.heif` landscape when its own thumbnail was portrait.
    #
    # ⚠ **GROUP-QUALIFIED, AND THE BARE NAME IS A REAL DEFECT.** `Rotation` is not unique:
    # exiftool also exposes `[Panasonic] Rotation`, a maker-note tag whose value space is
    # unrelated - `1` there means *"Horizontal (normal)"* while `1` in QuickTime means a quarter
    # turn. Requesting the bare name transposed two landscape Panasonic and Leica JPEGs, caught by
    # sampling 300 non-HEIF files after the change rather than by reading it.
    #
    # ⚠ Adding a tag changes `tags_fingerprint`, so every cached metadata row is invalidated and
    # the next run re-reads. That is one full exiftool pass, paid once, and it is affordable
    # precisely because no release has been cut - the rule that a compatibility path has no
    # beneficiary applies to cache warmth too.
    "QuickTime:Rotation",
)

#: Said to someone running a **packaged** copy. exiftool ships inside the application, so its
#: absence is a broken installation rather than something they forgot to do - and a person who
#: double-clicked an icon has no terminal to paste an install command into.
_MISSING_BUNDLED_MSG = (
    "Truestill could not find exiftool, which it needs to read the dates and camera details "
    "stored inside your photos. It is normally installed as part of Truestill, so this "
    "installation looks incomplete. Installing Truestill again should fix it."
)

#: Said to someone running a **packaged Linux** copy, where exiftool is a **declared dependency**
#: rather than a bundled file (`BACKLOG.md` `(aad)`, ruled 2026-08-13: there is no standalone Linux
#: exiftool, only a Perl script and its module tree, and carrying someone else's runtime means
#: owning a CVE surface we cannot patch). "Installing Truestill again should fix it" would be the
#: wrong advice here - the package manager is what supplies it, and naming the package is what the
#: reader can act on.
_MISSING_PACKAGED_LINUX_MSG = (
    "Truestill could not find exiftool, which it needs to read the dates and camera details "
    "stored inside your photos. On Linux it comes from your system's package manager rather than "
    "from Truestill. Install it with 'sudo apt install -y libimage-exiftool-perl' and try again."
)

#: Said in a source checkout, where the tool genuinely has to be obtained and the reader has a
#: terminal in front of them.
_MISSING_SOURCE_MSG = (
    "exiftool was not found. Truestill needs it to read the dates and camera details stored "
    "inside your photos. Install it with 'sudo apt install -y libimage-exiftool-perl' on "
    "Debian or Ubuntu, 'brew install exiftool' on macOS, or from exiftool.org on Windows."
)

#: Said when an explicit override points at a file that is not there. Naming the variable and
#: the path is the whole content of the fix, and falling back would hide the mistake.
_MISSING_OVERRIDE_MSG = (
    "{env} is set to '{value}', but there is no file there. Truestill will not quietly use a "
    "different exiftool than the one you asked for. Correct the path, or unset {env} to let "
    "Truestill find exiftool itself."
)


class ExiftoolMissingError(RuntimeError):
    """Raised when the exiftool binary is unavailable."""


def _missing_message() -> str:
    """The advice that fits the situation the reader is actually in.

    **Four audiences now, not three:** a mistyped override, a broken packaged install on Windows,
    a **packaged Linux** copy whose distro package is absent, and a source checkout that has not
    installed the tool. The Linux split arrived with the ruling that exiftool is a declared
    dependency there - telling that reader to reinstall Truestill would be wrong advice, and one
    message for all four would be vague enough to be useless to each.
    """
    override = os.environ.get(EXIFTOOL_BIN_ENV)
    if override:
        return _MISSING_OVERRIDE_MSG.format(env=EXIFTOOL_BIN_ENV, value=override)
    if not is_bundled_install():
        return _MISSING_SOURCE_MSG
    # A packaged copy, and the advice differs by platform because the PACKAGING does. Windows
    # bundles the binary, so a missing one means a broken install; Linux declares it, so a missing
    # one means a missing package and "reinstall Truestill" would send the reader nowhere useful.
    if sys.platform.startswith("linux"):
        return _MISSING_PACKAGED_LINUX_MSG
    return _MISSING_BUNDLED_MSG


def ensure_exiftool() -> str:
    """Path to the exiftool binary - bundled copy first, then PATH - or raise saying why not.

    See `binaries` for the resolution order and for why it is not cached (measured at 30.6 us
    per batch, against an exiftool process start of 50-200 ms).
    """
    found = resolve_binary(EXIFTOOL_BIN, override_env=EXIFTOOL_BIN_ENV)
    if found is None:
        raise ExiftoolMissingError(_missing_message())
    return found


def _chunked[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


#: `-m` ignores minor errors rather than refusing the whole write. Deliberately *not* `-q`:
#: quiet suppresses the per-file "1 image files updated" summary, which is the only signal
#: tying a batched result back to the file it belongs to.
_WRITE_FLAGS = ("-overwrite_original", "-m")


def build_metadata_args(
    *,
    taken_at_local: datetime | None = None,
    gps: tuple[float, float] | None = None,
    description: str = "",
) -> list[str]:
    """The exiftool arguments that bake this metadata, or ``[]`` when there is nothing to write.

    Shared by the single-file and batch paths so there is exactly one definition of what a
    rescued date, a rescued location and a description mean on disk.
    """
    tags: list[str] = []
    if taken_at_local is not None:
        stamp = taken_at_local.strftime("%Y:%m:%d %H:%M:%S")
        tags += [
            f"-DateTimeOriginal={stamp}",
            f"-CreateDate={stamp}",
            f"-QuickTime:CreateDate={stamp}",
        ]
    if gps is not None:
        lat, lon = gps
        tags += [
            f"-GPSLatitude={abs(lat)}",
            f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
            f"-GPSLongitude={abs(lon)}",
            f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
        ]
    if description:
        tags += [f"-Description={description}", f"-ImageDescription={description}"]

    return [*_WRITE_FLAGS, *tags] if tags else []


#: Files whose metadata is written per exiftool process. One process per *file* costs ~225 ms
#: -- measured -- of which nearly all is startup, so a 100k-file Takeout ingest spent about
#: 6 hours doing nothing but spawning. Batching cuts that ~43x.
#:
#: Smaller than the read batch on purpose: the caller stages a copy of each file before baking
#: it, so this constant is also the peak temp-disk footprint of an ingest (chunk x file size).
#: 100 trades a little speed for not needing gigabytes of scratch space -- which matters most
#: to exactly the people this feature serves.
WRITE_BATCH_SIZE = 100

#: exiftool prints one of these per `-execute`, in order, and that ordering is the only thing
#: tying a result back to its file.
_UPDATED = re.compile(r"^\s*(\d+) image files updated", re.MULTILINE)


def write_metadata_batch(items: Sequence[tuple[Path, list[str]]]) -> dict[Path, bool]:
    """Bake metadata into several files with as few exiftool processes as possible.

    Each item is ``(path, args)`` -- the tag arguments already built for that file. Operations
    are separated by ``-execute`` inside a single argfile, so one process serves up to
    :data:`WRITE_BATCH_SIZE` files instead of one process per file.

    Returns a per-file verdict. **A file absent from a short reply is reported as failed**, not
    assumed fine: if exiftool dies part-way through a batch it simply stops printing, and
    treating silence as success would record a bake that never happened.
    """
    if not items:
        return {}
    binary = ensure_exiftool()
    verdicts: dict[Path, bool] = {}

    for chunk in _chunked(list(items), WRITE_BATCH_SIZE):
        lines: list[str] = []
        for path, args in chunk:
            # The same input armour `_read_chunk` passes, and it must repeat PER BLOCK: options
            # apply only to the command their `-execute` closes, so a single leading `-charset`
            # would cover the first file alone. The argfile is exiftool's documented route for
            # non-ASCII filenames on Windows - the name travels as UTF-8 bytes in this file,
            # never through argv and the console code page. `(aic)`; verified against a
            # two-block argfile before landing.
            lines.extend(["-charset", "filename=utf8", *args, str(path), "-execute"])
        with tempfile.NamedTemporaryFile("w", suffix=".args", delete=False, encoding="utf-8") as fh:
            fh.write("\n".join(lines))
            argfile = Path(fh.name)
        try:
            proc = binaries.run(
                [binary, "-@", str(argfile)], capture_output=True, text=True, check=False
            )
            counts = [int(m) for m in _UPDATED.findall(proc.stdout)]
        except OSError:
            counts = []  # exiftool could not be run at all -- every file in this chunk failed
        finally:
            argfile.unlink(missing_ok=True)

        for i, (path, _) in enumerate(chunk):
            # Short reply -> the process stopped early; everything past that point is unknown,
            # and unknown is reported as failed.
            verdicts[path] = counts[i] > 0 if i < len(counts) else False

    return verdicts


def _partition_by_cache(
    paths: Sequence[Path],
    *,
    cache: HashCache | None,
    force: bool,
    tags_fp: str,
) -> tuple[dict[Path, dict[str, Any]], list[Path]]:
    """Split ``paths`` into cache hits and files that still need an exiftool read."""
    if cache is None or force:
        return {}, list(paths)

    collected: dict[Path, dict[str, Any]] = {}
    to_read: list[Path] = []
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            to_read.append(path)
            continue
        hit = cache.get_metadata(path, stat.st_size, stat.st_mtime_ns, tags_fp)
        if hit is None:
            to_read.append(path)
        else:
            collected[path] = hit
    return collected, to_read


def _read_chunk(binary: str, chunk: Sequence[Path]) -> list[dict[str, Any]]:
    """One exiftool batch. Empty stdout or unparseable JSON yields ``[]`` (silent skip)."""
    args = [binary, "-json", "-q", "-m", "-charset", "filename=utf8"]
    args += [f"-{tag}" for tag in REQUESTED_TAGS]
    args += [f"-{tag}#" for tag in _NUMERIC_TAGS]  # signed decimal degrees for GPS
    args += [str(path) for path in chunk]

    proc = binaries.run(args, capture_output=True, text=True, check=False)
    payload = proc.stdout.strip()
    if not payload:
        return []
    try:
        parsed: list[dict[str, Any]] = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return parsed


def _cache_records(
    collected: dict[Path, dict[str, Any]],
    chunk: Sequence[Path],
    records: Sequence[dict[str, Any]],
    *,
    cache: HashCache | None,
    tags_fp: str,
) -> None:
    """Merge one batch into ``collected`` and, when ``cache`` is set, write each hit back."""
    by_name = {str(path): path for path in chunk}
    for record in records:
        source = record.get("SourceFile")
        if not source:
            continue
        path = by_name.get(source) or Path(source)
        collected[path] = record
        if cache is None:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        cache.put_metadata(path, stat.st_size, stat.st_mtime_ns, tags_fp, record)


def read_metadata(
    paths: Sequence[Path],
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    cache: HashCache | None = None,
    force: bool = False,
) -> dict[Path, dict[str, Any]]:
    """Read the requested tags for ``paths``.

    Files that exiftool cannot parse are simply absent from the result; callers treat
    a missing entry as "no metadata", which flows naturally into the Other category
    and the Undated folder.

    ``progress`` is reported per exiftool batch, and ``cancel`` is checked between them. On a
    large library this phase is minutes of work before anything else starts: a run that
    reports nothing until it is over is indistinguishable from one that has hung, and a
    Cancel button that does nothing until the phase ends is indistinguishable from a broken
    one. Cancelling returns what was read so far -- callers treat a missing entry as "no
    metadata", which is already the normal path for an unparseable file.

    ``cache``, when given, serves unchanged files (path + size + ``mtime_ns`` + tag-set
    fingerprint) without invoking exiftool. ``force=True`` bypasses those hits -- required
    when an external tool may have edited tags without bumping mtime (IMatch-class editors).
    Verify and reclaim must never pass a cache: they re-read bytes on disk by design.
    """
    if not paths:
        return {}

    tags_fp = tags_fingerprint(REQUESTED_TAGS, _NUMERIC_TAGS)
    collected, to_read = _partition_by_cache(paths, cache=cache, force=force, tags_fp=tags_fp)

    if progress is not None and collected:
        # Cache hits count as done so a fully warm run shows a completed scanning phase.
        progress(Progress(len(collected), len(paths), Phase.SCANNING, ""))

    if not to_read:
        return collected

    binary = ensure_exiftool()
    done = len(collected)

    for chunk in _chunked(to_read, BATCH_SIZE):
        if cancel is not None and cancel.is_set():
            break
        if progress is not None:
            progress(Progress(done, len(paths), Phase.SCANNING, Path(chunk[0]).name))
        records = _read_chunk(binary, chunk)
        done += len(chunk)
        if not records:
            continue
        _cache_records(collected, chunk, records, cache=cache, tags_fp=tags_fp)

    return collected
