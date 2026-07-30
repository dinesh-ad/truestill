"""Space-safe reclaim: re-verify-always, min-copies, and never deleting on a failed verify."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.reclaim import plan_reclaim, run_reclaim


def _seed(
    catalog: Catalog, source: Path, drive_root: Path, drive_uuid: str, relative: str, content: bytes
) -> str:
    """Write a source file and its backed-up copy on a drive; record both. Returns the sha."""
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    sha = sha256_file(source)
    copy = drive_root / relative
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(content)
    catalog.upsert_drive(uuid=drive_uuid, label="Drive A")
    catalog.record_uploaded(
        source_path=str(source),
        original_name=source.name,
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=len(content),
        captured_at=None,
        category="Camera",
        relative=relative,
        drive_uuid=drive_uuid,
    )
    return sha


def test_reclaim_frees_a_verified_source(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")
        plan = plan_reclaim(catalog, "D1", drive)
        assert len(plan.candidates) == 1
        assert plan.total_bytes == len(b"content-a")

        outcome = run_reclaim(catalog, "D1", drive)
        assert outcome.deleted == 1
        assert not source.exists()  # source freed
        assert (drive / "Camera/a.jpg").exists()  # backup copy untouched
        assert catalog.pending_reclaim() == []  # journal drained


def test_reclaim_journals_a_deletion_before_the_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§1: every reclaim deletion is journalled for audit/resume.

    ``record_reclaim`` runs just before ``unlink``. A crash that is not ``OSError`` must leave
    a ``pending_reclaim`` row naming the source - otherwise the contract clause has no test
    (audit F13). ``OSError`` on unlink clears the journal on purpose; that path is not this one.
    """
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")

    real_unlink = Path.unlink

    def crash_after_journal(self: Path, *args: object, **kwargs: object) -> None:
        if self.resolve() == source.resolve():
            message = "simulated crash after reclaim journal"
            raise RuntimeError(message)
        real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", crash_after_journal)
    with Catalog(db) as catalog, pytest.raises(RuntimeError, match="simulated crash"):
        run_reclaim(catalog, "D1", drive)

    with Catalog(db) as catalog:
        pending = catalog.pending_reclaim()
        assert len(pending) == 1
        assert pending[0]["source_path"] == str(source)
        assert source.exists()  # unlink never completed


def test_reclaim_never_deletes_when_copy_fails_verify(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")
        # Corrupt the backup copy: it no longer matches copy_sha256.
        (drive / "Camera/a.jpg").write_bytes(b"CORRUPTED")

        plan = plan_reclaim(catalog, "D1", drive)
        assert plan.candidates == []  # not offered
        assert plan.unverified == 1
        assert source.exists()  # source is NEVER at risk when the copy can't be verified


def test_reclaim_reverifies_at_apply_not_on_a_stale_plan(tmp_path: Path) -> None:
    # A copy can verify when first planned, then rot before deletion. run_reclaim re-verifies
    # against fresh state at apply time, so a stale eligibility never causes a delete.
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")
        assert len(plan_reclaim(catalog, "D1", drive).candidates) == 1  # eligible now

        (drive / "Camera/a.jpg").write_bytes(b"ROTTED")  # copy rots before we apply
        outcome = run_reclaim(catalog, "D1", drive)
        assert outcome.deleted == 0
        assert source.exists()  # the rotted copy is never trusted -> source untouched


def test_reclaim_min_copies_gate_and_single_copy_warning(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")  # only 1 copy

        default = plan_reclaim(catalog, "D1", drive)  # min_copies=1
        assert len(default.candidates) == 1
        assert len(default.single_copy) == 1  # would drop to a single copy -> warned

        strict = plan_reclaim(catalog, "D1", drive, min_copies=2)
        assert strict.candidates == []
        assert strict.below_min_copies == 1


def test_reclaim_is_idempotent(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")
        run_reclaim(catalog, "D1", drive)  # frees the source
        again = run_reclaim(catalog, "D1", drive)  # re-run: source already gone
        assert again.deleted == 0
        assert again.plan.candidates == []
        assert again.plan.missing_sources == 1  # gone path is counted, not silently skipped


def test_reclaim_reports_missing_sources_with_examples(tmp_path: Path) -> None:
    """A catalog path that no longer exists must not yield an unexplained empty plan."""
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")
        source.unlink()  # recorded source_path is now stale

        plan = plan_reclaim(catalog, "D1", drive)
        assert plan.candidates == []
        assert plan.missing_sources == 1
        assert str(source) in plan.missing_examples


def test_reclaim_empty_plan_is_calm_when_nothing_is_eligible(tmp_path: Path) -> None:
    """No candidates and no missing sources = normal; must not look like a failure."""
    drive = tmp_path / "drive"
    drive.mkdir()
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        plan = plan_reclaim(catalog, "D1", drive)
        assert plan.candidates == []
        assert plan.missing_sources == 0
        assert plan.unverified == 0
        assert plan.below_min_copies == 0
        assert plan.organized_in_place == 0
