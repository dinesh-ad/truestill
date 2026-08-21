"""(aes) "Never checked" must mean nobody looked, not "we looked and found gaps".

**Two questions were sharing one field.** `drives.last_verified` is derived by
`Catalog.refresh_drive_verified` as *"MIN over the copies, and NULL the moment any of them has
never been confirmed"* - `(abg)` Stage 2, and it is **correct**: it answers *is this drive wholly
confirmed, and as of when*. It was never able to answer *has anyone looked*, and NULL is what both
absences look like.

Measured by soak two, S4: seven files deleted from drive B by hand, `verify B` reporting
`MISSING: 7` and naming each. In the same minute:

* `drives` -> `LAST VERIFIED: checked, gaps` ✅ - `(aej)`'s fix, deriving from the copies
* `status` -> **"Never checked: 'B'. Truestill has not looked since the copy was written."** ❌

with the catalog holding **2,262 copies carrying a `last_verified` and 7 carrying a `missing_at`**.
Truestill looked 2,269 times.

⚠ **The remedy is a shared predicate, not a fourth patch.** `(aej)` closed this on `drives` by
writing the discriminator at that one call site, and §4's fifty-sixth member is precisely that: a
rule discovered and then applied locally reads as settled while the surfaces it never reached
disagree in silence. Four surfaces answer *has this drive been looked at* - `custody_freshness`
(which feeds CLI `status` **and** the app's custody strip), `cli._verified_cell`, and the app's
safety table via `stats.py`. One of the four was right. They now share `drive.was_ever_checked`.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.drive import custody_freshness, was_ever_checked

_DRIVE = "11111111-2222-3333-4444-555555555555"


def _catalog_with_a_gapped_verify(tmp_path: Path) -> Catalog:
    """A drive whose verify ran and found one copy missing - the S4 state, in miniature.

    Built through the real writers (`record_uploaded`, `mark_copy_verified`, `mark_copy_missing`,
    `refresh_drive_verified`) rather than by fabricating rows, so the precondition asserted below
    is the product's own state and not a shape this test invented.
    """
    catalog = Catalog(tmp_path / "c.sqlite")
    catalog.upsert_drive(uuid=_DRIVE, label="B")
    for index in range(3):
        sha = f"{index:064x}"
        catalog.record_uploaded(
            source_path=str(tmp_path / f"src{index}.jpg"),
            sha256=sha,
            copy_sha256=sha,
            relative=f"2013/{index}.jpg",
            size=10,
            drive_uuid=_DRIVE,
            original_name=f"src{index}.jpg",
            perceptual=None,
            captured_at=None,
            category="Camera",
        )
    when = "2026-08-21T09:00:00+00:00"
    catalog.mark_copy_verified(sha256=f"{0:064x}", drive_uuid=_DRIVE, when=when)
    catalog.mark_copy_verified(sha256=f"{1:064x}", drive_uuid=_DRIVE, when=when)
    catalog.mark_copy_missing(sha256=f"{2:064x}", drive_uuid=_DRIVE, when=when)
    catalog.refresh_drive_verified(_DRIVE)
    return catalog


def test_a_drive_that_was_checked_and_found_wanting_is_not_called_never_checked(
    tmp_path: Path,
) -> None:
    """The defect, end to end through the function both surfaces call."""
    with _catalog_with_a_gapped_verify(tmp_path) as catalog:
        rows = list(catalog.list_drives())
        row = rows[0]
        assert row["last_verified"] is None, (
            "PRECONDITION: the stamp must be NULL - that is `(abg)` Stage 2 working, and it is "
            "the state this test exists to interpret correctly"
        )
        assert row["confirmed_count"], "PRECONDITION: copies were confirmed, so we DID look"
        assert row["missing_count"], "PRECONDITION: a copy was found missing"

        freshness = custody_freshness(catalog, rows, rows)

    assert freshness.never_checked == (), (
        "a drive that was verified, and whose verify found gaps, was reported as never checked - "
        f"got {freshness.never_checked}"
    )


def test_a_drive_nobody_has_looked_at_still_says_never(tmp_path: Path) -> None:
    """⚠ The cry-wolf half, and it is the whole reason the field exists.

    `(abg)` Stage 3's own note: a drive nothing has looked at must still say **never**, or the
    word stops being actionable on the drives where it is true and urgent.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid=_DRIVE, label="Fresh")
        catalog.record_uploaded(
            source_path=str(tmp_path / "a.jpg"),
            sha256="a" * 64,
            copy_sha256="a" * 64,
            relative="2013/a.jpg",
            size=10,
            drive_uuid=_DRIVE,
            original_name="a.jpg",
            perceptual=None,
            captured_at=None,
            category="Camera",
        )
        rows = list(catalog.list_drives())
        assert not rows[0]["confirmed_count"], "PRECONDITION: nothing confirmed"
        assert not rows[0]["missing_count"], "PRECONDITION: nothing marked missing"

        freshness = custody_freshness(catalog, rows, rows)

    assert freshness.never_checked == ("Fresh",), (
        "a drive nothing has ever looked at must still be named - otherwise 'never' stops "
        "meaning anything on the drives where it matters"
    )


def test_the_predicate_reads_evidence_not_the_stamp() -> None:
    """The shared rule, stated directly, because four surfaces now depend on it.

    A `dict` stands in for a row deliberately: `sqlite3.Row` is a mapping and the predicate must
    not care which one it is handed.
    """
    assert was_ever_checked({"confirmed_count": 2, "missing_count": 1}) is True
    assert was_ever_checked({"confirmed_count": 0, "missing_count": 1}) is True
    assert was_ever_checked({"confirmed_count": 3, "missing_count": 0}) is True
    assert was_ever_checked({"confirmed_count": 0, "missing_count": 0}) is False
    # A row from somewhere that does not carry the aggregates cannot claim a look happened.
    assert was_ever_checked({}) is False
    assert was_ever_checked({"confirmed_count": None, "missing_count": None}) is False
