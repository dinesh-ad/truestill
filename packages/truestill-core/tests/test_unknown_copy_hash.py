"""A copy with no recorded hash is unverifiable, not assumed byte-identical.

**The decision, stated.** ``copy_sha256 or sha256`` read a NULL as "legacy row, compare against
the source hash". That premise - the copy is byte-identical to its source - is exactly what the
Takeout bake already breaks and what date-rescue baking will break again. Carrying it into a
write path would make a *missing* per-drive update indistinguishable from a legacy row, so a
skipped write would surface as a **false corruption alarm** on a file truestill itself rewrote.

So NULL now means **unknown**, and unknown is reported as its own outcome rather than folded
into either success or corruption (§9: an unverifiable outcome is counted and named). The two
readings are tested separately below, because conflating them is the defect.

Measured before deciding: the real catalog has **0 NULLs in 4,538 copies and 0 in 2,300 files**,
so nothing in the only real library changes behaviour. NULL is reachable - ``attach_drive``
copies the deprecated per-content ``files.copy_sha256`` into ``file_copies`` - which is why it
needed an answer rather than an assumption.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies


def _copy(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_a_copy_with_a_recorded_hash_still_verifies(tmp_path: Path) -> None:
    """Cry-wolf half: the ordinary case must be untouched by this change."""
    _copy(tmp_path, "a.jpg", b"payload")
    real = sha256_file(tmp_path / "a.jpg")

    results = verify_copies([CopyToVerify("src-sha", "a.jpg", real)], tmp_path)

    assert [r.status for r in results] == [CopyStatus.VERIFIED]


def test_a_copy_with_no_recorded_hash_is_unverifiable_not_verified(tmp_path: Path) -> None:
    """The first reading, refused: NULL must not be silently compared against the source."""
    _copy(tmp_path, "b.jpg", b"payload")

    results = verify_copies([CopyToVerify("src-sha", "b.jpg", None)], tmp_path)

    assert [r.status for r in results] == [CopyStatus.UNVERIFIABLE]


def test_an_unverifiable_copy_is_not_reported_as_corruption(tmp_path: Path) -> None:
    """The second reading, also refused: not knowing is not the same as finding damage.

    Reporting MISMATCH here would tell a user their photo is damaged when truestill simply has
    no hash on file for it - the same class of lie as O1, arrived at from the other direction.
    """
    _copy(tmp_path, "c.jpg", b"payload")

    results = verify_copies([CopyToVerify("src-sha", "c.jpg", None)], tmp_path)

    assert results[0].status is not CopyStatus.MISMATCH
    assert results[0].status is not CopyStatus.VERIFIED


def test_a_missing_file_is_still_missing_even_with_no_recorded_hash(tmp_path: Path) -> None:
    """Absence outranks unknown: the file not being there is the more specific answer."""
    results = verify_copies([CopyToVerify("src-sha", "gone.jpg", None)], tmp_path)

    assert [r.status for r in results] == [CopyStatus.MISSING]
