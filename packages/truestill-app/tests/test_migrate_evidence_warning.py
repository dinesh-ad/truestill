"""A migration that could not read the files says so, instead of quietly sorting by label.

**The §9 gap this closes.** `migrate.rederive_rules` caught `ExiftoolMissingError` and returned
an empty mapping. The degradation is *correct* - falling back to the per-label decision beats
failing the whole migration - but an empty mapping is indistinguishable from "the evidence
agreed with the labels", so nothing reached the user. The run surfaced as **"my dates are
wrong"** rather than **"a tool is missing"**, which is the hardest kind of fault to diagnose:
the symptom names the wrong subsystem.

`(aad)` raises the stakes rather than creating them. Today a missing exiftool means a developer
skipped an install step. Once installers ship it means **the application is broken**, on a
machine whose owner has no terminal, no PATH, and no reason to have heard of exiftool.

§9 asks that a degraded outcome be counted **and named**. The count was there; this is the name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_app.service import migrate as service_migrate
from truestill_core import migrate as core_migrate
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.exif import ExiftoolMissingError

#: Stands in for whatever `ensure_exiftool` would say; this suite asserts on what the
#: migration layer *adds* to it, not on the exif layer's wording.
_NO_EXIFTOOL = "exiftool was not found."


def _drive_with_an_ambiguous_label(tmp_path: Path) -> tuple[Path, Path]:
    """A drive holding one `Camera` file - ambiguous by construction, so evidence is needed."""
    root = tmp_path / "drive"
    root.mkdir()
    create_marker(root, label="Drive A")
    db = tmp_path / "c.sqlite"
    relative = "Camera/2023/08/a.jpg"
    photo = root / relative
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"aaaa")
    with Catalog(db) as catalog:
        marker_uuid = create_marker(root, label="Drive A").uuid
        catalog.upsert_drive(uuid=marker_uuid, label="Drive A")
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="a" * 64,
            copy_sha256="a" * 64,
            perceptual=None,
            size=4,
            captured_at="2023-08-20T14:30:00",
            category="Camera",
            relative=relative,
            drive_uuid=marker_uuid,
        )
    return root, db


def test_the_preview_tells_the_user_the_files_could_not_be_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user-visible half. `warnings` is already rendered by the UI, so this reaches a screen.

    Patched at `core_migrate.read_metadata` - the module that *calls* it - so the guard stays
    aimed at the seam under test rather than at wherever the name was imported from.
    """
    root, db = _drive_with_an_ambiguous_label(tmp_path)

    def missing(_paths: object, **_kwargs: object) -> dict[Path, dict[str, str]]:
        raise ExiftoolMissingError(_NO_EXIFTOOL)

    monkeypatch.setattr(core_migrate, "read_metadata", missing)

    result = service_migrate.migration_preview(root, db)

    assert result["ok"] is True
    warnings = " ".join(result["warnings"]).lower()
    assert "exiftool" in warnings, f"the missing tool was never named: {result['warnings']}"
    assert "label" in warnings, "the consequence for this migration was not stated"


def test_an_ordinary_preview_carries_no_such_warning(tmp_path: Path) -> None:
    """Cry-wolf half: a warning shown on every migration is a warning nobody reads."""
    root, db = _drive_with_an_ambiguous_label(tmp_path)

    result = service_migrate.migration_preview(root, db)

    assert result["ok"] is True
    assert not any("exiftool" in w.lower() for w in result["warnings"])


def test_the_migration_still_runs_rather_than_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The degradation itself is correct and must stay - only the silence was the defect.

    Without this, a future change could satisfy the warning requirement by simply raising, which
    would turn a recoverable, human-resolvable ambiguity into a dead end.
    """
    root, db = _drive_with_an_ambiguous_label(tmp_path)

    def missing(_paths: object, **_kwargs: object) -> dict[Path, dict[str, str]]:
        raise ExiftoolMissingError(_NO_EXIFTOOL)

    monkeypatch.setattr(core_migrate, "read_metadata", missing)

    result = service_migrate.migration_preview(root, db)

    assert result["ok"] is True, "a missing binary must not fail the whole migration"
