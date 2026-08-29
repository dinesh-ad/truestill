"""(F3) LocalDestination must raise DestinationError, not raw OSError."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from truestill_core.destinations.base import DestinationError
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive_unwritable import persists_for_the_run
from truestill_core.migrate import _matches


def test_local_checksum_translates_oserror_to_destination_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ABC contract: checksum raises DestinationError; a raw OSError is the bug."""
    (tmp_path / "a.bin").write_bytes(b"present")
    dest = LocalDestination(tmp_path)

    def boom(_path: Path) -> str:
        raise OSError(errno.EIO, "Input/output error", "a.bin")

    monkeypatch.setattr("truestill_core.destinations.local.sha256_file", boom)
    with pytest.raises(DestinationError, match="cannot checksum"):
        dest.checksum("a.bin")


def test_migrate_matches_hands_an_unreadable_checksum_on_to_be_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_matches` must not let an `OSError` abort a migration mid-move.

    ⚠ **THE PROMISE IS UNCHANGED AND THE MECHANISM KEEPING IT IS NOT** (`(agm)`, 2026-08-24).
    This asserted `_matches(...) is False`, because when it was written `run_migration` had no
    handler at all and swallowing was the only protection available. **It did not actually
    work**: `False` sent `_apply_move` on to relocate onto a drive that had just failed a read,
    verify again, and raise a bare `DestinationError` that escaped the run - measured. Worse, the
    swallow destroyed the `__cause__`, so `persists_for_the_run` answered `False` for a failing
    drive and the run would have continued into it once a handler existed.

    The promise is now kept where it belongs: the error propagates with its chain, and
    `run_migration` classifies it and returns an outcome. Asserted here **and** end-to-end in
    `test_migrate_survives_one_bad_file.py`, because this half only proves the chain survives.
    """
    (tmp_path / "a.bin").write_bytes(b"present")
    dest = LocalDestination(tmp_path)

    def boom(_path: Path) -> str:
        raise OSError(errno.EIO, "Input/output error", "a.bin")

    monkeypatch.setattr("truestill_core.destinations.local.sha256_file", boom)
    with pytest.raises(DestinationError) as caught:
        _matches(dest, "a.bin", "0" * 64)

    assert persists_for_the_run(caught.value), "the chain must survive for `(agi)` to classify it"


def test_migrate_matches_still_answers_false_for_a_hash_that_simply_differs(
    tmp_path: Path,
) -> None:
    """The cry-wolf half: only a FAILED READ propagates. A mismatch is still a plain `False`.

    Without this, deleting the `try`/`except` and the `exists` check together would pass the test
    above while breaking the resume path, which relies on a mismatch meaning *"relocate it"*.
    """
    (tmp_path / "a.bin").write_bytes(b"present")

    assert _matches(LocalDestination(tmp_path), "a.bin", "0" * 64) is False
    assert _matches(LocalDestination(tmp_path), "gone.bin", "0" * 64) is False


def _copy_fails_with(monkeypatch: pytest.MonkeyPatch, number: int, text: str) -> None:
    """Make the copy raise a given errno, on the module that performs it (guard rule 3).

    That module changed on 2026-08-10: `LocalDestination.upload` no longer calls the copy
    itself, it calls `safe_copy.copy_leaving_nothing`, which does - and which removes a partial
    it wrote before the error is reported (`(abu)`). The rule is unchanged and the aim moved with
    the code; patching `destinations.local` would now patch a name that is not there.

    ⚠ **`copyfile`, not `copy2`, since `(aie)`.** The two calls `copy2` was are now made
    separately, because only the first one failing means the bytes did not arrive - and this
    helper is about the failures that discard, so it must aim at the data step. A `copy2` patch
    would land on a name `safe_copy` no longer calls and every test using this would go green
    against a real copy.
    """

    def boom(_src: Path, _dst: Path) -> Path:
        raise OSError(number, text)

    monkeypatch.setattr("truestill_core.safe_copy.shutil.copyfile", boom)


def test_efbig_is_named_as_the_fat32_limit_rather_than_passed_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``[Errno 27] File too large`` against a drive showing 200 GB free reads as truestill
    being broken. The only reading a user can act on is the one that names FAT32.

    The preflight catches this case before the run starts; this covers the copy that still
    fails - a file that grew after the check, or a limit no platform could report.
    """
    (tmp_path / "VID_4K.mp4").write_bytes(b"\x00" * 16)
    _copy_fails_with(monkeypatch, errno.EFBIG, "File too large")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "VID_4K.mp4", "Camera/2024/VID_4K.mp4")

    message = str(raised.value)
    assert "VID_4K.mp4" in message
    assert "FAT32" in message, f"the reason was not named: {message}"
    assert "4 GB" in message
    assert "27" not in message, "the raw errno leaked into a user-facing sentence"


def test_an_ordinary_copy_failure_is_not_dressed_up_as_a_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf direction: a full disk (ENOSPC) is a different problem with a different
    fix, and telling that user to reformat their drive as exFAT would be actively wrong."""
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8")
    _copy_fails_with(monkeypatch, errno.ENOSPC, "No space left on device")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "a.jpg", "Camera/2024/a.jpg")

    assert "FAT32" not in str(raised.value)


def test_a_failed_copy_says_neither_upload_nor_a_raw_errno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(aep)`: the two §9 violations that lived in one fall-through line.

    Reproduced verbatim on 2026-08-21 against a destination that refused the write::

        FAILED: IMG_0001.png: cannot upload to 'Saved/Undated/IMG_0001.png':
                [Errno 13] Permission denied: '/.../dest3/Saved'

    ⚠ **The existing guard could not see this.** `test_status_labels_cover_every_outcome` asserts
    every `ActionStatus` has a user-facing **label**, and says nothing about `detail` - the free
    string that carries the leak. A guard aimed at the right subject through a lens that cannot
    resolve part of it, which is §4's fifty-fourth member.
    """
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8")
    _copy_fails_with(monkeypatch, errno.EACCES, "Permission denied")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "a.jpg", "Camera/2024/a.jpg")

    message = str(raised.value)
    assert "upload" not in message, "backend vocabulary reached a user-facing sentence"
    assert "Errno" not in message, "the raw errno leaked into a user-facing sentence"
    assert "13" not in message, "the errno number leaked into a user-facing sentence"
    # The worded reason from the product's one errno table, not the OS's raw string.
    assert "read-only, or this account cannot write to it" in message
    assert "a.jpg" in message, "the file the user cares about is not named"


def test_the_folder_step_fails_in_the_same_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sibling path that fails BEFORE any bytes move, and used to leak identically.

    Two sites wording one condition is how they drift the first time either is corrected, so both
    read the same table - `(aep)`, and §4's rule that the remedy is usually to delete one of two
    copies rather than to add a second assertion.
    """

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", boom)

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "a.jpg", "Camera/2024/a.jpg")

    message = str(raised.value)
    assert "upload" not in message
    assert "Errno" not in message
    assert "read-only, or this account cannot write to it" in message


def test_a_full_disk_still_gets_its_own_words_rather_than_a_shared_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CRY-WOLF HALF, and the reason `(aek)`'s table is reused rather than flattened.

    Without this the fix could have replaced one raw errno with one generic sentence and passed
    the two tests above. `ENOSPC` and `EACCES` need **opposite** advice - delete something, versus
    check permissions - and the table exists precisely to keep them apart.
    """
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8")
    _copy_fails_with(monkeypatch, errno.ENOSPC, "No space left on device")

    with pytest.raises(DestinationError) as raised:
        LocalDestination(tmp_path).upload(tmp_path / "a.jpg", "Camera/2024/a.jpg")

    message = str(raised.value)
    assert "no space left on the drive" in message
    assert "read-only" not in message, "a full disk was worded as a permission problem"
    assert "FAT32" not in message
