"""Cheap organize inventory (backlog tt): walk + size, no exiftool or hashing."""

from __future__ import annotations

from pathlib import Path

import pytest
import truestill_core.exif as exif_mod
import truestill_core.hashing as hashing_mod
import truestill_core.scan as scan_mod
from truestill_app.service import organize_inventory, organize_preview
from truestill_core.organizer import inventory_source


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_inventory_source_counts_types_extensions_and_bytes(tmp_path: Path) -> None:
    _write(tmp_path / "a.jpg", b"jpeg-a")
    _write(tmp_path / "b.JPG", b"jpeg-bb")
    _write(tmp_path / "c.mp4", b"video-bytes-here")
    _write(tmp_path / "notes.pdf", b"%PDF")
    _write(tmp_path / "weird.xyz", b"nope")

    inv = inventory_source(tmp_path)
    assert inv.files == 3
    assert inv.photos == 2
    assert inv.videos == 1
    assert inv.audio == 0
    assert inv.by_format["photos"] == {"jpg": 2}
    assert inv.by_format["videos"] == {"mp4": 1}
    assert inv.total_bytes == len(b"jpeg-a") + len(b"jpeg-bb") + len(b"video-bytes-here")
    assert inv.skipped["documents"] == {".pdf": 1}
    assert inv.skipped["unrecognized"] == {".xyz": 1}


def test_inventory_does_not_call_exiftool_or_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The (tt) bug: inventory used to live only inside the full preview, so looking inside
    paid for exiftool + hashes. This fixture fails if those are reached."""
    _write(tmp_path / "a.jpg", b"photo-one")
    _write(tmp_path / "b.jpg", b"photo-two-different")

    calls = {"exif": 0, "sha": 0, "phash": 0, "compute": 0}

    def boom_exif(*_a: object, **_k: object) -> dict:
        calls["exif"] += 1
        raise RuntimeError

    def boom_sha(*_a: object, **_k: object) -> str:
        calls["sha"] += 1
        raise RuntimeError

    def boom_phash(*_a: object, **_k: object) -> str | None:
        calls["phash"] += 1
        raise RuntimeError

    def boom_compute(*_a: object, **_k: object) -> dict:
        calls["compute"] += 1
        raise RuntimeError

    # Patch where the service (and scan workers) would see them if inventory leaked.
    monkeypatch.setattr("truestill_app.service.read_metadata", boom_exif)
    monkeypatch.setattr(exif_mod, "read_metadata", boom_exif)
    monkeypatch.setattr(hashing_mod, "sha256_file", boom_sha)
    monkeypatch.setattr(hashing_mod, "perceptual_hash", boom_phash)
    monkeypatch.setattr(scan_mod, "compute_hashes", boom_compute)
    monkeypatch.setattr("truestill_app.service.resolve", boom_compute)

    result = organize_inventory(tmp_path)
    assert set(result) == {
        "tier",
        "files",
        "photos",
        "videos",
        "audio",
        "by_format",
        "total_bytes",
        "skipped",
    }
    assert result["tier"] == "inventory"
    assert result["files"] == 2
    assert result["photos"] == 2
    assert calls == {"exif": 0, "sha": 0, "phash": 0, "compute": 0}


def test_inventory_numbers_match_full_preview(tmp_path: Path) -> None:
    _write(tmp_path / "day" / "a.jpg", b"aaa")
    _write(tmp_path / "day" / "b.png", b"bbbb")
    _write(tmp_path / "day" / "c.mp4", b"cccccccc")
    _write(tmp_path / "day" / "readme.txt", b"text")
    dest = tmp_path / "out"
    db = tmp_path / "c.sqlite"

    inv = organize_inventory(tmp_path / "day")
    preview = organize_preview(tmp_path / "day", dest, db)

    assert inv["files"] == preview["files"] == 3
    assert inv["photos"] == preview["photos"] == 2
    assert inv["videos"] == preview["videos"] == 1
    assert inv["audio"] == preview["audio"] == 0
    assert inv["by_format"] == preview["by_format"]
    assert inv["skipped"] == preview["skipped"]
    assert inv["total_bytes"] == 3 + 4 + 8


def test_inventory_against_the_bug_would_fail_if_preview_were_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation check: if organize_inventory accidentally called organize_preview, the
    expensive-call guard above would fire. Pin that wiring explicitly."""
    _write(tmp_path / "a.jpg", b"x")
    seen: list[str] = []

    def fake_preview(*_a: object, **_k: object) -> dict[str, object]:
        seen.append("preview")
        return {"tier": "dedup", "files": 1, "photos": 1}

    monkeypatch.setattr("truestill_app.service.organize_preview", fake_preview)
    organize_inventory(tmp_path)
    assert seen == []  # inventory must not route through the full preview
