"""Layout migration: planning, copy-only relocation, and crash-safe resume.

The resume tests reconstruct the exact on-disk + catalog state a crash would leave at each step
of the copy -> verify -> flip-catalog -> remove-old sequence, then assert a re-run converges.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutTemplate
from truestill_core.migrate import Move, plan_migration, run_migration

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
        outcome = run_migration(
            catalog, LocalDestination(root), "D1", LayoutTemplate.parse(_DDL), apply=False
        )
    assert outcome.applied is False
    assert outcome.migrated == 0
    assert len(outcome.plan.moves) == 2
    assert (root / "Camera/2023/08/a.jpg").exists()  # untouched


def test_apply_relocates_and_updates_catalog(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _two_files(catalog, root)
        outcome = run_migration(
            catalog, LocalDestination(root), "D1", LayoutTemplate.parse(_DDL), apply=True
        )
        assert outcome.migrated == 2
        assert (root / "Camera/2023/a.jpg").exists()
        assert not (root / "Camera/2023/08/a.jpg").exists()  # old removed
        assert catalog.copy_relative(shas["Camera/2023/08/a.jpg"], "D1") == "Camera/2023/a.jpg"
        assert catalog.pending_migration("D1") == []  # journal drained


def test_apply_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    template = LayoutTemplate.parse(_DDL)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        run_migration(catalog, LocalDestination(root), "D1", template, apply=True)
        again = run_migration(catalog, LocalDestination(root), "D1", template, apply=True)
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
        run_migration(
            catalog, LocalDestination(root1), "D1", LayoutTemplate.parse(_DDL), apply=True
        )
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
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256)]
        )
        dest.relocate(move.old_relative, move.new_relative)  # new exists; old still exists

        run_migration(catalog, dest, "D1", LayoutTemplate.parse(_DDL), apply=True)

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
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256)]
        )
        dest.relocate(move.old_relative, move.new_relative)
        catalog.relocate_copy(
            move.sha256, "D1", move.new_relative
        )  # catalog flipped; old orphan remains

        run_migration(catalog, dest, "D1", LayoutTemplate.parse(_DDL), apply=True)

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
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256)]
        )
        corrupt = root / move.new_relative
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_bytes(b"XX")  # partial/corrupt -> must not be trusted

        run_migration(catalog, dest, "D1", LayoutTemplate.parse(_DDL), apply=True)

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
        plan = plan_migration(catalog, "D1", LayoutTemplate.parse("{category}/{yyyy}/{mm}/{dd}"))
    assert any("same path" in w for w in plan.warnings)
