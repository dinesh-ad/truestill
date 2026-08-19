"""`truestill status` states the age of its claim AND what that age now means. `(abg)` Stage 3.

**The defect.** The claim became datable (Stage 1) and dated (Stage 2); it never became
*conditional*. A library last checked in April printed the same sentence as one checked this
morning. `abg.md:172-207`.

**Two things can be true at once and both are printed.** Stage 1's single date went `None` the
moment any place was unchecked - right, because no single date is true of the whole claim. So
before Stage 3 a library with one never-checked drive could say nothing at all about its other
drives, which is the shape of the maintainer's own catalog. `dated_at` carries that second fact.
Never-checked leads, ordered by strength of evidence rather than severity.

⚠ **These strings had no test of any kind before this file**, on any platform. The app's
equivalents are pinned in three places; the CLI's three sentences were free to change silently.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import MARKER_NAME, DriveMarker, drive_path_hint


def _ago(days: int) -> str:
    """A verification date `days` before now.

    ⚠ **Relative, never a literal.** Once the wording depends on the clock, a hardcoded date
    crosses a threshold by calendar and turns this file red with no commit behind it.
    """
    return (datetime.now(UTC) - timedelta(days=days, hours=1)).isoformat()


def _library(db: Path, drives: dict[str, str | None], *, files: int = 2) -> None:
    """One copy of each file on every named drive, dated through the real path.

    `mark_copy_verified` then `refresh_drive_verified`, because Stage 2 made the drive's date
    derived from its copies - seeding `drives.last_verified` directly would assert against a
    value only a test could produce.
    """
    with Catalog(db) as catalog:
        for index, (label, verified) in enumerate(drives.items()):
            uuid = f"D{index}"
            catalog.upsert_drive(uuid=uuid, label=label)
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
            if verified is None:
                continue
            for row in catalog.copies_on_drive(uuid):
                catalog.mark_copy_verified(sha256=row["sha256"], drive_uuid=uuid, when=verified)
            catalog.refresh_drive_verified(uuid)


def _status(db: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["status", "--db", str(db)]) == 0
    return capsys.readouterr().out


def test_a_never_checked_place_no_longer_silences_how_old_the_others_are(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE REGRESSION, in the shape of the maintainer's own catalog.

    Before Stage 3 this printed the Morrowkeep line and stopped. The two 34-day-old drives had
    no sentence to appear in, so the surface that exists to state the age of the claim stated
    nothing about the only places that had one.
    """
    db = tmp_path / "c.sqlite"
    _library(db, {"Cabinet": _ago(34), "Output": _ago(20), "Morrowkeep": None})

    out = _status(db, capsys)

    assert "Never checked: 'Morrowkeep'" in out
    assert "Last checked:" in out, (
        "a never-checked drive still silences every dated one, so the age of the claim is "
        f"unsayable on a library shaped like the real catalog: {out!r}"
    )
    assert "34 days ago" in out, f"the tier follows the OLDEST dated drive: {out!r}"
    # Never-checked LEADS: no evidence precedes old evidence.
    assert out.index("Never checked") < out.index("Last checked")


def test_a_freshly_checked_library_reads_exactly_as_it_did_before(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cry-wolf half, and the sentence is byte-for-byte the one that shipped in Stage 1.

    A consequence that fires on a healthy library is the nagging this entry exists to avoid, so
    a fresh claim gains no age, no firmness and no prompt.
    """
    db = tmp_path / "c.sqlite"
    _library(db, {"Cabinet": _ago(3), "Output": _ago(9)})

    out = _status(db, capsys)

    assert "(the oldest of the drives holding copies)." in out
    assert "days ago" not in out, f"a healthy library was told its claim is ageing: {out!r}"
    assert "Re-check" not in out, f"a healthy library was prompted to act: {out!r}"


def test_a_softening_claim_says_what_the_age_costs_rather_than_only_its_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tier two. The number alone is what Stage 1 already printed; the consequence is the point."""
    db = tmp_path / "c.sqlite"
    _library(db, {"Cabinet": _ago(45)})

    out = _status(db, capsys)

    assert "45 days ago" in out
    assert "counts copies rather than confirms them" in out
    assert "nothing has confirmed them since" not in out, "tier three's firmer wording leaked"


def test_a_stale_claim_says_so_firmly_and_still_counts_every_copy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tier three, and `abg.md:49-53`'s two counting rules: a HISTORY gains a number rather than
    losing one. The copies still count; only the wording beside them changes."""
    db = tmp_path / "c.sqlite"
    _library(db, {"Cabinet": _ago(200), "Output": _ago(200)})

    out = _status(db, capsys)

    assert "200 days ago" in out
    assert "The copies still count; nothing has confirmed them since." in out
    assert "at least two drive copies" in out, f"a stale claim stopped counting: {out!r}"


def test_the_date_is_never_replaced_by_the_age(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ `abg.md:280` - *"a date that only gets older cannot mislead"*, and a bare "45 days ago"
    is not such a value: it changes while the fact behind it does not, which is the failure this
    entry is named after. The age is added BESIDE the date, never instead of it."""
    db = tmp_path / "c.sqlite"
    when = _ago(45)
    _library(db, {"Cabinet": when})

    out = _status(db, capsys)

    assert when[:10] in out, f"the absolute date was replaced by a relative one: {out!r}"


def test_the_route_names_a_real_path_only_for_a_drive_that_is_actually_connected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ `(adx)` GAP 2 NOT REPEATED. `truestill verify` takes a required path that must be a
    connected drive root, so naming the command without one, or with a path for an absent drive,
    is a remedy the reader cannot follow."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "cabinet"
    root.mkdir()
    _library(db, {"Cabinet": _ago(45)})
    with Catalog(db) as catalog:
        uuid = next(d["uuid"] for d in catalog.list_drives())
        (root / MARKER_NAME).write_text(
            DriveMarker(uuid=uuid, label="Cabinet", created="2026-01-01T00:00:00").to_json()
        )
        catalog.set_setting(drive_path_hint(uuid), str(root))

    out = _status(db, capsys)

    assert f"truestill verify {root}" in out, f"the connected drive's path is not offered: {out!r}"


def test_an_unreachable_drive_is_told_what_to_connect_rather_than_a_dead_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half, and the one gap 2 is actually about. With no reachable drive there is no
    path to name, and printing `truestill verify <something>` anyway would be the same defect
    reworded. The step that IS available is connecting the drive."""
    db = tmp_path / "c.sqlite"
    _library(db, {"Cabinet": _ago(45)})

    out = _status(db, capsys)

    assert "connect 'Cabinet'" in out
    assert "truestill verify /" not in out, f"a path was invented for an absent drive: {out!r}"


def test_a_remembered_path_that_is_no_longer_there_is_not_offered_as_a_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ THE ACTUAL `(adx)` GAP 2 SHAPE, and the one a missing-hint fixture cannot reach.

    A drive that has moved still HAS a remembered path; the path is simply stale. Deciding the
    route on *"do we have a hint"* rather than *"is the drive there"* prints a real, specific,
    confidently wrong command - `truestill verify /media/old-place` for a drive that is not at
    /media/old-place. `verify` requires a connected drive root, so it fails, and a confident
    wrong pointer ends the search where no pointer would not have.

    Found by mutation: replacing the reach check with `if hint:` survived every other test here,
    because none of them had a hint that pointed anywhere.
    """
    db = tmp_path / "c.sqlite"
    stale = tmp_path / "where-it-used-to-be"
    stale.mkdir()  # a real directory, with no marker in it: the drive is not here any more
    _library(db, {"Cabinet": _ago(45)})
    with Catalog(db) as catalog:
        uuid = next(d["uuid"] for d in catalog.list_drives())
        catalog.set_setting(drive_path_hint(uuid), str(stale))

    out = _status(db, capsys)

    assert str(stale) not in out, (
        f"a path the drive has left was offered as a command that cannot work: {out!r}"
    )
    assert "connect 'Cabinet'" in out


def test_the_route_answers_the_claim_that_leads_rather_than_whatever_is_plugged_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ FOUND ON THE REAL CATALOG WHILE BUILDING THIS, and it is the subtle half.

    A never-checked drive leads the claim. Offering `verify <the other, connected, fresh drive>`
    is a real path and a working command that answers the sentence above it not at all - the user
    runs it, it succeeds, and the never-checked place is still never checked. The route follows
    the same lead rule as the wording.
    """
    db = tmp_path / "c.sqlite"
    connected = tmp_path / "output"
    connected.mkdir()
    _library(db, {"Morrowkeep": None, "Output": _ago(2)})
    with Catalog(db) as catalog:
        uuid = next(d["uuid"] for d in catalog.list_drives() if d["label"] == "Output")
        (connected / MARKER_NAME).write_text(
            DriveMarker(uuid=uuid, label="Output", created="2026-01-01T00:00:00").to_json()
        )
        catalog.set_setting(drive_path_hint(uuid), str(connected))

    out = _status(db, capsys)

    assert "connect 'Morrowkeep'" in out, (
        f"the route pointed at a reachable but already-fresh drive: {out!r}"
    )
    assert str(connected) not in out


def test_a_library_with_nothing_on_a_drive_is_unchanged_and_offered_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An honest zero. Nothing to stand behind, nothing to apologise for, and nothing to act on."""
    db = tmp_path / "c.sqlite"
    with Catalog(db):
        pass

    out = _status(db, capsys)

    assert "Nothing is on a drive yet, so there is nothing to have checked." in out
    assert "Re-check" not in out
