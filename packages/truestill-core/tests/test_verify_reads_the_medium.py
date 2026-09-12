"""`verify` reads the device, not the page cache. Ruled 2026-09-12 from a real-drive measurement.

⚠ **THE DEFECT, MEASURED RATHER THAN REASONED.** On a real exFAT drive over USB the same 161
copies verified in **1.33 s** reading cache and **6.51 s** reading the drive, and printed
`verified: 161` both times. A user can back up, verify green, pull the drive and lose most of it -
`backup` left **240 MB of a 297 MB copy dirty in RAM** when it printed its summary.

`safe_copy`'s recorded decision not to `fsync` rests on the sentence *"`copy_sha256` and `verify`
already own"* whether content survives power loss. Verify did not own it. That is why this is a
correctness guard and not a performance one.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from truestill_core import hashing
from truestill_core import verify as verify_module
from truestill_core.hashing import (
    CAN_READ_FROM_THE_MEDIUM,
    sha256_file,
    sha256_from_the_medium,
)
from truestill_core.verify import MEDIUM_READ_UNAVAILABLE


def test_the_two_hashes_agree(tmp_path: Path) -> None:
    """The anti-vacuity anchor. Forcing a cold read must not change the answer - if it did, every
    assertion about eviction below would be measuring a broken hash instead."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8" + bytes(range(256)) * 400)

    assert sha256_from_the_medium(target) == sha256_file(target)


def test_verify_hashes_through_the_medium_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ **The wiring, which is the whole defect.** `verify` used `sha256_file` and therefore read
    whatever RAM held. This asserts the call actually goes through the evicting form - a test that
    only compared digests would pass against the defect, because both produce the same hash."""
    seen: list[Path] = []

    def _record(path: Path) -> str:
        seen.append(path)
        return "deadbeef"

    monkeypatch.setattr(verify_module, "sha256_from_the_medium", _record)

    assert verify_module._hash_path("/some/copy.jpg") == "deadbeef"
    # ⚠ **`Path`, NOT `str(path)` AGAINST A POSIX LITERAL - that took `main` red on Windows.**
    # `_hash_path` builds a `Path`, and `str()` of one renders `\some\copy.jpg` off POSIX, so the
    # comparison failed on the one platform nobody here can run. Path equality is
    # separator-correct everywhere, and the assertion is about WHICH path was hashed rather than
    # about how it is spelled.
    assert seen == [Path("/some/copy.jpg")], "verify did not hash through the medium reader"


def test_eviction_is_attempted_for_every_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each hashed file gets its own eviction. A single eviction at the start would leave every
    later file answered from the cache the first read populated."""
    files = []
    for i in range(3):
        p = tmp_path / f"{i}.jpg"
        p.write_bytes(bytes([i]) * 2048)
        files.append(p)

    evicted: list[Path] = []

    def _note(path: Path) -> bool:
        evicted.append(path)
        return True

    monkeypatch.setattr(hashing, "_evict_from_cache", _note)
    for p in files:
        sha256_from_the_medium(p)

    assert evicted == files


def test_a_file_that_cannot_be_evicted_is_still_hashed(tmp_path: Path) -> None:
    """⚠ **Best effort, never a failed verify.** A hash that could not be forced cold is still a
    hash; refusing to produce one would turn a platform limit into a reported loss."""
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"\xff\xd8data")
    expected = sha256_file(target)

    missing = tmp_path / "gone.jpg"
    assert hashing._evict_from_cache(missing) is False, "eviction claimed to work on a missing file"
    assert sha256_from_the_medium(target) == expected


def test_the_platform_capability_matches_what_python_exposes() -> None:
    """The constant is derived, not declared. It gates the note `verify` prints, so a wrong value
    either silences an honest caveat or prints one on a platform that does not need it.

    ⚠ **NO `skipif`, deliberately, and it cannot be proved on Linux.** The first draft skipped
    unless the capability was present - which skipped it on exactly the two platforms where it can
    fail. Hard-coding this to `True` survives mutation here, because on Linux the derived answer IS
    True; the same mutation goes red on the macOS and Windows `check` lanes, where
    `os.posix_fadvise` does not exist. The proof is CI's, not this machine's, and saying so is
    better than a skip that hides it.
    """
    assert CAN_READ_FROM_THE_MEDIUM is hasattr(os, "posix_fadvise")


def test_the_caveat_names_the_remedy() -> None:
    """A platform limit stated with no next step is a shrug. `(adx)` gap 2."""
    assert "eject" in MEDIUM_READ_UNAVAILABLE.lower()
    assert "verify again" in MEDIUM_READ_UNAVAILABLE.lower()
