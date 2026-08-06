"""Which drives physically hold a given set of content hashes.

**The gap this closes.** `files.source_path` is where a file was first READ from, and
`test_overlapping_organize_runs.py` pins that a duplicate never repoints it - so the path a
preview reports for a match names the user's old folder, not their library. The only table that
knows where content physically sits is `file_copies`, keyed by `(sha256, drive_uuid)`, and
nothing on the preview path asked it.

Without this, a screen that offered to act on "your library" could only guess which one, and the
two-destination case - copy into X, later preview against Y - makes that guess wrong silently.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog


def _seed(catalog: Catalog, sha: str, drive: str, relative: str) -> None:
    catalog.record_uploaded(
        sha256=sha,
        # The path a preview would report today: where it was first READ from, never repointed.
        source_path=f"/old/place/{sha[:4]}.jpg",
        original_name=f"{sha[:4]}.jpg",
        perceptual=None,
        size=10,
        captured_at=None,
        category="Camera",
        relative=relative,
        drive_uuid=drive,
    )


def test_it_names_the_drive_a_matched_file_actually_sits_on(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        _seed(catalog, "a" * 64, "u-x", "2021/a.jpg")

        rows = catalog.drives_holding(["a" * 64])

    assert [(r.drive_uuid, r.label, r.files) for r in rows] == [("u-x", "BackupA", 1)]


def test_content_on_two_drives_reports_both(tmp_path: Path) -> None:
    """Stage 1's two-destination case: the same photo copied into X, then previewed against Y.

    Picking the first row and calling it "your library" is the failure this exists to prevent.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        catalog.upsert_drive(uuid="u-y", label="BackupB")
        _seed(catalog, "a" * 64, "u-x", "2021/a.jpg")
        _seed(catalog, "a" * 64, "u-y", "2021/a.jpg")

        rows = catalog.drives_holding(["a" * 64])

    assert {r.label for r in rows} == {"BackupA", "BackupB"}


def test_drives_are_ordered_by_how_much_of_the_set_they_hold(tmp_path: Path) -> None:
    """A surface names the first one. It should be where most of the matches are."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-big", label="Big")
        catalog.upsert_drive(uuid="u-small", label="Small")
        shas = [f"{i:064x}" for i in range(4)]
        for sha in shas:
            _seed(catalog, sha, "u-big", "x.jpg")
        _seed(catalog, shas[0], "u-small", "x.jpg")

        rows = catalog.drives_holding(shas)

    assert [r.label for r in rows] == ["Big", "Small"]
    assert [r.files for r in rows] == [4, 1]


def test_a_hash_with_no_copy_row_contributes_to_no_drive(tmp_path: Path) -> None:
    """Not hypothetical: `files` rows with no `file_copies` row are the orphan state
    `test_organize_registers_the_destination.py` exists for. They are counted by the CALLER as
    unplaced; this query must not invent a drive for them."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        _seed(catalog, "a" * 64, "u-x", "2021/a.jpg")

        rows = catalog.drives_holding(["a" * 64, "b" * 64])

    assert sum(r.files for r in rows) == 1, "a hash with no copy row was attributed to a drive"


def test_an_empty_set_asks_the_database_nothing(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.drives_holding([]) == []


def test_a_set_larger_than_sqlites_parameter_limit_is_answered_in_full(tmp_path: Path) -> None:
    """A 40,000-file overlapping preview is the ordinary case this is built for.

    SQLite refuses more bound parameters than `SQLITE_MAX_VARIABLE_NUMBER`, so the set is
    chunked. A truncating implementation would undercount silently, which is worse than raising.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        shas = [f"{i:064x}" for i in range(40_000)]
        for sha in shas:
            _seed(catalog, sha, "u-x", "x.jpg")

        rows = catalog.drives_holding(shas)

    assert [r.files for r in rows] == [40_000]


def test_a_duplicate_hash_in_the_query_is_not_counted_twice(tmp_path: Path) -> None:
    """The caller passes one sha per matched FILE, and two source files can be the same content.

    Counting per row would report more files on the drive than the drive holds.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        _seed(catalog, "a" * 64, "u-x", "2021/a.jpg")

        rows = catalog.drives_holding(["a" * 64, "a" * 64])

    assert [r.files for r in rows] == [1]


def test_the_lookup_uses_an_index_rather_than_scanning_every_copy(tmp_path: Path) -> None:
    """`file_copies` has one row per (content, drive), so on a real library this table is as long
    as the library. A scan per preview would be a table scan on every check for duplicates.

    `PRIMARY KEY (sha256, drive_uuid)` puts sha256 first, so the automatic index already serves
    this and NO NEW INDEX IS ADDED. Asserted rather than assumed - a later schema change that
    reordered that key would make this a scan with nothing to notice.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u-x", label="BackupA")
        _seed(catalog, "a" * 64, "u-x", "2021/a.jpg")
        plan = " ".join(r["detail"] for r in catalog.explain_drives_holding(["a" * 64]))

    assert "SCAN" not in plan, plan
    # Names the index, not just "a seek happened": the claim is that the PRIMARY KEY's own
    # automatic index serves this, which is why the commit adds none. It is a COVERING seek -
    # `drive_uuid` is the key's second column, so the row itself is never fetched.
    assert "sqlite_autoindex_file_copies_1 (sha256=?)" in plan, plan
