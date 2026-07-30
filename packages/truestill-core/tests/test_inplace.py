"""In-place organize: rename fast-path, its landmines, and the undo that reverses it.

Every test here corresponds to a way this feature could destroy or scramble the only copy of
someone's library, because that is who uses it -- a drive with no backup, by definition.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.dedup import DedupIndex
from truestill_core.destinations import LocalDestination
from truestill_core.models import ActionStatus
from truestill_core.organizer import Relocation, execute, plan, resolve
from truestill_core.reclaim import plan_reclaim
from truestill_core.undo import UndoError, UndoSkip, plan_undo, run_undo

_DRIVE = "drive-uuid-inplace"


def _jpeg(path: Path, colour: int) -> Path:
    """A file with no EXIF: dateless and category-stable, so placement is deterministic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes([colour]) * 4096)
    return path


def _organize(
    root: Path,
    db: Path,
    *,
    apply: bool = True,
    require_rename: bool = False,
    run_id: str = "run-1",
    source: Path | None = None,
    dest: Path | None = None,
):
    """Plan and execute an in-place organize, returning the results."""
    src = source or root
    dst = dest or root
    files = sorted(p for p in src.rglob("*") if p.is_file())
    decisions = plan(files, {}, None)
    destination = LocalDestination(dst)
    relocation = Relocation(
        run_id=run_id, source_root=src, dest_root=dst, require_rename=require_rename
    )
    with Catalog(db) as catalog:
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), threshold=10)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
        if apply:
            catalog.start_inplace_run(
                run_id=run_id, source_root=str(src), dest_root=str(dst), drive_uuid=_DRIVE
            )
        results = execute(
            resolutions,
            destination,
            catalog,
            apply=apply,
            move=True,
            relocation=relocation if apply else None,
            drive_uuid=_DRIVE,
        )
        if apply:
            catalog.finish_inplace_run(run_id)
    return results


# --- the rename fast-path ---------------------------------------------------------------


def test_files_move_by_rename_and_nothing_is_copied(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)
    inode_before = original.stat().st_ino

    results = _organize(root, tmp_path / "c.sqlite")

    assert [r.status for r in results] == [ActionStatus.MOVED_IN_PLACE]
    assert not original.exists()  # it moved; it was not left behind as well
    landed = next(p for p in root.rglob("*.jpg") if p.is_file())
    assert landed.stat().st_ino == inode_before  # same inode: no bytes were rewritten


def test_dry_run_moves_nothing(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)

    results = _organize(root, tmp_path / "c.sqlite", apply=False)

    assert [r.status for r in results] == [ActionStatus.PLANNED]
    assert original.is_file()  # still exactly where it was


def test_collision_on_rename_never_overwrites(tmp_path: Path) -> None:
    """The measured POSIX trap: `rename` onto an existing file destroys it silently.

    Never-overwrite is carried by `_free_relative`, not by the syscall. Two distinct files
    that plan to the same path must both survive.
    """
    root = tmp_path / "drive"
    _jpeg(root / "one" / "a.jpg", 1)
    _jpeg(root / "two" / "a.jpg", 2)

    results = _organize(root, tmp_path / "c.sqlite")

    assert all(r.status is ActionStatus.MOVED_IN_PLACE for r in results)
    landed = sorted(p for p in root.rglob("*.jpg") if p.is_file())
    assert len(landed) == 2  # nothing was silently destroyed
    assert {p.read_bytes()[:1] for p in landed} == {b"\x01", b"\x02"}  # both contents intact


def test_cross_device_falls_back_to_the_verified_copy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EXDEV is answered by the kernel, not predicted -- and a plain move survives it."""
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)

    def _refuse(*_args: object) -> Path:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(Path, "rename", _refuse)
    results = _organize(root, tmp_path / "c.sqlite")

    assert [r.status for r in results] == [ActionStatus.MOVED]  # copied, verified, source removed
    assert not original.exists()
    assert any(p.is_file() for p in root.rglob("*.jpg"))


def test_in_place_refuses_rather_than_copying_across_devices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of --in-place: a user with no room must be told, not quietly filled up."""
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)

    def _refuse(*_args: object) -> Path:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(Path, "rename", _refuse)
    results = _organize(root, tmp_path / "c.sqlite", require_rename=True)

    assert [r.status for r in results] == [ActionStatus.FAILED]
    assert original.is_file()  # untouched: no fallback copy was made
    assert "different filesystems" in results[0].detail


def test_rerun_is_a_no_op_on_a_fresh_catalog(tmp_path: Path) -> None:
    """Idempotency without dedup's help: the file is already at its target, so leave it.

    Guards the trap where `_free_relative` sees the file occupying its own destination and
    suffixes it to `a_1.jpg` -- a re-run quietly renaming an already-organized library.
    """
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    _organize(root, tmp_path / "first.sqlite")
    placed = sorted(p for p in root.rglob("*.jpg") if p.is_file())

    results = _organize(root, tmp_path / "fresh.sqlite", run_id="run-2")

    assert [r.status for r in results] == [ActionStatus.ALREADY_PLACED]
    assert sorted(p for p in root.rglob("*.jpg") if p.is_file()) == placed  # no suffixed twin


def test_hash_is_unchanged_because_the_inode_is(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"

    _organize(root, db)

    with Catalog(db) as catalog:
        source_path, sha256, _ = catalog.seed_rows()[0]
        row = catalog.find_by_sha256(sha256)
        assert row is not None
        assert row["copy_sha256"] == row["sha256"]  # a rename cannot change content
        # The recorded source is where the file now lives, not the path it vacated.
        assert Path(source_path).is_file()


# --- the reclaim landmine ---------------------------------------------------------------


def test_reclaim_refuses_a_file_organized_in_place(tmp_path: Path) -> None:
    """The catastrophic case: source and drive copy are one inode, so a file verifies against
    itself and reclaim would delete the only copy in existence."""
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"
    _organize(root, db)

    with Catalog(db) as catalog:
        plan_result = plan_reclaim(catalog, _DRIVE, root)

    assert plan_result.candidates == []  # never offered
    assert plan_result.organized_in_place == 1  # and never silently: it is counted
    assert any(p.is_file() for p in root.rglob("*.jpg"))


# --- undo -------------------------------------------------------------------------------


def test_undo_restores_exact_prior_paths(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    originals = {
        _jpeg(root / "DCIM" / "a.jpg", 1): b"\x01",
        _jpeg(root / "holiday" / "b.jpg", 2): b"\x02",
    }
    db = tmp_path / "c.sqlite"
    _organize(root, db)
    assert not any(p.exists() for p in originals)

    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog), apply=True)

    assert outcome.restored == 2
    for path, content in originals.items():
        assert path.is_file()
        assert path.read_bytes()[:1] == content


def test_undo_previews_without_moving_anything(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"
    _organize(root, db)

    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog), apply=False)

    assert outcome.applied is False
    assert outcome.restored == 0
    assert not original.exists()  # still organized; the preview wrote nothing


def test_undo_refuses_to_overwrite_an_occupied_original_path(tmp_path: Path) -> None:
    """Undo obeys never-overwrite too: whatever is there now wins, and the clash is reported."""
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 1)
    db = tmp_path / "c.sqlite"
    _organize(root, db)
    _jpeg(original, 9)  # something else took the old path back

    with Catalog(db) as catalog:
        outcome = run_undo(catalog, plan_undo(catalog), apply=True)

    assert outcome.restored == 0
    assert [s.reason for s in outcome.skipped] == [UndoSkip.ORIGIN_OCCUPIED]
    assert original.read_bytes()[:1] == b"\x09"  # the incumbent survived untouched


def test_undo_clears_the_catalog_so_a_reorganize_works(tmp_path: Path) -> None:
    """The subtle one. A `files` row surviving an undo makes the content look organized, and
    the next organize skips every restored file as an exact duplicate -- an undo that quietly
    leaves the library un-organizable."""
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"
    _organize(root, db)
    with Catalog(db) as catalog:
        run_undo(catalog, plan_undo(catalog), apply=True)

    results = _organize(root, db, run_id="run-2")

    assert [r.status for r in results] == [ActionStatus.MOVED_IN_PLACE]  # not DUPLICATE


def test_undo_is_reversible_round_trip(tmp_path: Path) -> None:
    """Organize -> undo -> organize lands the file back at the same place it first went."""
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"
    _organize(root, db)
    first = next(p for p in root.rglob("*.jpg") if p.is_file()).relative_to(root)

    with Catalog(db) as catalog:
        run_undo(catalog, plan_undo(catalog), apply=True)
    _organize(root, db, run_id="run-2")

    second = next(p for p in root.rglob("*.jpg") if p.is_file()).relative_to(root)
    assert second == first


def test_undo_names_unreachable_roots_and_override_flags(tmp_path: Path) -> None:
    """Stored absolute roots that no longer exist must fail loudly, not skip every move."""
    root = tmp_path / "drive"
    _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"
    _organize(root, db)

    moved = tmp_path / "remounted"
    root.rename(moved)

    with Catalog(db) as catalog:
        with pytest.raises(UndoError, match="unreachable") as raised:
            plan_undo(catalog)
        message = str(raised.value)
        assert str(root) in message
        assert "--source-root" in message
        assert "--dest-root" in message

        # Overrides point undo at the remount; the journal's relative paths still apply.
        plan = plan_undo(catalog, source_root=moved, dest_root=moved)
        assert plan.restorable == 1
        assert plan.source_root == moved


def test_an_interrupted_run_is_still_undoable(tmp_path: Path) -> None:
    """A crash leaves the run `in_progress`, but every completed rename is already journalled,
    so what actually moved can still be put back."""
    root = tmp_path / "drive"
    original = _jpeg(root / "DCIM" / "a.jpg", 7)
    db = tmp_path / "c.sqlite"

    files = [original]
    decisions = plan(files, {}, None)
    with Catalog(db) as catalog:
        index = DedupIndex.from_catalog_rows(catalog.seed_rows(), threshold=10)
        resolutions = resolve(decisions, index, catalog_sizes=catalog.known_sizes())
        catalog.start_inplace_run(
            run_id="crashed", source_root=str(root), dest_root=str(root), drive_uuid=_DRIVE
        )
        execute(
            resolutions,
            LocalDestination(root),
            catalog,
            apply=True,
            move=True,
            relocation=Relocation(run_id="crashed", source_root=root, dest_root=root),
            drive_uuid=_DRIVE,
        )
        # no finish_inplace_run: simulate the process dying here
        undo_plan = plan_undo(catalog)
        assert undo_plan.status == "in_progress"
        outcome = run_undo(catalog, undo_plan, apply=True)

    assert outcome.restored == 1
    assert original.is_file()
