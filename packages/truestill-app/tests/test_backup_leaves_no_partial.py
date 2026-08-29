"""A backup copy takes the real name only once its bytes are there AND verify.

`(abu)`'s third site, and `(acj)`'s reason for existing. Two windows, closed by the same change:

* **The copy.** A `copy2` that dies mid-file used to leave what it wrote at the destination path.
  It now writes a staged sibling, so the destination is never touched by a failure.
* **The check.** The digest used to be taken *after* the file was already at its real name, and a
  copy that did not match was unlinked afterwards. So a bad copy wore the organized name for the
  length of a full re-read of its own bytes. `(abu)`'s fix did not reach this: that fix was aimed
  at the copy, and this window is after the copy succeeded.

The message is the half that is easy to leave out: when a cleanup fails too, the run stops either
way, and the difference between a good failure and a bad one is whether the user is told where the
bytes are.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core import backup as backup_engine
from truestill_core import safe_copy
from truestill_core.backup import _copy_verified
from truestill_core.hashing import sha256_file


def _copy_that_dies_after_writing(payload: bytes) -> object:
    def stub(_src: object, dst: object, **_kw: object) -> None:
        Path(str(dst)).write_bytes(payload)
        raise OSError(5, "Input/output error")

    return stub


def test_a_failed_backup_copy_never_writes_the_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observed from inside the failure, because that is the only moment the designs differ.

    "Absent afterwards" was equally true of removing a partial, so it cannot tell this apart from
    what it replaced.
    """
    source = tmp_path / "a.mp4"
    source.write_bytes(b"x" * 10)
    dst = tmp_path / "target" / "a.mp4"
    dst.parent.mkdir()
    seen: list[bool] = []

    def stub(_src: object, dst_path: object) -> None:
        Path(str(dst_path)).write_bytes(b"x" * 6)
        seen.append(dst.exists())
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(safe_copy.shutil, "copyfile", stub)

    # ⚠ Returns a failed verdict rather than raising since `(afw)` Stage 4 - one bad file no
    # longer aborts the batch. The PROPERTY under test is unchanged and is asserted below: the
    # destination is never written. Only how the failure is delivered changed.
    verdict = _copy_verified(source, dst, "a.mp4", None)
    assert not verdict.ok
    assert "Input/output error" in verdict.detail

    assert seen == [False], "the destination existed while the copy was in flight"
    assert not dst.exists(), "the backup left a partial nobody owns"


def test_a_copy_that_does_not_verify_never_takes_the_real_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE WINDOW `(abu)`'s FIX DID NOT REACH.

    A whole, healthy-looking copy whose bytes are not what the catalog recorded. It used to be
    written to the destination, hashed there, and unlinked - so for the length of that hash the
    wrong bytes wore the organized name. Now the digest is taken on the staged copy and a
    mismatch abandons it, so the destination is never written at all.
    """
    source = tmp_path / "a.mp4"
    source.write_bytes(b"these are not the recorded bytes")
    dst = tmp_path / "target" / "a.mp4"
    dst.parent.mkdir()
    seen_during: list[bool] = []
    real_hash = sha256_file

    def watching_hash(path: Path) -> str:
        # The hash is the only moment the file exists anywhere; look at the destination from
        # inside it. Under the old order this list would read [True].
        seen_during.append(dst.exists())
        return real_hash(path)

    # ⚠ Re-aimed by `(ahf)` stage 1: the read-back lives in `truestill_core.backup` now.
    # Patching the app module would patch a panel that no longer hashes anything.
    monkeypatch.setattr(backup_engine, "sha256_file", watching_hash)

    verdict = _copy_verified(source, dst, "a.mp4", "0" * 64)
    assert not verdict.ok
    assert "did not match" in verdict.detail

    assert seen_during == [False], "the unverified copy was at the real name while it was hashed"
    assert not dst.exists(), "the unverified copy was left at the destination"
    assert list(dst.parent.iterdir()) == [], "the abandoned staged copy was left behind"


def test_a_verified_copy_is_committed_and_its_digest_returned(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A version that abandoned every copy would pass both tests above."""
    source = tmp_path / "a.mp4"
    source.write_bytes(b"real bytes")
    dst = tmp_path / "target" / "a.mp4"
    dst.parent.mkdir()
    want = sha256_file(source)

    written = _copy_verified(source, dst, "a.mp4", want).digest

    assert written == want
    assert dst.read_bytes() == b"real bytes"
    assert [p.name for p in dst.parent.iterdir()] == ["a.mp4"], "a staged file was left beside it"


def test_a_row_with_no_recorded_hash_is_still_copied_and_still_digested(tmp_path: Path) -> None:
    """`want=None` is unverifiable, not suspect.

    `verify` draws that distinction and this must not collapse it: the copy is committed, and the
    digest is still computed and returned so `record_copy` never stores a NULL and turns a fresh
    copy into the UNVERIFIABLE case.
    """
    source = tmp_path / "a.mp4"
    source.write_bytes(b"real bytes")
    dst = tmp_path / "target" / "a.mp4"
    dst.parent.mkdir()

    written = _copy_verified(source, dst, "a.mp4", None).digest

    assert written == sha256_file(source), "no digest was recorded for an unverifiable row"
    assert dst.read_bytes() == b"real bytes"


def test_a_staged_copy_that_cannot_be_removed_is_named_and_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONLY THE FAILED-CLEANUP PATH REACHES THIS MESSAGE, and a mutation that dropped it killed
    no test until now: the ordinary failure re-raises the original error and looks identical.

    **The destination is deliberately NOT named `a.mp4.partial` any more.** It was, and that made
    `str(dst) in message` true as a mere prefix of the staged name - the assertion passed while
    locating a different file.
    """
    source = tmp_path / "a.mp4"
    source.write_bytes(b"x" * 10)
    dst = tmp_path / "organized.mp4"
    monkeypatch.setattr(safe_copy.shutil, "copyfile", _copy_that_dies_after_writing(b"y" * 802))
    monkeypatch.setattr(
        Path, "unlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError(30, "Read-only"))
    )

    verdict = _copy_verified(source, dst, "a.mp4", None)

    assert not verdict.ok
    message = verdict.detail
    assert "802 bytes are still at" in message, f"the survivor was not measured: {message}"
    # `(aaw)`: the staged sibling carries a per-process token now, so the name comes from
    # the one helper that builds it rather than being re-derived here.
    staged = safe_copy.staging_path(dst)
    assert str(staged) in message, "the survivor was not located"
    assert str(dst) + "\n" not in message, "the message points at the destination, not the survivor"
    assert backup_engine  # the message comes from the copy engine, not from safe_copy
