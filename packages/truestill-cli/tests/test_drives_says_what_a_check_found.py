"""`drives` distinguishes "nothing has ever run" from "a check ran and found gaps". `(aej)`.

**The defect, from the first soak.** Seven organized files were deleted by hand and `verify` was
run. It reported `verified 4098 / MISSING 7` and named all seven paths correctly. Sixteen seconds
later `truestill drives` printed::

    D3   4105   11649.2   connected   2026-08-20T09:06:46   never

⚠ **Both halves are wrong, and they are wrong in the reassuring direction.** *"never"* is the one
word that is not true - a check had just run - and `4105` is every recorded copy including the
seven a check had just failed to find. The timestamp of that very run is printed on the same line
as the claim that no run ever happened.

**The rule underneath is right and is NOT what changed.** `refresh_drive_verified` leaves
`drives.last_verified` NULL unless *every* copy is confirmed, so the drive cannot claim a date it
has not earned - `(abg)` Stage 2, *"structurally incapable of over-claiming"*. **NULL is a
claim-SUPPRESSION flag**, and its own docstring says it covers *"missing, unreadable, unverifiable
and not reached before the user cancelled"*. The defect is that four read sites decode that flag as
a positive assertion about history: the field answers *"may I reassure?"* and they ask it *"what
happened?"*.

**This is the FALSE EMPTY**, the trust-destroying pattern: a no-results state that is
indistinguishable from a first-use state. A user who sees an empty state contradicted moments later
stops trusting empty states generally - and in a custody product that means they stop acting on
*"never checked"* where it is true and urgent.

**Nothing new is computed.** `list_drives` already returns `missing_count` and `missing_at`
(`catalog.py:1849-1861`), and its docstring says why: *"a drive reads '2,269 recorded, 2,269 not
found on 11 Aug'"*. The CLI had both in hand and printed neither.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import MARKER_NAME, DriveMarker, drive_path_hint


def _library(db: Path, root: Path, *, files: int = 3) -> str:
    """A registered drive holding `files` recorded copies, none of them verified yet."""
    root.mkdir(parents=True, exist_ok=True)
    uuid = "drive-under-test"
    (root / MARKER_NAME).write_text(
        DriveMarker(uuid=uuid, label="Cabinet", created="2026-01-01T00:00:00").to_json()
    )
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Cabinet")
        catalog.set_setting(drive_path_hint(uuid), str(root))
        for n in range(files):
            catalog.record_uploaded(
                source_path=f"/src/{n}.jpg",
                original_name=f"{n}.jpg",
                sha256=f"sha{n}",
                copy_sha256=f"sha{n}",
                perceptual=None,
                size=10,
                captured_at=None,
                category="Camera",
                relative=f"Camera/{n}.jpg",
                drive_uuid=uuid,
            )
    return uuid


def _drives_line(db: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["drives", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    return next(line for line in out.splitlines() if line.startswith("Cabinet"))


def test_a_drive_whose_check_found_missing_files_is_not_reported_as_never_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE REGRESSION, IN THE SOAK'S SHAPE.

    A check ran, confirmed two copies and could not find the third. The drive legitimately has no
    date - it did not earn one - but it has emphatically been checked.
    """
    db = tmp_path / "c.sqlite"
    uuid = _library(db, tmp_path / "drive")
    with Catalog(db) as catalog:
        for n in (0, 1):
            catalog.mark_copy_verified(
                sha256=f"sha{n}", drive_uuid=uuid, when="2026-08-20T09:00:00"
            )
        catalog.mark_copy_missing(sha256="sha2", drive_uuid=uuid, when="2026-08-20T09:00:00")
        catalog.refresh_drive_verified(uuid)
        assert catalog.list_drives()[0]["last_verified"] is None, "the NULL rule must not change"

    line = _drives_line(db, capsys)

    assert "never" not in line, (
        f"a drive that was checked sixteen seconds ago is reported as never checked: {line!r}. "
        "That is the false empty - a no-results state rendering as a first-use state."
    )


def test_a_drive_nothing_has_ever_looked_at_still_says_never(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE CRY-WOLF HALF, and the whole point of the distinction.

    "Never checked" must keep meaning *never checked*. A fix that simply stopped saying the word
    would destroy the signal instead of repairing it - which is the failure the false-empty
    research describes, arrived at from the other side.
    """
    db = tmp_path / "c.sqlite"
    _library(db, tmp_path / "drive")

    line = _drives_line(db, capsys)

    assert "never" in line, f"a genuinely unchecked drive stopped saying so: {line!r}"


def test_the_shortfall_a_check_found_is_on_screen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """S2. `file_count` counts every recorded copy INCLUDING ones a check did not find, which is
    right - this list reports history, and a count dropping to zero destroys the only clue to what
    happened. But then the shortfall has to be stated, or the row reads as a complete backup.

    `list_drives` returns `missing_count` and `missing_at`; the CLI read neither.
    """
    db = tmp_path / "c.sqlite"
    uuid = _library(db, tmp_path / "drive")
    with Catalog(db) as catalog:
        catalog.mark_copy_missing(sha256="sha2", drive_uuid=uuid, when="2026-08-20T09:00:00")
        catalog.refresh_drive_verified(uuid)

    line = _drives_line(db, capsys)

    # ⚠ Read the COLUMNS, not the raw line. A substring check would match a digit inside the
    # runtime `last seen` timestamp and pass for the wrong reason - the first draft of this
    # assertion did exactly that and was green before the fix existed.
    columns = line.split()
    assert columns[1] == "3", f"the recorded count must survive - history, not a promise: {line!r}"
    assert columns[2] == "1", (
        f"one file is known missing and the row does not say so: {line!r}. `list_drives` returns "
        "`missing_count`; the row had it and printed nothing."
    )


def test_a_drive_with_nothing_missing_gains_no_alarming_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second cry-wolf half: a healthy drive must not grow a shortfall it does not have."""
    db = tmp_path / "c.sqlite"
    uuid = _library(db, tmp_path / "drive")
    with Catalog(db) as catalog:
        for n in range(3):
            catalog.mark_copy_verified(
                sha256=f"sha{n}", drive_uuid=uuid, when="2026-08-20T09:00:00"
            )
        catalog.refresh_drive_verified(uuid)

    line = _drives_line(db, capsys)

    assert "never" not in line
    assert "checked, gaps" not in line, f"a fully confirmed drive was told it had gaps: {line!r}"
    assert "2026-08-20" in line, f"a fully confirmed drive must show its date: {line!r}"
    assert line.split()[2] == "-", f"a healthy drive was given a shortfall: {line!r}"


def test_a_cancelled_check_counts_as_having_looked_even_though_nothing_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE CASE `missing_count` CANNOT SEE, and mutation is what found the hole.

    A copy can be unconfirmed **without being missing**: the run was cancelled before reaching it,
    or the file was unreadable. `refresh_drive_verified`'s docstring lists exactly these -
    *"missing, unreadable, unverifiable and not reached before the user cancelled"* - so the drive
    correctly has no date, `missing_count` is **0**, and a check plainly did run.

    Deciding on `missing_count` alone renders this as `never`, which is the original defect
    surviving through a narrower door. `confirmed_count` is the general discriminator, and this is
    the only test that distinguishes the two: replacing it with `missing_count` leaves every other
    assertion here green.
    """
    db = tmp_path / "c.sqlite"
    uuid = _library(db, tmp_path / "drive")
    with Catalog(db) as catalog:
        # Two confirmed, one simply never reached. Nothing is marked missing.
        for n in (0, 1):
            catalog.mark_copy_verified(
                sha256=f"sha{n}", drive_uuid=uuid, when="2026-08-20T09:00:00"
            )
        catalog.refresh_drive_verified(uuid)
        row = catalog.list_drives()[0]
        assert row["last_verified"] is None, "an incomplete check must not earn a date"
        assert row["missing_count"] == 0, "nothing is missing - that is the point of this case"

    line = _drives_line(db, capsys)

    assert "never" not in line, (
        f"a check ran, confirmed two of three copies, and the drive reads as never checked: "
        f"{line!r}. `missing_count` is 0 here, so only `confirmed_count` can tell."
    )
    assert line.split()[2] == "-", "nothing is missing, so the shortfall column stays empty"
