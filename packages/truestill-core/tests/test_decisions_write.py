"""Putting the decisions document on a drive, without ever risking the copy already there.

**Two properties, and the second is the harder one.**

1. **Atomic.** A crash between writing and renaming must leave the PREVIOUS good document
   untouched. This file is the only copy of names a human typed; a half-written one is worse than
   none, because it looks like a backup.
2. **It can never fail the user's actual work.** Naming a trip must succeed even when the drive
   write does not. A decision lost because its own backup failed is the worst trade available, so
   every failure comes back as a reported outcome and nothing raises into the caller.

A drive that is read-only, full, or gone mid-write is a normal Tuesday for a removable disk. Each
is reported in words rather than swallowed.
"""

from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path

import pytest
from truestill_core.decisions import (
    DECISIONS_NAME,
    Decisions,
    from_document,
    write_decisions,
)

_GOOD = Decisions(
    drive_uuid="u-1",
    drive_label="Output",
    trips=({"name": "Wayanad", "slug": "wayanad", "start": "2014-08-14", "end": "2014-08-17"},),
    written="2026-08-09T12:00:00+00:00",
)
_NEWER = Decisions(
    drive_uuid="u-1",
    drive_label="Output",
    trips=({"name": "Kerala", "slug": "kerala", "start": "2014-08-14", "end": "2014-08-17"},),
    written="2026-08-10T12:00:00+00:00",
)


def test_it_writes_a_document_a_person_can_read(tmp_path: Path) -> None:
    outcome = write_decisions(tmp_path, _GOOD)

    assert outcome.written is True
    assert outcome.path == tmp_path / DECISIONS_NAME
    assert outcome.error is None
    text = (tmp_path / DECISIONS_NAME).read_text(encoding="utf-8")
    assert "Wayanad" in text
    assert text.count("\n") > 5, "collapsed to one line; the point is that a human can read it"
    assert from_document(json.loads(text)).trips[0]["name"] == "Wayanad"


def test_it_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    write_decisions(tmp_path, _GOOD)

    assert [p.name for p in tmp_path.iterdir()] == [DECISIONS_NAME]


# --- atomicity: the property that protects the only copy ----------------------------------


def test_a_crash_between_write_and_rename_leaves_the_previous_document_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ONE THAT MATTERS. Interrupted exactly where a half-file would appear.

    Asserted on the CONTENT of the old document, not merely that a file exists: a truncated or
    empty file at the right path is precisely the failure this guards, and it would satisfy an
    existence check.
    """
    assert write_decisions(tmp_path, _GOOD).written is True
    before = (tmp_path / DECISIONS_NAME).read_text(encoding="utf-8")

    def die(*_args: object, **_kwargs: object) -> None:
        message = "interrupted between write and rename"
        raise OSError(message)

    # Patched on `Path.replace`, which is what the code calls. Patching `os.replace`
    # would still work today because pathlib delegates to it, but a test that guards
    # atomicity must intercept the exact call it is guarding.
    monkeypatch.setattr(Path, "replace", die)
    outcome = write_decisions(tmp_path, _NEWER)

    assert outcome.written is False
    assert outcome.error, "a failed write must say why"
    assert (tmp_path / DECISIONS_NAME).read_text(encoding="utf-8") == before
    assert "Wayanad" in before
    assert "Kerala" not in before
    assert [p.name for p in tmp_path.iterdir()] == [DECISIONS_NAME], "a temp file was left behind"


def test_the_temporary_file_sits_beside_the_target(tmp_path: Path) -> None:
    """Same directory, so the rename is same-filesystem and can be atomic. A temp in /tmp would
    make the final step a copy across devices, which is exactly what must not happen here."""
    seen: list[Path] = []
    real = Path.replace

    def watch(self: Path, target: object) -> object:
        seen.append(self)
        return real(self, target)  # type: ignore[arg-type]

    original = Path.replace
    Path.replace = watch  # type: ignore[assignment,method-assign]
    try:
        write_decisions(tmp_path, _GOOD)
    finally:
        Path.replace = original  # type: ignore[method-assign]

    assert seen, "nothing was renamed; the write was not atomic"
    assert seen[0].parent == tmp_path


# --- failure is reported, never raised ----------------------------------------------------


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="a read-only directory is POSIX permissions, and root ignores them",
)
def test_a_read_only_drive_is_reported_rather_than_raised(tmp_path: Path) -> None:
    """A disk with the write-protect tab on is a normal Tuesday, not an exception.

    POSIX-only, and it took a Windows CI lane to find out: `chmod(0o500)` on a directory does
    nothing there, so this asserted a failure that could not happen. One condition, platform
    first - see `test_platform_skips_collect_everywhere.py`.
    """
    root = tmp_path / "drive"
    root.mkdir()
    root.chmod(0o500)
    try:
        outcome = write_decisions(root, _GOOD)
    finally:
        root.chmod(0o700)

    assert outcome.written is False
    assert outcome.error is not None
    assert "read-only" in outcome.error.lower()


def test_a_full_drive_is_reported_rather_than_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_space(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "fsync", no_space)
    outcome = write_decisions(tmp_path, _GOOD)

    assert outcome.written is False
    assert outcome.error is not None
    assert "space" in outcome.error.lower()
    assert not (tmp_path / DECISIONS_NAME).exists(), "a partial file survived a full disk"
    assert list(tmp_path.iterdir()) == [], "the temp file was left behind on a full disk"


def test_a_missing_drive_root_is_reported_rather_than_raised(tmp_path: Path) -> None:
    """The user pulled the disk out. That is not a crash."""
    outcome = write_decisions(tmp_path / "not-there", _GOOD)

    assert outcome.written is False
    assert outcome.error


def test_no_failure_mode_raises(tmp_path: Path) -> None:
    """The blanket promise, asserted rather than assumed: naming a trip must succeed even when
    the drive write cannot, so nothing here may propagate into the caller."""
    empty_root = Path("")  # noqa: PTH201 - the empty path IS the input under test here
    for root in (tmp_path / "missing", Path("/proc/nonexistent-truestill"), empty_root):
        outcome = write_decisions(root, _GOOD)
        assert outcome.written is False
        assert outcome.error
