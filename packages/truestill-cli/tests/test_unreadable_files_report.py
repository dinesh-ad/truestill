"""The CLI names the source files it could not read, on both the preview and the run.

`BACKLOG.md` ``(aac)``. The engine has known which files it could not read since ``(aac)``'s
scan fix; this is the surface that says so out loud, and the reason a preview no longer exits 0
on a library it could not fully account for.

Nothing here touches the filesystem: these are report-shape tests over synthetic
:class:`Resolution` values, which is what lets them run identically on all three CI lanes.
"""

from __future__ import annotations

import errno
import shutil
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_cli.cli import _STATUS_PREVIEW, _print_unreadable, main
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    UnreadableReason,
)


def _resolution(name: str, reason: UnreadableReason | None) -> Resolution:
    decision = Decision(
        source=Path("/src") / name,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.HIGH, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=None, perceptual=None, unreadable=reason),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_the_cli_names_unreadable_files_with_the_reason_for_each(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Count, names, and a reason per file - three different next actions, so three wordings."""
    named = _print_unreadable(
        [
            _resolution("DSC_0042.jpg", UnreadableReason.PERMISSION),
            _resolution("IMG_1180.heic", UnreadableReason.IO_ERROR),
            _resolution("clip.mp4", UnreadableReason.MISSING),
            _resolution("fine.jpg", None),
        ]
    )
    out = capsys.readouterr().out

    assert named == 3, "the readable file must not be counted among the failures"
    assert "files that could not be read: 3" in out
    # The whole rendered line, not the two halves separately: co-presence somewhere in the
    # output would pass even if every reason were attached to the wrong file.
    assert "DSC_0042.jpg  (permission denied)" in out
    assert "IMG_1180.heic  (input/output error)" in out
    assert "clip.mp4  (disappeared during the scan)" in out
    assert "fine.jpg" not in out, "a readable file must never appear in this block"
    # §9: no backend vocabulary reaches a user. `permission` is not checked here because the
    # value collides with ordinary English - the guidance line legitimately says "fix the
    # permission" - so the two that cannot collide are checked instead, plus the enum repr.
    assert UnreadableReason.IO_ERROR.value not in out, "the raw enum value leaked to the user"
    assert UnreadableReason.MISSING.value not in out, "the raw enum value leaked to the user"
    assert "UnreadableReason" not in out


def test_the_block_is_silent_when_every_file_was_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The cry-wolf half: an ordinary run must not grow a scary empty section."""
    named = _print_unreadable([_resolution("a.jpg", None), _resolution("b.jpg", None)])

    assert named == 0
    assert capsys.readouterr().out == ""


def test_the_list_elides_past_twenty_and_says_how_many_it_hid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Truncation is never silent - the same bargain `_duplicate_report` strikes in the app.

    A tree of readable directories full of unreadable files can produce thousands of these, so
    the list is capped. The count above it is not, which is the part a user needs.
    """
    named = _print_unreadable(
        [_resolution(f"p{i:03d}.jpg", UnreadableReason.PERMISSION) for i in range(25)]
    )
    out = capsys.readouterr().out

    assert named == 25
    assert "files that could not be read: 25" in out, "the count must be the true count"
    assert out.count("permission denied") == _STATUS_PREVIEW
    assert f"... and {25 - _STATUS_PREVIEW} more." in out


def test_a_run_never_names_the_same_file_twice(capsys: pytest.CaptureFixture[str]) -> None:
    """On a run an unreadable file also FAILS the copy, and `_print_execution` already says so.

    Naming it once vaguely and once precisely is worse than either alone, so the FAILED set is
    subtracted here. The FAILED line wins because it is the later observation and carries the
    real ``OSError`` text.
    """
    doomed = _resolution("doomed.jpg", UnreadableReason.PERMISSION)
    duplicate = _resolution("cached-dup.jpg", UnreadableReason.PERMISSION)
    failed = ActionResult(doomed, ActionStatus.FAILED, None, "Permission denied")

    named = _print_unreadable([doomed, duplicate], _failed_sources([failed]))
    out = capsys.readouterr().out

    assert "doomed.jpg" not in out, "already named by the EXECUTED block as FAILED"
    assert "cached-dup.jpg" in out, (
        "an unreadable file that was never copied - a cached exact duplicate - produces no "
        "FAILED result, so this block is the only place it is ever named"
    )
    assert named == 1


def _failed_sources(results: list[ActionResult]) -> frozenset[Path]:
    return frozenset(
        r.resolution.decision.source for r in results if r.status is ActionStatus.FAILED
    )


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_a_preview_over_an_unreadable_file_exits_one_not_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole command, end to end: exit 1, because the run it predicts will exit 1.

    This is the user-visible contract change. ``truestill organize <src> <dst> && next_step``
    used to chain past a library truestill could not fully account for; now it stops. The pair
    of assertions matters more than either alone - the readable half proves the new code is not
    simply failing every preview.
    """
    source = tmp_path / "src"
    source.mkdir()
    _jpeg_on_disk(source / "readable.jpg", colour="red")
    _jpeg_on_disk(source / "locked.jpg", colour="blue")

    clean = main(["organize", str(source), str(tmp_path / "out"), "--db", str(tmp_path / "a.db")])
    assert clean == 0, "fixture check: an all-readable preview must still exit 0"
    assert "could not be read" not in capsys.readouterr().out

    _deny_open(monkeypatch, name="locked.jpg", exc=PermissionError(errno.EACCES, "denied"))
    code = main(["organize", str(source), str(tmp_path / "out"), "--db", str(tmp_path / "b.db")])
    out = capsys.readouterr().out

    assert code == 1, (
        "a preview that cannot read one of the user's photos must not report success; the run "
        "will exit 1 on that same file through ActionStatus.FAILED"
    )
    assert "files that could not be read: 1" in out
    assert "locked.jpg  (permission denied)" in out
    assert "DRY RUN" in out, "the exit code changed; the preview itself did not"


def _jpeg_on_disk(path: Path, *, colour: str) -> None:
    Image.new("RGB", (64, 64), colour).save(path)


def _deny_open(monkeypatch: pytest.MonkeyPatch, *, name: str, exc: OSError) -> None:
    """Deny one filename at ``Path.open``, which works identically on all three CI lanes."""
    real = Path.open

    def fake(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == name:
            raise exc
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake)
