"""(aek) Writing a drive marker must refuse in a sentence and leave nothing behind.

The soak found `organize` into an unregistered destination dying on a full disk with an unhandled
`OSError` and a `pathlib` traceback, a few steps from a copy path that handles the same errno
impeccably. `write_marker` is the two lines that raised.

**Two failure modes, two tests, and collapsing them proves nothing.** `EACCES` fails at `open`, so
no file is ever created and "no debris" is true whatever the code does. `ENOSPC` fails at the
*write*, after `O_CREAT|O_TRUNC` has already taken the name - which is what left a zero-byte
`.truestill-drive.json` at the drive root, the only truestill-named artifact this product ever
writes to a user's disk (`IMPLEMENTATION_STANDARDS.md` §3.1). The debris assertion belongs to the
write-time failure alone; asserting it on the permission case would pass for the wrong reason
(`ENGINEERING_STANDARD.md` §4, thirteenth member).

The contract mirrors `decisions.write_decisions`, which is older, proven, and pinned by
`test_decisions_write.py` - one wording, one staging discipline, two callers.
"""

from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path

import pytest
from truestill_core.drive import (
    MARKER_NAME,
    DriveMarker,
    read_marker,
    write_marker,
)

_MARKER = DriveMarker(
    uuid="11111111-2222-3333-4444-555555555555",
    label="The Memory Cabinet",
    created="2026-08-21T00:00:00+00:00",
)


def _no_space(*_args: object, **_kwargs: object) -> None:
    raise OSError(errno.ENOSPC, "No space left on device")


def test_it_writes_a_marker_a_later_read_can_use(tmp_path: Path) -> None:
    """The happy path, first - a guard whose subject never succeeds proves nothing either."""
    outcome = write_marker(tmp_path, _MARKER)

    assert outcome.written is True
    assert outcome.path == tmp_path / MARKER_NAME
    assert outcome.error is None
    assert read_marker(tmp_path) == _MARKER
    assert json.loads((tmp_path / MARKER_NAME).read_text(encoding="utf-8"))["uuid"] == _MARKER.uuid


def test_it_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    """The cry-wolf half of the staging: a SUCCESSFUL write leaves the marker and nothing else."""
    write_marker(tmp_path, _MARKER)

    assert [p.name for p in tmp_path.iterdir()] == [MARKER_NAME]


def test_a_full_drive_is_reported_rather_than_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The soak's own condition. Aimed at the module that performs the flush, never at `pathlib`.

    The debris assertion lives here rather than on the permission test because this is the only
    failure that gets past `open`: `write_text` takes the real name with `O_CREAT|O_TRUNC` and
    then fails, which is exactly how a zero-byte marker was left on a full disk.
    """
    monkeypatch.setattr("truestill_core.drive.os.fsync", _no_space)
    outcome = write_marker(tmp_path, _MARKER)

    assert outcome.written is False
    assert outcome.error is not None
    assert "space" in outcome.error.lower()
    assert not (tmp_path / MARKER_NAME).exists(), "a zero-byte marker survived a full disk"
    assert list(tmp_path.iterdir()) == [], "the staged file was left behind on a full disk"


def test_a_quota_exhausted_drive_says_allowance_rather_than_no_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EDQUOT was the errno the soak actually hit (122), and the drive may have plenty of room.

    Its own sentence rather than ENOSPC's: telling someone their drive is full when the drive is
    not full sends them to delete files that were never the problem.
    """
    quota = getattr(errno, "EDQUOT", None)
    if quota is None:  # pragma: no cover - platform without the errno
        pytest.skip("this platform has no EDQUOT")

    def exhausted(*_args: object, **_kwargs: object) -> None:
        raise OSError(quota, "Disk quota exceeded")

    monkeypatch.setattr("truestill_core.drive.os.fsync", exhausted)
    outcome = write_marker(tmp_path, _MARKER)

    assert outcome.written is False
    assert outcome.error is not None
    assert "allowance" in outcome.error.lower()
    assert "no space left" not in outcome.error.lower(), "a quota is not a full drive"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="a read-only directory is POSIX permissions, and root ignores them",
)
def test_a_read_only_drive_is_reported_rather_than_raised(tmp_path: Path) -> None:
    """The ordering fix cannot cover this one: there is nothing to preflight against.

    ONE `skipif` condition, platform first - two stacked decorators both evaluate at import and
    `os.geteuid` does not exist on Windows, which fails the whole module's collection
    (`test_platform_skips_collect_everywhere.py`).

    No debris assertion here on purpose - see the module docstring.
    """
    root = tmp_path / "drive"
    root.mkdir()
    root.chmod(0o500)
    try:
        outcome = write_marker(root, _MARKER)
    finally:
        root.chmod(0o700)

    assert outcome.written is False
    assert outcome.error is not None
    assert "read-only" in outcome.error.lower()


def test_no_failure_mode_raises(tmp_path: Path) -> None:
    """The blanket promise, asserted rather than assumed - the whole of `(aek)` in one line.

    Real conditions only. A path carrying a null byte raises `ValueError` from pathlib before any
    syscall happens, and widening the `except` to swallow that would be tuning the contract to fit
    a case no destination can reach: a root comes from argparse or a folder browse, never from
    arbitrary bytes.

    **No absolute-path guard here, deliberately**, and this is where `write_marker` and
    `write_decisions` part company. That one requires an absolute root because `Path("")`
    normalises to `.` and it would otherwise write into the working directory. A drive root there
    always comes from the catalog; here `truestill organize src dest` with a relative `dest` is
    ordinary use, so the same guard would refuse a legitimate run.
    """
    a_file = tmp_path / "not-a-folder"
    a_file.write_text("this is a file, not a drive root", encoding="utf-8")
    for root in (Path("/proc/nonexistent-truestill/drive"), a_file):
        outcome = write_marker(root, _MARKER)
        assert outcome.written is False, root
        assert outcome.error, root
