"""A file reclaim cannot read is never a deletion candidate - pinned, not left to coincidence.

**Why this file exists, and why it was written BEFORE the `(aey)` fix rather than after.**
`(aey)` found that on Python 3.14 `Path.is_file()` stops raising on ``EACCES`` and returns
``False``. Five sites broke on that. Reclaim did **not**, and the reason is worth stating exactly:
its two gates read ``False`` as *do not delete*, so a refused file lands on the safe side of both
whether the call raises or returns. **That is a coincidence of which answer is conservative, not a
property anything asserted** - and reclaim is the only path in this product that deletes a user's
files.

⚠ **Reclaim deliberately does NOT use `truestill_core.path_reach`.** The shared probe exists to
tell *absent* from *refused*; this site does not want the distinction and must not acquire it by a
uniformity sweep. `_source_present` and `_verify` say so in their own words. These tests are what
stands between that decision and somebody "tidying" it.

The two gates, from `plan_reclaim`:

* `_source_present` false -> counted as a missing source and `continue`d;
* `_verify` false -> counted `unverified` and `continue`d.

Neither can be reached by a file whose bytes we could not read, which is what the tests below
assert directly rather than by inspection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.reclaim import plan_reclaim, run_reclaim


def _seed(
    catalog: Catalog, source: Path, drive_root: Path, drive_uuid: str, relative: str, content: bytes
) -> str:
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


def _refuse(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Make ``target`` - and only it - refuse every stat-backed probe and every read.

    Monkeypatched rather than `chmod 000` so the assertions run on the Windows lane too, where a
    mode of 000 does not deny the owner. Both the predicate and `open` are refused, because the
    two gates use different mechanisms: one probes, the other re-hashes.
    """
    for name in ("is_file", "exists", "stat"):
        original = getattr(Path, name)

        def patched(self: Path, *args: Any, _orig: Any = original, **kwargs: Any) -> Any:
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return _orig(self, *args, **kwargs)

        monkeypatch.setattr(Path, name, patched)

    real_open = Path.open

    def refusing_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refusing_open)


def test_a_source_that_cannot_be_read_is_never_a_deletion_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate one. The file is backed up and would otherwise qualify - refusal is the only change."""
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "a.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/a.jpg", b"content-a")

        # Fixture check: without the refusal this file IS a candidate, so the assertion below
        # measures the refusal rather than some unrelated disqualification.
        assert len(plan_reclaim(catalog, "D1", drive).candidates) == 1

        _refuse(monkeypatch, source)
        plan = plan_reclaim(catalog, "D1", drive)

        assert plan.candidates == [], (
            "a source Truestill could not examine was offered for deletion. Reclaim's whole "
            "safety argument is that it re-verifies before deleting, and it cannot verify this."
        )


def test_a_destination_copy_that_cannot_be_read_never_frees_its_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate two, and the more dangerous direction.

    Here the *source* is perfectly readable, so nothing about it disqualifies it. What cannot be
    read is the backup this deletion depends on - and an unverifiable backup must never license
    removing the only other copy.
    """
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "b.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/b.jpg", b"content-b")
        assert len(plan_reclaim(catalog, "D1", drive).candidates) == 1

        _refuse(monkeypatch, drive / "Camera" / "b.jpg")
        plan = plan_reclaim(catalog, "D1", drive)

        assert plan.candidates == [], (
            "the backup copy could not be re-verified and the source was offered for deletion "
            "anyway - the exact failure re-verification exists to prevent"
        )
        assert plan.unverified == 1, "it must be counted, not silently dropped from the plan"


def test_a_refused_copy_survives_apply_as_well_as_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The gate is re-checked at apply, so a plan built before the refusal cannot delete either.

    `plan_reclaim` and `run_reclaim` are separate calls with a user's decision between them. A
    test that only pinned the plan would leave the window where the drive becomes unreadable
    *after* the user says yes - which is the ordinary way a drive goes away.
    """
    drive = tmp_path / "drive"
    source = tmp_path / "src" / "c.jpg"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, source, drive, "D1", "Camera/c.jpg", b"content-c")
        assert len(plan_reclaim(catalog, "D1", drive).candidates) == 1

        _refuse(monkeypatch, drive / "Camera" / "c.jpg")
        outcome = run_reclaim(catalog, "D1", drive)

        assert outcome.deleted == 0, "a source was deleted against a backup that could not be read"
        assert source.exists(), "the user's only readable copy was removed"
