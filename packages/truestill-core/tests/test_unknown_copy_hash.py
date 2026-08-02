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

import contextlib
import sqlite3
from pathlib import Path

from truestill_core.hashing import sha256_file
from truestill_core.verify import CopyStatus, CopyToVerify, verify_copies


def _row(**fields: object) -> sqlite3.Row:
    """A genuine ``sqlite3.Row``, built in memory - the exact type ``copies_on_drive`` returns.

    A dict would type-check and lie: ``sqlite3.Row`` raises ``IndexError`` rather than
    ``KeyError`` on an absent column, so a fixture that is not really a row cannot prove
    :meth:`CopyToVerify.from_row` reads the columns it claims to.
    """
    # Closed once the row is materialised: a `sqlite3.Row` holds its values, not the cursor, so
    # it outlives the connection - and leaving the handle open leaked one per call.
    with contextlib.closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        columns = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        row: sqlite3.Row = conn.execute(
            f"WITH r({columns}) AS (VALUES ({placeholders})) SELECT * FROM r",
            tuple(fields.values()),
        ).fetchone()
    return row


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


# --- one home for the row mapping ----------------------------------------------------------
#
# The rule above had one home already (``_partition`` alone decides what NULL means), but the
# row -> object mapping was still written out on both the CLI and the app. Two copies of a
# mapping is how the fallback survived on one surface after being removed from the other, so the
# copy is deleted rather than guarded (ENGINEERING_STANDARD.md §4).


def test_from_row_reads_the_columns_copies_on_drive_returns() -> None:
    """The mapping itself: which column becomes which field, asserted once."""
    row = _row(sha256="src-sha", relative="Camera/2014/a.jpg", copy_sha256="copy-sha", size=7)

    copy = CopyToVerify.from_row(row)

    assert copy.sha256 == "src-sha"
    assert copy.relative == "Camera/2014/a.jpg"
    assert copy.expected_hash == "copy-sha"


def test_from_row_carries_a_null_through_as_unknown() -> None:
    """The mapping must not be where the deleted fallback comes back.

    ``expected_hash=row["copy_sha256"] or row["sha256"]`` would satisfy every other test in this
    file - the source hash is a real string, and verification would run - while quietly asserting
    the byte-identity a bake breaks. This is the assertion that refuses it.
    """
    row = _row(sha256="src-sha", relative="a.jpg", copy_sha256=None, size=7)

    assert CopyToVerify.from_row(row).expected_hash is None
