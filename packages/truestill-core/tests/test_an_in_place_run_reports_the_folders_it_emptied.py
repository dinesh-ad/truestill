"""`clean-empty` sees both journals, and only the runs whose paths are on this drive. `(afi)`

A layout migration writes `migration_journal`; `organize --in-place` writes `inplace_moves`.
`Catalog.migrated_old_paths` read the first alone, so the folders an in-place run emptied were
invisible to `clean-empty` **and** to the offer printed after the run - while the run's own banner
promised *"Empty folders left behind are reported, never deleted."*

⚠ The union is restricted, and the restriction is a safety condition rather than a tidiness one:
`Relocation` is built for plain ``--move`` too, and `old_relative` is relative to the **source
root**, which for a ``--move`` is the folder the user imported FROM.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog


def _catalog(tmp_path: Path) -> Catalog:
    return Catalog(tmp_path / "catalog.sqlite")


def _in_place_run(
    catalog: Catalog, *, drive: str, run: str, root: str, old: str, dest: str | None = None
) -> None:
    catalog.start_inplace_run(
        run_id=run, source_root=root, dest_root=dest or root, drive_uuid=drive
    )
    catalog.record_inplace_move(
        run_id=run, sha256="a" * 64, old_relative=old, new_relative="Camera/2013/new.jpg"
    )
    catalog.finish_inplace_run(run)


def test_an_in_place_run_contributes_the_folders_it_emptied(tmp_path: Path) -> None:
    """The defect, end to end at the catalog: 161 rows and 'no leftovers recorded'."""
    catalog = _catalog(tmp_path)
    try:
        _in_place_run(catalog, drive="drive-1", run="r1", root="/drive", old="Old Folder/a.jpg")
        assert catalog.migrated_old_paths("drive-1") == ["Old Folder/a.jpg"]
    finally:
        catalog.close()


def test_a_plain_move_from_another_root_contributes_nothing(tmp_path: Path) -> None:
    """⚠ The safety half, and the reason the union is not a bare UNION.

    ``organize ~/Downloads /drive --move`` journals the same way, but its `old_relative` is
    relative to ``~/Downloads``. Counting it would offer to remove the same relative path **on the
    drive** - a folder truestill never emptied there, which is the drive sweep the scope rule
    exists to forbid.
    """
    catalog = _catalog(tmp_path)
    try:
        _in_place_run(
            catalog,
            drive="drive-1",
            run="r2",
            root="/home/someone/Downloads",
            dest="/drive",
            old="Holiday/a.jpg",
        )
        assert catalog.migrated_old_paths("drive-1") == []
    finally:
        catalog.close()


def test_another_drives_in_place_run_contributes_nothing(tmp_path: Path) -> None:
    """The scope rule's other half: one drive's leftovers are not another's."""
    catalog = _catalog(tmp_path)
    try:
        _in_place_run(catalog, drive="drive-2", run="r3", root="/other", old="Old/a.jpg")
        assert catalog.migrated_old_paths("drive-1") == []
    finally:
        catalog.close()


def test_an_unfinished_in_place_run_contributes_nothing(tmp_path: Path) -> None:
    """A run still in flight has not emptied anything yet, and may never.

    `migration_journal` was already filtered on ``completed_at IS NOT NULL``; the in-place half
    has to answer the same way or the two journals disagree about what "emptied" means.
    """
    catalog = _catalog(tmp_path)
    try:
        catalog.start_inplace_run(
            run_id="r4", source_root="/drive", dest_root="/drive", drive_uuid="drive-1"
        )
        catalog.record_inplace_move(
            run_id="r4", sha256="b" * 64, old_relative="Old/a.jpg", new_relative="New/a.jpg"
        )
        assert catalog.migrated_old_paths("drive-1") == []
    finally:
        catalog.close()


def test_the_same_root_spelled_two_ways_is_still_one_place(tmp_path: Path) -> None:
    """A trailing slash is not a different folder, and the roots are stored as typed.

    `Path` already settles `lib/` and `./lib`, but the pair reaches the catalog as two strings and
    a raw comparison would call a real in-place run a `--move` - silently restoring the very gap
    this fix closes, for a user who typed the destination with a slash.
    """
    catalog = _catalog(tmp_path)
    try:
        _in_place_run(
            catalog, drive="drive-1", run="r5", root="/drive/", dest="/drive", old="Old/a.jpg"
        )
        assert catalog.migrated_old_paths("drive-1") == ["Old/a.jpg"]
    finally:
        catalog.close()
