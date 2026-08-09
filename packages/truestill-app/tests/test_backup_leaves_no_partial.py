"""A backup copy that fails leaves nothing it wrote, and says so when it cannot.

`(abu)`'s third site. The work list comes from `_files_missing_on_target`, which reads the
CATALOG rather than the disk - so a file the catalog does not know about can already be sitting
at the destination, and that one is not ours to delete. What this call wrote, it removes.

The message is the half that is easy to leave out: when the cleanup fails too, the run stops
either way, and the difference between a good failure and a bad one is whether the user is told
where the bytes are.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_app.service import backup as backup_service
from truestill_app.service.backup import _copy_or_raise
from truestill_core import safe_copy


def _copy_that_dies_after_writing(payload: bytes) -> object:
    def stub(_src: object, dst: object, **_kw: object) -> None:
        Path(str(dst)).write_bytes(payload)
        raise OSError(5, "Input/output error")

    return stub


def test_a_partial_from_a_failed_backup_copy_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "a.mp4"
    source.write_bytes(b"x" * 10)
    dst = tmp_path / "target" / "a.mp4"
    dst.parent.mkdir()
    monkeypatch.setattr(safe_copy.shutil, "copy2", _copy_that_dies_after_writing(b"x" * 6))

    with pytest.raises(OSError, match="Input/output error"):
        _copy_or_raise(source, dst, "a.mp4")

    assert not dst.exists(), "the backup left a partial nobody owns"


def test_a_partial_that_cannot_be_removed_is_named_and_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONLY THE FAILED-CLEANUP PATH REACHES THIS MESSAGE, and a mutation that dropped it killed
    no test until now: the ordinary failure re-raises the original error and looks identical."""
    source = tmp_path / "a.mp4"
    source.write_bytes(b"x" * 10)
    dst = tmp_path / "a.mp4.partial"
    monkeypatch.setattr(safe_copy.shutil, "copy2", _copy_that_dies_after_writing(b"y" * 802))
    monkeypatch.setattr(
        Path, "unlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError(30, "Read-only"))
    )

    with pytest.raises(OSError, match="could not be removed") as raised:
        _copy_or_raise(source, dst, "a.mp4")

    message = str(raised.value)
    assert "802 bytes are still at" in message, f"the surviving partial was not measured: {message}"
    assert str(dst) in message, "the surviving partial was not located"
    assert backup_service  # the message comes from the backup service, not from core
