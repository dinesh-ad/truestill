"""A copy that fails leaves nothing behind - but only removes what it wrote itself.

**The observed defect `(abu)`:** `shutil.copy2` raised `[Errno 5]` at 802 MB of 852 MB and left
the 802 MB where it fell, carrying a correct organized name, with no `files` row and no
`file_copies` row. The run said `1 failed`. It did not say 802 MB of it arrived.

**Why a blind unlink in the `except` would be worse than the debris.** `copy2` opens the SOURCE
first. A failure before the destination is opened - unreadable source, denied permission, a
parent that could not be made - leaves the target untouched. At two of the three call sites that
target can legitimately already exist: `relocate` overwrites a partial from an interrupted run by
design, and `backup` builds its work list from the CATALOG, so a file the catalog does not know
about can be sitting there. Deleting it would be this fix destroying a user's file.

So the rule is **remove only what this call created**, decided by an `exists()` check taken
immediately before the copy rather than trusted from a caller.
"""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path

import pytest
from truestill_core import safe_copy
from truestill_core.safe_copy import copy_leaving_nothing


def _fails_after_writing(payload: bytes) -> object:
    """A `copy2` that writes some bytes and then dies, like a disk going away mid-file."""

    def stub(_src: object, dst: object, **_kw: object) -> None:
        Path(str(dst)).write_bytes(payload)
        raise OSError(5, "Input/output error")

    return stub


def _fails_before_touching_anything(*_args: object, **_kw: object) -> None:
    """A `copy2` that dies opening the SOURCE, so the destination is never touched."""
    raise PermissionError(13, "Permission denied")


def test_a_partial_this_copy_wrote_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE DEFECT ITSELF. 802 MB with an organized name and nothing owning it."""
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "out" / "organized.mp4"
    target.parent.mkdir()
    monkeypatch.setattr(safe_copy.shutil, "copy2", _fails_after_writing(b"x" * 60))

    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is False
    assert outcome.error is not None
    assert not target.exists(), "the partial was left behind"
    assert outcome.leftover is None


def test_a_file_this_copy_did_not_write_is_never_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ONE THAT DECIDES WHETHER THE FIX IS SAFE AT ALL.

    `copy2` opens the source first, so a failure before the destination is opened leaves whatever
    was already there untouched - and at two of three call sites something legitimately can be.
    A blind unlink in the `except` would delete a user's file to tidy up after an error that
    never touched it.
    """
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "already-here.mp4"
    target.write_bytes(b"THIS IS THE USER'S FILE")
    monkeypatch.setattr(safe_copy.shutil, "copy2", _fails_before_touching_anything)

    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is False
    assert target.read_bytes() == b"THIS IS THE USER'S FILE", (
        "the fix deleted a file it did not write"
    )
    assert outcome.leftover is None, "an untouched incumbent is not a leftover of ours"


def test_when_the_cleanup_itself_fails_the_leftover_is_named_and_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure that produced the partial is often the one that refuses the delete - a
    disconnected drive, a read-only mount, the same I/O error. The cleanup must never raise, and
    the user must end up with a WORSE message rather than a silent one: 800 MB across a slow link
    deserves to be named, not wondered about.
    """
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "partial.mp4"
    monkeypatch.setattr(safe_copy.shutil, "copy2", _fails_after_writing(b"y" * 802))

    def refuse_unlink(*_args: object, **_kw: object) -> None:
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(Path, "unlink", refuse_unlink)
    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is False
    assert outcome.leftover == target, "the surviving partial was not named"
    assert outcome.leftover_bytes == 802, "the user is not told how much is sitting there"


def test_a_successful_copy_reports_success_and_keeps_the_file(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A helper that removed the file on the happy path would pass every test
    above and organize nothing."""
    source = tmp_path / "in.jpg"
    source.write_bytes(b"real bytes")
    target = tmp_path / "out" / "organized.jpg"
    target.parent.mkdir()

    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is True
    assert outcome.error is None
    assert target.read_bytes() == b"real bytes"
    assert shutil  # the real copy2 ran; nothing was stubbed in this test


def test_a_retry_after_a_cleaned_failure_does_not_accumulate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(abu)`'s sharp end. `_free_relative` suffixes rather than overwrites - correct for two
    distinct `IMG_0001.jpg` - so before this fix a retry saw the partial as an incumbent and
    wrote `..._1.mp4` beside it. Every retry left another 802 MB.
    """
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "organized.mp4"
    monkeypatch.setattr(safe_copy.shutil, "copy2", _fails_after_writing(b"x" * 60))
    assert copy_leaving_nothing(source, target).ok is False

    monkeypatch.undo()
    outcome = copy_leaving_nothing(source, target)

    assert outcome.ok is True
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.mp4", "organized.mp4"], (
        "the retry landed beside a surviving partial instead of at the name it wanted"
    )


def test_the_decision_is_taken_here_and_never_passed_in() -> None:
    """ANTI-DRIFT, and it is what makes the TOCTOU window unreachable as a data-loss path.

    A caller that checked `exists()` earlier - `_free_relative` does, some lines before the write
    - could pass a stale answer, and a stale "it was free" is exactly the input that turns this
    into a delete of someone else's file. The check is taken immediately before the copy and the
    signature offers no way to override it.
    """
    params = set(inspect.signature(copy_leaving_nothing).parameters)

    assert params == {"source", "target"}, f"the helper accepts a caller's opinion: {params}"
