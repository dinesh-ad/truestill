"""What a drive carries that this catalog lacks - and the three ways that number can lie.

⚠ **THIS IS A READER AND NOTHING ELSE.** Stage 1 of the restore arc. Every test here asserts that
the library is *unchanged* afterwards, because the one thing a report must never do is the thing
it is reporting on.

The three states it has to tell apart are the subject, and two of them look like the third:

1. a real zero - everything the drive records is recorded here too;
2. ⚠ **a drive nobody walked** - `file_copies` empty while the drive is full, which reads as a gap
   of 0 for a drive holding everything. That is the worst wrong answer available: it tells
   somebody who has just lost a disk that their backup has nothing to recover;
3. a library this process could not look at - so "recorded here" means recorded, not present.
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import pytest
from truestill_core.carried import Carried, DriveRef, carried_by, render
from truestill_core.catalog import Catalog
from truestill_core.drive import DriveMarker

DRIVE = DriveRef(uuid="drive-uuid", label="Backup 2024")
LIBRARY = DriveRef(uuid="library-uuid", label="My Library")


def _sha(index: int) -> str:
    return f"{index:064x}"


@pytest.fixture
def catalog(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "catalog.sqlite") as opened:
        opened.upsert_drive(uuid=DRIVE.uuid, label=DRIVE.label)
        opened.upsert_drive(uuid=LIBRARY.uuid, label=LIBRARY.label)
        yield opened


def _place(catalog: Catalog, uuid: str, index: int, *, root: Path | None, size: int = 11) -> None:
    """Record one copy, and optionally put a real file of that size where it says."""
    relative = f"Camera/2014/photo-{index:05d}.jpg"
    catalog.record_copy(
        sha256=_sha(index), drive_uuid=uuid, relative=relative, size=size, copy_sha256=None
    )
    if root is not None:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * size)


# --- the three cases the plan named ------------------------------------------------------------


def test_a_complete_library_carries_nothing(catalog: Catalog, tmp_path: Path) -> None:
    """Case 1: everything the drive records is recorded here, and really here. Gap is zero."""
    library_root = tmp_path / "library"
    for index in range(5):
        _place(catalog, DRIVE.uuid, index, root=None)
        _place(catalog, LIBRARY.uuid, index, root=library_root)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)

    assert report.gap == 0
    assert report.drive_walked is True
    assert report.library_observed is True
    assert report.contradicted_here == 0


def test_files_missing_here_are_counted_and_named_as_records(
    catalog: Catalog, tmp_path: Path
) -> None:
    """Case 2: the drive records ten, this library records four. The gap is six.

    ⚠ **The output must say it counted RECORDS**, because `dedup.credible_copies` measured what
    happens when a row is read as an observation: *"836 zero-byte files on exFAT and 304
    unreadable on NTFS against confident rows"*. A report that printed "6 files" full stop would
    be making a promise about bytes that nothing checked.
    """
    library_root = tmp_path / "library"
    for index in range(10):
        _place(catalog, DRIVE.uuid, index, root=None)
    for index in range(4):
        _place(catalog, LIBRARY.uuid, index, root=library_root)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)
    printed = render(report, drive_path="/mnt/backup")

    assert report.gap == 6
    assert report.recorded_on_drive == 10
    assert report.recorded_here == 4
    assert "6 file(s) this catalog does not record" in printed
    assert "Counted from records, not from a fresh look at the drive" in printed
    assert "Nothing was read from 'Backup 2024' itself" in printed


def test_the_drive_half_answers_with_the_drive_unplugged(catalog: Catalog, tmp_path: Path) -> None:
    """Case 3: no drive is attached anywhere in this test, and the answer is still right.

    That is the design `date-provenance-design.md` states outright - *"a drive can be
    disconnected. The catalog answers instantly and offline"* - and it is the half a restore needs
    most, because the user asking has just lost the other half.
    """
    for index in range(7):
        _place(catalog, DRIVE.uuid, index, root=None)
    for index in range(2):
        _place(catalog, LIBRARY.uuid, index, root=None)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=tmp_path / "gone")

    assert report.gap == 5
    assert report.library_observed is False
    assert render(report, drive_path="/mnt/backup").count("NOT checked against its own disk") == 1


def test_an_unobserved_library_says_so_rather_than_implying_it_looked(catalog: Catalog) -> None:
    """⚠ **The cry-wolf half of the case above.** `contradicted_here` is 0 when nothing was
    looked at, and 0 when everything was fine - two different facts sharing a number. The prose
    is what separates them, so the prose is asserted."""
    for index in range(3):
        _place(catalog, DRIVE.uuid, index, root=None)

    unlooked = render(
        carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=None),
        drive_path="/mnt/backup",
    )

    assert "NOT checked against its own disk" in unlooked
    assert "recorded, not present" in unlooked
    assert "every recorded file was there" not in unlooked


# --- the answer that must never be zero ---------------------------------------------------------


def test_a_drive_nobody_walked_refuses_to_print_a_number(catalog: Catalog, tmp_path: Path) -> None:
    """⚠ **THE WORST WRONG ANSWER IN THE PRODUCT, and it is one `drives --init` away.**

    That command writes a marker and does not walk, so `file_copies` is empty while the drive is
    full. A naive set difference reads **0 files carried** and tells somebody who has just lost a
    disk that their backup holds nothing to recover.

    So the number is withheld, the reason is given, and the command that would fill the rows is
    named.

    ⚠ The assertion is on the COUNT PHRASING, not on the character `0` - the label "Backup 2024"
    contains one, and a test that banned the digit would have been asserting something it did not
    mean and would have gone red on a customer's drive name.
    """
    library_root = tmp_path / "library"
    for index in range(5):
        _place(catalog, LIBRARY.uuid, index, root=library_root)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)
    printed = render(report, drive_path="/mnt/backup")

    assert report.drive_walked is False
    assert report.gap == 0, "the raw count is still zero - the RENDERING is what must not say it"
    assert "0 file(s)" not in printed
    assert "carries" not in printed
    assert "no record of anything on 'Backup 2024'" in printed
    assert "not the same as the drive being empty" in printed
    assert "truestill rescan /mnt/backup" in printed


def test_a_walked_drive_with_a_real_zero_reads_differently(
    catalog: Catalog, tmp_path: Path
) -> None:
    """The other side of the line, and what makes the test above mean something.

    A drive that WAS walked and genuinely carries nothing extra must produce an ordinary report
    with a number in it - otherwise "we cannot say" would be the answer to everything.
    """
    library_root = tmp_path / "library"
    for index in range(3):
        _place(catalog, DRIVE.uuid, index, root=None)
        _place(catalog, LIBRARY.uuid, index, root=library_root)

    printed = render(
        carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root),
        drive_path="/mnt/backup",
    )

    assert "carries 0 file(s)" in printed
    assert "no record of anything" not in printed


# --- a row is a claim ---------------------------------------------------------------------------


def test_a_recorded_file_the_library_does_not_actually_have_re_enters_the_gap(
    catalog: Catalog, tmp_path: Path
) -> None:
    """⚠ **The measured failure, reproduced: rows that describe copies the medium never took.**

    `backup.py` measured *"429 rows against 124 files actually there, 305 false custody claims"*.
    Here the library records five and its disk holds three, so a comparison that believed the
    rows would report a gap of 0 and leave two photographs unrecoverable.

    `credible_copies` is the existing remedy and is reused rather than reimplemented; this
    asserts it is actually reached.
    """
    library_root = tmp_path / "library"
    for index in range(5):
        _place(catalog, DRIVE.uuid, index, root=None)
    for index in range(3):
        _place(catalog, LIBRARY.uuid, index, root=library_root)
    for index in (3, 4):
        _place(catalog, LIBRARY.uuid, index, root=None)  # recorded, never written

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)

    assert report.recorded_here == 5
    assert report.contradicted_here == 2
    assert report.gap == 2, "rows were believed over the disk"
    assert "2 recorded file(s) were not there" in render(report, drive_path="/mnt/backup")


def test_a_zero_byte_copy_is_not_a_copy(catalog: Catalog, tmp_path: Path) -> None:
    """The exFAT shape specifically: the file is *there* and is the wrong size.

    *"A missing file is honest; a zero-byte file is a lie"* - `rescan.py`. The size comes from the
    stat the walk already did, so catching this costs nothing extra.
    """
    library_root = tmp_path / "library"
    _place(catalog, DRIVE.uuid, 1, root=None)
    _place(catalog, LIBRARY.uuid, 1, root=library_root, size=11)
    (library_root / "Camera/2014/photo-00001.jpg").write_bytes(b"")

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)

    assert report.contradicted_here == 1
    assert report.gap == 1


# --- it reads, and only reads -------------------------------------------------------------------


def test_the_report_changes_nothing(catalog: Catalog, tmp_path: Path) -> None:
    """**The property the whole stage rests on.** A reader that wrote would be stage 2 arriving
    without its preview, its confirm or its undo."""
    library_root = tmp_path / "library"
    for index in range(4):
        _place(catalog, DRIVE.uuid, index, root=None)
    for index in range(2):
        _place(catalog, LIBRARY.uuid, index, root=library_root)
    before_files = sorted(p.relative_to(library_root) for p in library_root.rglob("*"))
    before_rows = catalog.copies_on_drive(LIBRARY.uuid)
    # Two empty lists compare equal, so "nothing changed" is what an empty fixture also says.
    assert before_files, "the library is empty, so the comparison below cannot fail"
    assert before_rows, "nothing is recorded, so the row count below cannot fail"

    carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)

    assert sorted(p.relative_to(library_root) for p in library_root.rglob("*")) == before_files
    assert len(catalog.copies_on_drive(LIBRARY.uuid)) == len(before_rows)
    assert len(catalog.copies_on_drive(DRIVE.uuid)) == 4


def test_the_gap_is_keyed_on_content_not_on_path(catalog: Catalog, tmp_path: Path) -> None:
    """A file filed under a different name on the drive is still the same photograph.

    Identity is `sha256`, which is `NOT NULL UNIQUE` in `files` and half the primary key of
    `file_copies`. A path-keyed comparison would report a gap for every file the two sides
    happened to name differently - which, after a layout migration, is all of them.
    """
    library_root = tmp_path / "library"
    catalog.record_copy(
        sha256=_sha(1),
        drive_uuid=DRIVE.uuid,
        relative="OLD/LAYOUT/img.jpg",
        size=11,
        copy_sha256=None,
    )
    _place(catalog, LIBRARY.uuid, 1, root=library_root)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)

    assert report.gap == 0


# --- the drive that is not in the room ----------------------------------------------------------


def test_a_drive_named_by_label_says_it_was_not_connected(catalog: Catalog, tmp_path: Path) -> None:
    """⚠ **The state the question is usually asked from: the disk is gone.**

    ``drive_path=None`` is how the CLI says "this drive was named out of the `drives` table, not
    read". The count is identical either way - the drive half is records on both paths - but what
    the reader can do next is not, and neither is what a number means to somebody holding no disk.
    So an offer to `rescan` a path that does not exist must not be printed.
    """
    library_root = tmp_path / "library"
    for index in range(4):
        _place(catalog, DRIVE.uuid, index, root=None)
    _place(catalog, LIBRARY.uuid, 0, root=library_root)

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=library_root)
    absent = render(report, drive_path=None)

    assert report.gap == 3
    assert "is NOT CONNECTED" in absent
    assert "truestill rescan <its folder>" in absent
    assert render(report, drive_path="/mnt/backup") != absent, "the two states read the same"


def test_nothing_in_the_signature_can_carry_the_drive_s_location() -> None:
    """⚠ **The offline guarantee, asserted where it actually lives: the parameter list.**

    The first version of this test called `carried_by` twice with identical arguments and asserted
    the two gaps matched. It could not fail. There is no "drive unplugged" input to vary, and that
    absence IS the property - the drive half reads `file_copies` and nothing else, so a drive that
    is not there cannot change the number.

    What CAN break it is somebody adding a drive path to reach the disk "just to be sure". This
    fails the moment they do, which the comparison never would.
    """
    taken = set(inspect.signature(carried_by).parameters) - {"catalog", "drive", "library"}

    assert taken == {"library_root"}, "a new input reaches a filesystem; only the library may"
    assert not any(field.name.endswith("_root") for field in fields(Carried))


def test_a_marker_becomes_a_ref_without_being_believed() -> None:
    """`DriveRef.of` is the only bridge, and it drops `created` on the floor deliberately.

    A `DriveMarker` is *"the identity of a destination drive, as stored in its marker file"*. A
    `DriveRef` is a name and a uuid from wherever they came. Keeping them separate types is what
    stops a catalog row being handed round in a shape that claims a drive was read.
    """
    marker = DriveMarker(uuid="u", label="L", created="2026-01-01T00:00:00Z")

    assert DriveRef.of(marker) == DriveRef(uuid="u", label="L")
    assert not hasattr(DriveRef.of(marker), "created")


# --- the size line ------------------------------------------------------------------------------


def test_the_size_is_formatted_by_the_one_formatter(catalog: Catalog) -> None:
    """⚠ **Found by running it, not by reading it.** The first version divided by ``1e9`` and
    printed *"About 0.0 GB"* for a real gap of six photographs - a figure that is worse than
    silence, because it says the drive holds nothing worth fetching.

    `units.format_bytes` is the one formatter and `test_byte_formatting_agrees_across_surfaces`
    already holds the browser to it, so using it here is also what stops this line drifting from
    every other size the product prints.
    """
    for index in range(3):
        _place(catalog, DRIVE.uuid, index, root=None, size=4096)

    printed = render(
        carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=None),
        drive_path="/mnt/backup",
    )

    assert "12.3 KB, by the sizes recorded." in printed
    assert "0.0 GB" not in printed


def test_a_gap_row_with_no_recorded_size_makes_the_total_a_floor(catalog: Catalog) -> None:
    """``file_copies.size`` is nullable, and summing NULL as zero quietly shrinks the number.

    A person reads this figure to decide whether a disk is big enough. Understating it silently
    is the one direction that costs them a second trip, so the shortfall is named and the total
    is labelled as a floor rather than presented as whole.
    """
    _place(catalog, DRIVE.uuid, 1, root=None, size=1000)
    catalog.record_copy(
        sha256=_sha(2), drive_uuid=DRIVE.uuid, relative="b.jpg", size=None, copy_sha256=None
    )

    report = carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=None)
    printed = render(report, drive_path="/mnt/backup")

    assert report.gap == 2
    assert report.gap_bytes == 1000
    assert report.gap_bytes_unknown == 1
    assert "AT LEAST, because 1 of those" in printed


def test_a_gap_whose_rows_all_carry_sizes_says_nothing_about_floors(catalog: Catalog) -> None:
    """The anti-cry-wolf half: the caveat above must not print when it does not apply."""
    _place(catalog, DRIVE.uuid, 1, root=None, size=1000)

    printed = render(
        carried_by(catalog, drive=DRIVE, library=LIBRARY, library_root=None),
        drive_path="/mnt/backup",
    )

    assert "AT LEAST" not in printed
    assert "1.0 KB, by the sizes recorded." in printed
