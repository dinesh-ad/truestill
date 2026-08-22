"""The bytes take the real name only once they are all there - `(acj)`.

**The observed defect `(abu)`:** `shutil.copy2` raised `[Errno 5]` at 802 MB of 852 MB and left
the 802 MB where it fell, carrying a correct organized name, with no `files` row and no
`file_copies` row. The run said `1 failed`. It did not say 802 MB of it arrived.

**What changed, and what these tests now have to assert.** The first fix removed the partial in an
`except`, which meant deciding whether a file at the target was ours - a wrong answer there
deletes a user's file. Staging removes the question: the copy goes to a sibling and only a
finished copy is renamed onto the target.

So the assertion is no longer "the partial was removed" but **"the target was never written"**,
and the difference is not cosmetic: the old cleanup satisfies "absent afterwards" too, so a test
phrased that way passes against both designs and distinguishes nothing. Where a test below can
observe the target *during* the failure it does, because that is the only moment the two designs
differ.
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


def test_the_target_is_never_written_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE DETECTOR, and the reason it is phrased this way.

    Asserting the target is absent *afterwards* is satisfied by removing a partial too, so it
    cannot tell this design from the one it replaced. What only staging can satisfy is that the
    target never existed **at the moment the copy died** - so the stub looks, from inside the
    failure, and records what it saw.
    """
    source = tmp_path / "in.mp4"
    source.write_bytes(b"x" * 100)
    target = tmp_path / "out" / "organized.mp4"
    target.parent.mkdir()
    seen: list[bool] = []

    def stub(_src: object, dst: object) -> None:
        Path(str(dst)).write_bytes(b"x" * 60)
        seen.append(target.exists())
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(safe_copy.shutil, "copy2", stub)

    outcome = copy_leaving_nothing(source, target)

    assert seen == [False], "the target existed while the copy was in flight"
    assert outcome.ok is False
    assert outcome.error is not None
    assert not target.exists()
    assert outcome.leftover is None


def test_a_file_this_copy_did_not_write_is_never_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ONE THAT DECIDES WHETHER THE FIX IS SAFE AT ALL.

    `copy2` opens the source first, so a failure before the destination is opened leaves whatever
    was already there untouched - and at two of three call sites something legitimately can be.
    A blind unlink in the `except` would delete a user's file to tidy up after an error that
    never touched it.

    **Held for a different reason since `(acj)`, and the test is kept for that reason.** It used
    to depend on an `exists()` taken at the right moment; now nothing is ever written at the
    target, so an incumbent cannot be reached by any failure path. The assertion is unchanged
    because the promise is - what changed is that it is now structural rather than careful.
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
    # The survivor is the STAGED sibling, never the target - which is the point rather than a
    # detail: what a crashed run leaves behind can no longer be mistaken for an organized photo,
    # because `.partial` is not a media extension.
    # ⚠ The CONTRACT, not the literal name. Since `(aaw)` the staged sibling carries a
    # per-process token, so pinning `name + STAGING_SUFFIX` would pin the very sharing that
    # let two runs write into one file. What must hold is that it is a sibling of the target,
    # names the target, and still ENDS in the suffix - which is what rescan's debris scan and
    # `scan_source`'s unrecognized-extension handling both key on.
    assert outcome.leftover == safe_copy.staging_path(target), (
        "the surviving staged copy was not named"
    )
    assert outcome.leftover is not None
    assert outcome.leftover.parent == target.parent, "the staged copy must be a sibling"
    assert outcome.leftover.name.startswith(target.name), "it must name what it was staging"
    assert outcome.leftover.name.endswith(safe_copy.STAGING_SUFFIX), (
        "debris detection keys on the suffix ENDING the name"
    )
    assert outcome.leftover.name != target.name + safe_copy.STAGING_SUFFIX, (
        "a staging name derived from the target alone is shared between processes - `(aaw)`"
    )
    assert outcome.leftover_bytes == 802, "the user is not told how much is sitting there"
    assert not target.exists(), "the target was written despite the failure"


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


def test_the_staged_name_is_derived_here_and_never_passed_in() -> None:
    """The same anti-drift pin on the staged form, and it guards a second thing.

    A staging path accepted from a caller could point outside the target's directory - which
    would make the final step a cross-filesystem rename, i.e. a copy, i.e. exactly the
    non-atomic write staging exists to avoid. Deriving it from the target is what makes
    "same directory" true by construction rather than by everyone remembering.
    """
    params = set(inspect.signature(safe_copy.staged_copy).parameters)

    assert params == {"source", "target"}, f"the staged form takes an opinion: {params}"


def test_committing_over_an_occupied_target_replaces_it(tmp_path: Path) -> None:
    """`Path.replace`, never `Path.rename` - and this test is only discriminating on Windows.

    Recorded because the mutation proving it did NOT fire here: POSIX `rename` overwrites
    silently, so on this lane the two calls are indistinguishable and swapping them kills
    nothing. On Windows `rename` raises when the target exists, and an occupied target is
    ordinary at two of the three call sites - `relocate` overwrites an interrupted run's copy by
    design, and `backup` writes paths the catalog may not know about.

    So the guard for that choice is the **Windows lane running this test**, not a mutation on a
    developer machine. Stated rather than left as a green tick that means less than it looks.
    """
    source = tmp_path / "in.jpg"
    source.write_bytes(b"new bytes")
    target = tmp_path / "organized.jpg"
    target.write_bytes(b"the incumbent")

    outcome = safe_copy.staged_copy(source, target).commit()

    assert outcome.ok is True, "committing onto an occupied target failed"
    assert target.read_bytes() == b"new bytes"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.jpg", "organized.jpg"]


def test_a_staged_copy_can_be_abandoned_without_touching_the_target(tmp_path: Path) -> None:
    """What `backup` needs: look at the bytes, then decide.

    A copy that does not verify must never take the real name - the window this closes is
    `(abu)`'s own shape one step later, where a bad copy was renamed into place and then removed.
    """
    source = tmp_path / "in.jpg"
    source.write_bytes(b"real bytes")
    target = tmp_path / "organized.jpg"
    target.write_bytes(b"THE INCUMBENT")

    staged = safe_copy.staged_copy(source, target)
    assert staged.ok is True
    assert staged.temp is not None
    assert staged.temp.read_bytes() == b"real bytes", "the staged bytes are not readable"
    assert target.read_bytes() == b"THE INCUMBENT", "staging touched the target"

    staged.abandon()

    assert target.read_bytes() == b"THE INCUMBENT", "abandoning took the incumbent with it"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.jpg", "organized.jpg"], (
        "the abandoned staged copy was left behind"
    )
