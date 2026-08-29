"""A copy whose METADATA is refused is still a copy. `(aie)`

**The measured defect.** `LocalDestination.upload` called `shutil.copy2`, which is `copyfile`
then `copystat`, inside one `except OSError`. On a mount that refuses `os.utime` - SMB/CIFS, NFS
with `root_squash`, FUSE and cloud mounts, FAT32, or simply not owning the destination file - the
bytes arrived in full and `copystat` raised. The `except` could not tell that from a truncated
write, so it **deleted the complete photograph**, reported `FAILED` with the words *"the drive is
read-only, or this account cannot write to it"* - about a drive that had just taken the write -
and did it again to every remaining file, because the condition belongs to the mount.

**What decides it is which call raised, not which errno.** `EPERM` from `copyfile` and `EPERM`
from `copystat` are the same number with opposite meanings; a *"keep on any `OSError`"* would keep
`(abu)`'s 802-MB truncation, which is the defect `safe_copy` exists to close. So the two halves
below are equally load-bearing:

* a refused `copystat` keeps the file and says so - four times over, because `copystat` has four
  steps and only one of them was ever measured;
* **a refused `copyfile` still discards**, and a partial write is still never given the real name.

The field is unanimous and the standard library is explicit: `copy2` *"never raises an exception
because it cannot preserve file metadata"* on a platform that lacks the capability, and
`shutil.copy` is named for callers that *"cannot tolerate metadata errors"*. rsync keeps the file
and exits 23; restic ignores it; robocopy separates data from metadata by design.
"""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

import pytest
from truestill_core import safe_copy
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations.local import LocalDestination
from truestill_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import execute
from truestill_core.safe_copy import copy_leaving_nothing

_REFUSED = OSError(errno.EPERM, "Operation not permitted")


def _refuse(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make one step INSIDE `copystat` refuse, leaving the others working.

    ⚠ **Patched on `os`, not on `shutil.copystat`.** Replacing `copystat` wholesale would prove
    only that `safe_copy` calls something that can fail; what has to hold is that a refusal from
    each real step reaches the same place, since the stdlib guards them differently - `utime` not
    at all, `chmod` against `NotImplementedError` rather than `OSError`.
    """

    def boom(*_args: object, **_kwargs: object) -> None:
        raise _REFUSED

    monkeypatch.setattr(os, name, boom)


@pytest.mark.parametrize("step", ["utime", "chmod"])
def test_a_refused_copystat_keeps_the_file_and_reports_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    """THE DETECTOR. Both unguarded steps, because only `utime` was ever measured.

    `chmod` is here on its own evidence rather than for symmetry: the stdlib wraps it in
    `except NotImplementedError`, which is not what a refusal raises, so every `OSError` from it
    propagates - and SMB/CIFS, most FUSE mounts, a Windows read-only attribute, `chattr +i` and
    NFS root-squash all refuse a mode change outright. Its exposure is wider than `utime`'s, and
    a fix that closed the measured case alone would have left it.
    """
    source = tmp_path / "in.jpg"
    source.write_bytes(b"an irreplaceable photograph")
    target = tmp_path / "out" / "organized.jpg"
    target.parent.mkdir()
    _refuse(step, monkeypatch)

    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is True, f"a complete copy was reported as a failure ({step})"
    assert target.read_bytes() == b"an irreplaceable photograph", "the copy was thrown away"
    assert outcome.error is None, "a metadata refusal was reported as a copy failure"
    assert outcome.metadata_error is not None, "the refusal was swallowed instead of reported"
    assert outcome.metadata_error.errno == errno.EPERM


def test_a_refused_copyfile_still_discards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CRY-WOLF HALF ONE: a destination that genuinely will not take the write must still refuse.

    This is the mutation the fix could most easily overshoot into - *"keep on any `OSError`"* -
    and it is exactly `(abu)`: 802 MB of an 852 MB video, wearing an organized name, counted as
    failed and left on the disk.
    """
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "organized.mp4"

    def dies_after_writing(_src: object, dst: object, **_kw: object) -> None:
        Path(str(dst)).write_bytes(b"y" * 60)
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(safe_copy.shutil, "copyfile", dies_after_writing)

    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is False, "a truncated write was accepted as a copy"
    assert outcome.error is not None
    assert outcome.metadata_error is None, "a data failure was labelled a metadata one"
    assert not target.exists(), "60 bytes took the real name"
    assert list(tmp_path.iterdir()) == [source], "the partial survived"


def test_the_copy_is_verifiable_after_a_refused_copystat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CRY-WOLF HALF TWO, and the reason keeping the file is safe rather than merely kinder.

    Keeping a copy is only right if the copy is *whole*. `verify` re-hashes what is on the drive
    against what the catalog recorded, so a kept file that differed by a byte would be worse than
    a deleted one - it would be a false custody claim that survives the run.
    """
    source = tmp_path / "in.jpg"
    source.write_bytes(os.urandom(64 * 1024))
    target = tmp_path / "organized.jpg"
    _refuse("utime", monkeypatch)

    assert copy_leaving_nothing(source, target).ok is True
    assert target.read_bytes() == source.read_bytes(), "the kept copy is not byte-identical"


def _resolution(source: Path) -> Resolution:
    return Resolution(
        decision=Decision(
            source=source,
            category=CategoryMatch(
                label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
            ),
            captured_at=None,
            date_source=DateSource.NONE,
            date_tag=None,
            relative=Path("Camera/Undated") / source.name,
        ),
        hashes=FileHashes(sha256=source.name.ljust(64, "a"), perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_organize_lands_every_file_on_a_mount_that_refuses_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P140'S REPRODUCTION, INVERTED. It is the end-to-end half and the one that ranks.

    Before this fix the same injection organized **nothing**: three complete photographs deleted,
    three `FAILED` lines each naming a read-only drive that had just accepted the write, and no
    flag that helped - `--no-timestamps` guards `set_timestamp`, not the `copystat` inside the
    copy.

    ⚠ **The refusal is scoped to the STAGED name on purpose.** `copystat` writes to the staged
    sibling; `Destination.set_timestamp` writes to the final path. Refusing both would prove two
    defects at once and pass while either was broken - and the second is `(ain)`, open and
    unfixed, where a refused stamp after a committed rename leaves a file with no catalog row.
    """
    sources = []
    for i in range(3):
        p = tmp_path / "src" / f"p{i}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes([i]) * 2048)
        sources.append(p)

    real_utime = os.utime

    def refuse_on_staged(path: object, *args: object, **kwargs: object) -> None:
        if str(path).endswith(safe_copy.STAGING_SUFFIX):
            raise _REFUSED
        real_utime(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "utime", refuse_on_staged)

    results = execute(
        [_resolution(p) for p in sources],
        LocalDestination(tmp_path / "dest"),
        None,
        apply=True,
    )

    assert [r.status for r in results] == [ActionStatus.UPLOADED] * 3, (
        "complete copies were reported as failures"
    )
    landed = sorted(p.name for p in (tmp_path / "dest" / "Camera" / "Undated").iterdir())
    assert landed == ["p0.jpg", "p1.jpg", "p2.jpg"], "the photographs were thrown away"

    assert [r.metadata_ok for r in results] == [False] * 3, (
        "the degradation is silent - nothing can select these files to report them"
    )
    for result in results:
        assert "is safe" in result.detail, "the note does not say the file survived"
        assert "timestamps or permissions" in result.detail, "the note does not say what was lost"
        assert "read-only" not in result.detail, (
            "the drive is named read-only about a file that is sitting on it"
        )


def test_an_ordinary_run_says_nothing_about_metadata(tmp_path: Path) -> None:
    """CRY-WOLF HALF THREE. A note on every successful copy would be worse than silence.

    Nothing is stubbed here: `copystat` really runs and really succeeds, so `metadata_ok` must
    stay true and the detail must stay empty of any of this.
    """
    source = tmp_path / "src" / "p0.jpg"
    source.parent.mkdir()
    source.write_bytes(b"z" * 2048)

    results = execute([_resolution(source)], LocalDestination(tmp_path / "dest"), None, apply=True)

    assert [r.status for r in results] == [ActionStatus.UPLOADED]
    assert results[0].metadata_ok is True, "a working destination was reported as refusing"
    assert "timestamps" not in results[0].detail
    assert shutil  # the real copy ran; nothing was stubbed in this test
