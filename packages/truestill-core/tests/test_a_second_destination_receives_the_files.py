"""Organizing into a second drive copies what is not on THAT drive. `(aei)`.

**The defect, found by the first soak against 4,111 real photos.** `truestill organize <Input>
<D2> --apply` into a **fresh, empty** destination copied **nothing**: 4,111 files reported
`duplicate, skipped / already in your library`, exit 0, a drive registered holding **0 files** -
while `status` warned in the same breath that 4,088 files existed on only ONE drive. **The product
named the problem, declined to fix it, and reported that as success.**

**The cause is one query.** `Catalog.seed_rows` is ``SELECT source_path, sha256, perceptual FROM
files`` - catalog-global, no ``drive_uuid`` - and the index it seeds is a ``dict[sha256, path]``
with no drive dimension. So "already in your library" meant *this catalog has ever seen this
content, on any drive or on none*, and organizing onto a second drive skipped everything already
recorded from the first.

**The correct model was already in the tree and was never carried across.**
``backup.py:_files_missing_on_target`` asks per-drive and its docstring says why, verbatim:
*"keyed on per-drive presence, not the catalog-global dedup that would wrongly skip a genuine
second copy."* `IMPLEMENTATION_STANDARDS.md` states the same rule twice - for backup and for the
preview - and the write path was never brought along.

⚠ **Scope is deliberately three-valued**, because a destination without a drive identity cannot be
asked a per-drive question at all:

* ``None`` - no per-drive scope available, use the catalog-global answer. The default, so every
  direct-API caller keeps today's semantics and the change is opt-in per call site. This is also
  what an **rclone** remote gets: `cli.py` scopes drive tracking to local destinations on purpose
  ("always-online cloud, not drives-in-a-drawer"), and a per-drive check would re-copy an rclone
  remote in full on every run.
* ``{}`` - a markerless local destination, which provably holds no recorded copies.
* populated - sha -> the relative path recorded on this drive, which also lets the skip line
  name where the copy actually is.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.exif import read_metadata
from truestill_core.organizer import discover, execute, plan, resolve


def _organize(
    source: Path,
    out: Path,
    db: Path,
    *,
    drive_uuid: str | None,
    label: str = "Drive",
) -> list:
    """One organize run into a REGISTERED destination, the way the CLI does it.

    The existing `_run` in `test_organizer.py` registers no drive, which is the ``None`` case
    above and is deliberately left alone. This helper is the two-destination shape: a drive is
    upserted, its recorded shas become the dedup scope, and copies are recorded against it.
    """
    files = discover(source)
    metadata = read_metadata(files)
    decisions = plan(files, metadata)
    with Catalog(db) as catalog:
        if drive_uuid is not None:
            catalog.upsert_drive(uuid=drive_uuid, label=label)
        on_destination = (
            {str(r["sha256"]): str(r["relative"]) for r in catalog.copies_on_drive(drive_uuid)}
            if drive_uuid is not None
            else None
        )
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), threshold=10)
        resolutions = resolve(
            decisions,
            index,
            catalog_sizes=catalog.known_sizes(),
            on_destination=on_destination,
        )
        results = execute(
            resolutions,
            LocalDestination(out),
            catalog,
            apply=True,
            drive_uuid=drive_uuid,
        )
    return list(zip(resolutions, results, strict=True))


def _copied(out: Path) -> int:
    return len([p for p in out.rglob("*") if p.is_file() and not p.name.startswith(".truestill")])


def test_a_fresh_second_destination_receives_the_files(tmp_path: Path, gradient_png: Path) -> None:
    """⚠ THE REGRESSION, IN THE SOAK'S SHAPE. Today the second destination gets nothing.

    Organize a source into drive A, then organize the SAME source into a fresh, empty drive B.
    B must receive the files: they are known to the catalog, and they are not on B.
    """
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    db = tmp_path / "c.sqlite"

    first = _organize(source, tmp_path / "A", db, drive_uuid="drive-a", label="A")
    assert _copied(tmp_path / "A") == 1, "the first destination did not receive the file"
    assert first[0][0].should_upload

    second = _organize(source, tmp_path / "B", db, drive_uuid="drive-b", label="B")

    assert _copied(tmp_path / "B") == 1, (
        "a fresh second destination received NOTHING. The content is known to the catalog and "
        "is not on this drive, so it must be copied - otherwise the product reports 'already in "
        "your library' about a drive that holds none of it. `(aei)`."
    )
    assert second[0][0].should_upload, (
        "the file was classified as a duplicate on a drive without it"
    )


def test_a_rerun_into_the_same_destination_still_writes_nothing(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE BEHAVIOUR TO PROTECT - the soak's S2, and it is correct today.

    The same content, the same drive, twice. The second run must write nothing: this content IS
    on this drive, so the skip is right. A fix that made the first test pass by disabling dedup
    would fail here, which is the whole point of keeping the pair together.
    """
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    db = tmp_path / "c.sqlite"
    out = tmp_path / "A"

    _organize(source, out, db, drive_uuid="drive-a", label="A")
    assert _copied(out) == 1

    paired = _organize(source, out, db, drive_uuid="drive-a", label="A")

    assert _copied(out) == 1, "a re-run into the SAME destination wrote a second copy"
    resolution = paired[0][0]
    assert resolution.exact_duplicate is not None, "the re-run stopped recognising its own copy"
    assert not resolution.should_upload


def test_two_identical_files_in_one_batch_still_yield_one_copy(
    tmp_path: Path, gradient_png: Path
) -> None:
    """Within-batch dedup, on a FRESH destination - the soak's *"matched another file earlier in
    this batch"*. Neither file is on the drive, so a per-drive check alone would copy both; the
    RUN-origin match has to keep suppressing the second regardless of drive."""
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "one.png")
    shutil.copy(gradient_png, source / "two.png")

    paired = _organize(source, tmp_path / "A", tmp_path / "c.sqlite", drive_uuid="drive-a")

    assert _copied(tmp_path / "A") == 1, "byte-identical files in one batch were both copied"
    uploaded = [res for res, _ in paired if res.should_upload]
    assert len(uploaded) == 1


def test_a_caller_that_names_no_drive_keeps_the_catalog_wide_answer(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE `None` CASE, AND IT IS LOAD-BEARING FOR rclone.

    `cli.py` scopes drive tracking to local destinations on purpose - an rclone remote is
    "always-online cloud, not drives-in-a-drawer" - so it has no drive identity and never will.
    Under a per-drive check it would re-copy the entire remote on every run. ``None`` means *no
    per-drive scope available*, and the catalog-global answer is the only one there is.

    This also keeps every existing direct-API caller on today's semantics, including
    `test_organizer.test_rerun_recognises_catalog_and_skips`, which registers no drive.
    """
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "A", db, drive_uuid=None)
    assert _copied(tmp_path / "A") == 1

    paired = _organize(source, tmp_path / "B", db, drive_uuid=None)

    assert _copied(tmp_path / "B") == 0, (
        "a caller that named no drive got per-drive semantics. For an rclone remote that means "
        "re-copying the whole destination every run."
    )
    assert paired[0][0].exact_duplicate is not None


def test_the_skip_names_where_the_copy_is_not_the_file_being_skipped(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE TAUTOLOGY, AND IT WAS THE MOST-READ LINE OF THE WHOLE FEATURE.

    The skip line named `files.source_path` - where the content was FIRST read from, deliberately
    never repointed - so on the most ordinary re-run, the same folder scanned twice, it printed
    the path of the very file it was skipping:

        img_1080x1920x24_0149142.jpg  [SKIP: exact duplicate]
            identical to : /home/.../Input/Testing-new/img_1080x1920x24_0149142.jpg

    **X is identical to X.** The catalog held the useful answer all along - `file_copies.relative`
    for that sha on that drive - and the line did not ask for it.
    """
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "photo.png")
    db = tmp_path / "c.sqlite"
    out = tmp_path / "A"

    _organize(source, out, db, drive_uuid="drive-a", label="A")
    paired = _organize(source, out, db, drive_uuid="drive-a", label="A")

    match = paired[0][0].exact_duplicate
    assert match is not None
    assert match.matched_path != str(source / "photo.png"), (
        "the skip still names the file being skipped, which explains nothing"
    )
    with Catalog(db) as catalog:
        recorded = catalog.copy_relative(paired[0][0].hashes.sha256, "drive-a")
    assert match.matched_path == recorded, (
        f"the skip must name the copy on this drive ({recorded!r}), not {match.matched_path!r}"
    )


def test_within_batch_twins_are_not_both_copied_onto_a_second_drive(
    tmp_path: Path, gradient_png: Path
) -> None:
    """⚠ THE CASE THE FIRST FIX BROKE, AND THE UNIT TESTS MISSED IT - the real corpus caught it.

    Organizing 4,111 real photos into a second drive wrote **4,111** files where the first drive
    held 4,105: the six byte-identical twins were both copied. `test_two_identical_files_in_one_
    batch_still_yield_one_copy` passed throughout, because its catalog was empty and so held no
    paths from the source folder.

    **Why the empty catalog hid it.** `DedupIndex._origin_of` decides RUN-vs-CATALOG by **path
    string**. Re-scanning a folder the catalog was ingested from registers a path that is already
    a catalog path, so a genuine within-run twin reports `CATALOG` - and the per-destination gate
    demoted it a second time. The fix is that the destination grows as the run writes: content
    this run has already placed here counts as here.

    The fixture is therefore the discriminating one: a catalog seeded FROM THIS SOURCE, then a
    fresh destination, with twins in the batch.
    """
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(gradient_png, source / "one.png")
    shutil.copy(gradient_png, source / "two.png")
    db = tmp_path / "c.sqlite"

    _organize(source, tmp_path / "A", db, drive_uuid="drive-a", label="A")
    assert _copied(tmp_path / "A") == 1

    _organize(source, tmp_path / "B", db, drive_uuid="drive-b", label="B")

    assert _copied(tmp_path / "B") == 1, (
        "both byte-identical twins were copied onto the second drive. The catalog was seeded "
        "from this very folder, so the twin's path is a catalog path and the within-run match "
        "reported CATALOG."
    )
