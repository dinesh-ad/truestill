"""Layout migration: planning, copy-only relocation, and crash-safe resume.

The resume tests reconstruct the exact on-disk + catalog state a crash would leave at each step
of the copy -> verify -> flip-catalog -> remove-old sequence, then assert a re-run converges.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import MARKER_NAME
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import Move, plan_migration, run_migration, undo_migration


def _scheme(template: str) -> LayoutScheme:
    """A migration scheme from one template -- the legacy shape these tests exercise."""
    parsed = LayoutTemplate.parse(template)
    return LayoutScheme(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


_DDL = "{category}/{yyyy}"  # drops the month the default adds -> every dated file must move


def _seed(
    catalog: Catalog, root: Path, drive_uuid: str, rows: list[tuple[str, str, str, bytes]]
) -> dict[str, str]:
    """Write real files and record them; return {relative: sha256}."""
    shas: dict[str, str] = {}
    for relative, category, captured, content in rows:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        sha = sha256_file(path)
        shas[relative] = sha
        catalog.record_uploaded(
            source_path=f"/src/{PurePosixPath(relative).name}",
            original_name=PurePosixPath(relative).name,
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=len(content),
            captured_at=captured,
            category=category,
            relative=relative,
            drive_uuid=drive_uuid,
        )
    return shas


def _two_files(catalog: Catalog, root: Path) -> dict[str, str]:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    return _seed(
        catalog,
        root,
        "D1",
        [
            ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa"),
            ("WhatsApp/2024/01/b.jpg", "WhatsApp", "2024-01-15T00:00:00", b"bbbb"),
        ],
    )


def test_preview_moves_nothing(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(_DDL), apply=False)
    assert outcome.applied is False
    assert outcome.migrated == 0
    assert len(outcome.plan.moves) == 2
    assert (root / "Camera/2023/08/a.jpg").exists()  # untouched


def test_apply_relocates_and_updates_catalog(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _two_files(catalog, root)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(_DDL), apply=True)
        assert outcome.migrated == 2
        assert (root / "Camera/2023/a.jpg").exists()
        assert not (root / "Camera/2023/08/a.jpg").exists()  # old removed
        assert catalog.copy_relative(shas["Camera/2023/08/a.jpg"], "D1") == "Camera/2023/a.jpg"
        assert catalog.pending_migration("D1") == []  # journal drained


def test_apply_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    scheme = _scheme(_DDL)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        run_migration(catalog, LocalDestination(root), "D1", scheme, apply=True)
        again = run_migration(catalog, LocalDestination(root), "D1", scheme, apply=True)
    assert again.migrated == 0
    assert again.plan.unchanged == 2


def test_only_the_given_drive_is_touched(tmp_path: Path) -> None:
    root1, root2 = tmp_path / "d1", tmp_path / "d2"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root1)
        catalog.upsert_drive(uuid="D2", label="Drive B")
        other = _seed(
            catalog,
            root2,
            "D2",
            [("Camera/2023/08/z.jpg", "Camera", "2023-08-20T14:30:00", b"zzzz")],
        )
        run_migration(catalog, LocalDestination(root1), "D1", _scheme(_DDL), apply=True)
        # D2's copy is left exactly where it was -- migration is one connected drive at a time.
        assert catalog.copy_relative(other["Camera/2023/08/z.jpg"], "D2") == "Camera/2023/08/z.jpg"
        assert (root2 / "Camera/2023/08/z.jpg").exists()


# -- crash recovery: reconstruct each intermediate state, then resume -----------------------


def _one_move(catalog: Catalog, root: Path) -> Move:
    sha = _seed(
        catalog, root, "D1", [("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa")]
    )["Camera/2023/08/a.jpg"]
    catalog.upsert_drive(uuid="D1", label="Drive A")
    return Move(sha, "Camera/2023/08/a.jpg", "Camera/2023/a.jpg", sha)


def test_resume_after_crash_before_catalog_flip(tmp_path: Path) -> None:
    # Crash state: new copy written + journalled, but the catalog still points at the old path.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        dest.relocate(move.old_relative, move.new_relative)  # new exists; old still exists

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert (root / "Camera/2023/a.jpg").exists()
        assert not (root / "Camera/2023/08/a.jpg").exists()
        assert catalog.copy_relative(move.sha256, "D1") == "Camera/2023/a.jpg"
        assert catalog.pending_migration("D1") == []


def test_resume_after_crash_after_flip_removes_orphan(tmp_path: Path) -> None:
    # Crash state: catalog already flipped to new, but the old copy was never removed (orphan).
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        dest.relocate(move.old_relative, move.new_relative)
        catalog.relocate_copy(
            move.sha256, "D1", move.new_relative
        )  # catalog flipped; old orphan remains

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert not (root / "Camera/2023/08/a.jpg").exists()  # orphan cleaned
        assert (root / "Camera/2023/a.jpg").exists()
        assert catalog.pending_migration("D1") == []


def test_resume_repairs_partial_copy(tmp_path: Path) -> None:
    # Crash state: the new copy was only half-written (wrong bytes); catalog still points at old.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        corrupt = root / move.new_relative
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_bytes(b"XX")  # partial/corrupt -> must not be trusted

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert sha256_file(root / "Camera/2023/a.jpg") == move.copy_sha256  # re-copied and verified
        assert not (root / "Camera/2023/08/a.jpg").exists()
        assert catalog.pending_migration("D1") == []


def test_plan_flags_collision(tmp_path: Path) -> None:
    # Two files whose new paths differ only in case collide on a case-insensitive filesystem.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                ("camera/2023/08/a.jpg", "camera", "2023-08-20T00:00:00", b"aaaa"),
                ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T00:00:00", b"bbbb"),
            ],
        )
        plan = plan_migration(catalog, "D1", _scheme("{category}/{yyyy}/{mm}/{dd}"))
    assert any("same path" in w for w in plan.warnings)


def _fingerprint(root: Path) -> list[tuple[str, str]]:
    """Every file with its content hash -- catches a move, a rewrite or a deletion."""
    return sorted(
        (p.relative_to(root).as_posix(), sha256_file(p))
        for p in root.rglob("*")
        if p.is_file() and p.name != MARKER_NAME
    )


def test_forward_then_undo_returns_the_tree_and_the_catalog(tmp_path: Path) -> None:
    """The reverse gear, proved the same way preview purity was: byte-identical, both sides.

    A migration that cannot be undone is a one-way door on someone's only organized copy. This
    asserts the door swings: disk back to the same paths with the same content, and the catalog
    agreeing with disk again so `verify` still passes.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_tree = _fingerprint(root)
        before_paths = {r["relative"] for r in catalog.copies_for_migration("D1")}
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        assert _fingerprint(root) != before_tree  # it really did move

        outcome = undo_migration(catalog, dest, "D1", apply=True)

        assert outcome.reversed_files == 2
        assert outcome.clean
        assert {r["relative"] for r in catalog.copies_for_migration("D1")} == before_paths
        assert _fingerprint(root) == before_tree


def test_undo_is_resumable_when_interrupted_partway(tmp_path: Path) -> None:
    """Undo drops a journal row only after its file is verified back, so it can be re-run."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_tree = _fingerprint(root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)

        # A realistic interruption: the restore was written to disk but the process died
        # before the catalog flip, the removal and the journal drop.
        record = catalog.reversible_migration("D1")
        assert record is not None
        first = record[1][0]
        dest.relocate(str(first["new_relative"]), str(first["old_relative"]))

        # Re-running finishes every move, including the half-done one, without double-counting
        # or tripping over the copy already sitting at its old path.
        outcome = undo_migration(catalog, dest, "D1", apply=True)

        assert outcome.reversed_files == 2
        assert outcome.clean
        assert _fingerprint(root) == before_tree
        assert catalog.reversible_migration("D1") is None  # the record is spent


def test_undo_refuses_a_file_that_changed_since_the_migration(tmp_path: Path) -> None:
    """Someone edited the photo after it moved. Undo reports it and leaves it alone.

    Putting the old path back would discard whatever that edit was, which is exactly the kind of
    silent loss the copy-only invariant exists to prevent.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)

        record = catalog.reversible_migration("D1")
        assert record is not None
        moved = root / str(record[1][0]["new_relative"])
        moved.write_bytes(b"edited since the migration")

        outcome = undo_migration(catalog, dest, "D1", apply=True)

        # The untouched file goes back; the edited one is reported and left exactly as it is.
        assert outcome.reversed_files == 1
        assert not outcome.clean
        assert "changed since the migration" in outcome.refused[0][1]
        assert moved.read_bytes() == b"edited since the migration"
        assert catalog.reversible_migration("D1") is not None  # its record survives for a retry


def test_a_new_migration_supersedes_the_previous_reversal_record(tmp_path: Path) -> None:
    """Retention is bounded by supersession, not by a timer -- one run's record per drive."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        first = catalog.reversible_migration("D1")
        assert first is not None

        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}/{dd}"), apply=True)
        second = catalog.reversible_migration("D1")

        assert second is not None
        assert second[0] != first[0]  # a new run
        assert len(second[1]) == 2  # and only its own moves are retained
