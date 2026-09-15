"""A copy a check proved corrupt stops counting as somewhere the file lives. `(aku)`

⚠ **FOUND BY USING THE PRODUCT, NOT BY A TEST, AND NO TEST COULD HAVE.** `verify` had exactly two
write branches - `VERIFIED` -> `mark_copy_verified` and `MISSING` -> `mark_copy_missing`. A
`MISMATCH` took **neither**. So on a real library a check read a photograph, found its bytes wrong,
reported *"1 changed"*, named the file - and wrote nothing. The copy recorded as
``missing_at IS NULL, last_verified IS NULL``: *present, never checked*, which is byte-for-byte the
state of a copy nobody has ever looked at.

Measured consequence: `/api/where` went on saying that photograph was in **2 places**, and the
custody band, the at-risk count and the custody floor all counted a copy the product had just
proven was garbage. **Every test passed**, because every test asserted the verify *report*, which
was correct. The defect lived in the gap between two correct components.

🔑 **THREE STATES, NOT TWO.** Never checked (both NULL). Checked and clean (``last_verified``).
Checked and **wrong** (``damaged_at``). The third is persistent - an unplugged drive comes back,
rotted bytes do not un-rot - and survives until a later verify reads the bytes again.

**The field's own framing, which is why the third state is not optional:**

* **Ceph** runs two scrub classes with two health states and warns about exactly this: *"if a
  corrupt replica's OSD fails before the next deep scrub runs, recovery can rebuild from the
  corrupt copy and propagate the damage."*
* **CockroachDB**, on a checksum mismatch: *"this is not a transient condition - the database is
  telling you that data integrity is compromised."*
* **Borg**: `check` is read-only and reports; repairing is a separate explicit act.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog

_A = "a" * 64
_B = "b" * 64
WHEN = "2026-09-15T12:00:00+00:00"


def _library(db: Path, *, drives: tuple[str, ...] = ("D1", "D2")) -> None:
    """One file on every named drive, so the copy count is the number of drives."""
    with Catalog(db) as catalog:
        conn = catalog._conn
        for index, uuid in enumerate(drives):
            conn.execute("INSERT INTO drives (uuid, label) VALUES (?, ?)", (uuid, f"Drive{index}"))
        conn.execute(
            "INSERT INTO files (sha256, original_name, size, source_path, category, relative,"
            " upload_status, processed_at)"
            " VALUES (?, 'holiday.jpg', 10, '/in/holiday.jpg', 'Camera', '2014/holiday.jpg',"
            " 'uploaded', ?)",
            (_A, WHEN),
        )
        for uuid in drives:
            conn.execute(
                "INSERT INTO file_copies (sha256, drive_uuid, relative, copy_sha256, size)"
                " VALUES (?, ?, '2014/holiday.jpg', ?, 10)",
                (_A, uuid, _A),
            )
        conn.commit()


@pytest.fixture
def two_copies(tmp_path: Path) -> Path:
    db = tmp_path / "c.sqlite"
    _library(db)
    return db


def _counts(db: Path) -> dict[str, object]:
    """Every surface that answers *how many places does this file have*, in one dict."""
    with Catalog(db) as catalog:
        floor = catalog.custody_floor()
        return {
            "single_copy_count": catalog.single_copy_count(),
            "single_copy_shas": len(catalog.single_copy_shas()),
            "at_risk_total": sum(g.total for g in catalog.single_copy_by_drive(sample_limit=6)),
            "custody_floor": int(floor["floor"]),
            "held_floor": int(floor["held_floor"]),
            "one_copy": int(floor["one_copy"]),
            "holder_sets": len(catalog.holder_sets()),
            "drives_holding": len(catalog.drives_holding([_A])),
        }


# --- the state is recorded at all ------------------------------------------------------------


def test_a_mismatch_is_recorded_rather_than_reported_and_forgotten(two_copies: Path) -> None:
    """**The headline.** Before `(aku)` this column did not exist and the write never happened."""
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        row = catalog._conn.execute(
            "SELECT damaged_at, last_verified FROM file_copies WHERE drive_uuid = 'D2'"
        ).fetchone()
    assert row["damaged_at"] == WHEN
    # ⚠ Cleared in the same statement, `mark_copy_missing`'s reason: a copy cannot be
    # simultaneously confirmed good and known wrong.
    assert row["last_verified"] is None


def test_damaged_is_distinguishable_from_never_checked(two_copies: Path) -> None:
    """⚠ **THE WHOLE DEFECT IN ONE ASSERTION.** These two states were identical on disk."""
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        rows = {
            str(r["drive_uuid"]): r
            for r in catalog._conn.execute(
                "SELECT drive_uuid, last_verified, missing_at, damaged_at FROM file_copies"
            )
        }
    never_checked, damaged = rows["D1"], rows["D2"]
    assert (never_checked["last_verified"], never_checked["missing_at"]) == (None, None)
    assert (damaged["last_verified"], damaged["missing_at"]) == (None, None)
    # Identical in every column that existed before `(aku)`; the new one is what tells them apart.
    assert never_checked["damaged_at"] is None
    assert damaged["damaged_at"] == WHEN


# --- every surface agrees ---------------------------------------------------------------------


def test_every_copy_counter_stops_counting_a_damaged_copy(two_copies: Path) -> None:
    """⚠ **THE ONE THAT MATTERS: NINE COUNTERS, ONE ANSWER.**

    A file on two drives is safe. Prove one copy corrupt and it is a file in **one** place - and
    every surface must say so together, because a user who reads "2 places" on the band and
    "1 at risk" on the card cannot tell which is lying. `a_place` is why they agree.
    """
    before = _counts(two_copies)
    assert before == {
        "single_copy_count": 0,
        "single_copy_shas": 0,
        "at_risk_total": 0,
        "custody_floor": 2,
        "held_floor": 2,
        "one_copy": 0,
        "holder_sets": 1,
        "drives_holding": 2,
    }, f"the fixture is not two clean copies: {before}"

    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)

    after = _counts(two_copies)
    assert after == {
        "single_copy_count": 1,
        "single_copy_shas": 1,
        "at_risk_total": 1,
        "custody_floor": 1,
        "held_floor": 1,
        "one_copy": 1,
        "holder_sets": 0,
        "drives_holding": 1,
    }, f"a damaged copy is still counted as a place somewhere: {after}"


def test_a_file_with_one_good_and_one_damaged_copy_is_at_risk(two_copies: Path) -> None:
    """Stated as its own test because it is the product's central claim, in words.

    Two copies, one corrupt, is not redundancy - it is one copy and a warning.
    """
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        groups = catalog.single_copy_by_drive(sample_limit=6)

    assert [(g.drive_label, g.total) for g in groups] == [("Drive0", 1)], (
        "the at-risk listing does not name the drive still holding the one good copy"
    )


def test_the_damaged_copy_is_not_offered_as_a_holder(two_copies: Path) -> None:
    """`drives_holding` answers *where does this file live* - and it does not live there."""
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        holders = {h.label for h in catalog.drives_holding([_A])}
    assert holders == {"Drive0"}, f"a drive holding only a corrupt copy was listed: {holders}"


# --- what clears it ---------------------------------------------------------------------------


def test_a_later_clean_verify_clears_the_damage(two_copies: Path) -> None:
    """⚠ **THE CORRECTIVE HALF, AND `mark_copy_missing`'s docstring says why it matters most.**

    *"A stuck state is worse than the defect it was added for, because that defect at least
    corrected itself when the news turned good."* A user who replaces a corrupt file and re-checks
    must get their custody count back.
    """
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
    assert _counts(two_copies)["single_copy_count"] == 1

    with Catalog(two_copies) as catalog:
        catalog.mark_copy_verified(sha256=_A, drive_uuid="D2", when="2026-09-16T00:00:00+00:00")

    after = _counts(two_copies)
    assert after["single_copy_count"] == 0, "a clean re-verify did not restore the copy"
    assert after["custody_floor"] == 2


def test_writing_the_copy_afresh_clears_the_damage(two_copies: Path) -> None:
    """The second way back: replacing the bytes makes the old verdict a fact about nothing."""
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        catalog.record_copy(
            sha256=_A, drive_uuid="D2", relative="2014/holiday.jpg", copy_sha256=_A, size=10
        )
    assert _counts(two_copies)["single_copy_count"] == 0


def test_merely_seeing_the_drive_again_does_not_clear_the_damage(two_copies: Path) -> None:
    """⚠ **PERSISTENT, AND THIS IS WHERE DAMAGE DIFFERS FROM ABSENCE IN KIND.**

    An absent copy is explained by an unplugged drive, so the drive coming back is news. Rotted
    bytes are not explained by anything that reconnecting fixes - only reading them again is.
    `upsert_drive` is what every attach and every verify calls first.
    """
    with Catalog(two_copies) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D2", when=WHEN)
        catalog.upsert_drive(uuid="D2", label="Drive1")

    assert _counts(two_copies)["single_copy_count"] == 1, (
        "seeing the drive again cleared a damage verdict that only re-reading the bytes can clear"
    )


# --- the fixture can tell the difference -------------------------------------------------------


def test_an_absent_copy_and_a_damaged_copy_are_both_excluded_but_separately(
    tmp_path: Path,
) -> None:
    """⚠ **A cry-wolf check on the predicate itself.** Both disqualify, and each on its own column.

    If `a_place` had been written to test only one of them, one of these two halves would pass on
    a predicate that ignores the other entirely.
    """
    db = tmp_path / "c.sqlite"
    _library(db, drives=("D1", "D2", "D3"))
    assert _counts(db)["custody_floor"] == 3

    with Catalog(db) as catalog:
        catalog.mark_copy_missing(sha256=_A, drive_uuid="D2", when=WHEN)
    assert _counts(db)["custody_floor"] == 2, "absence alone no longer disqualifies a copy"

    with Catalog(db) as catalog:
        catalog.mark_copy_damaged(sha256=_A, drive_uuid="D3", when=WHEN)
    assert _counts(db)["custody_floor"] == 1, "damage alone no longer disqualifies a copy"
