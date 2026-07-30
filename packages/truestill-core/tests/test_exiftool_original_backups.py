"""Safety refuse for exiftool ``*_original`` sidecars (backlog bbb).

Distinction pinned here: exiftool appends ``_original`` to the *full* filename
(``holiday.jpg_original``); a legitimate ``vacation_original.jpg`` is not a backup.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from truestill_core import organizer
from truestill_core.organizer import (
    EXIFTOOL_BACKUP_LABEL,
    _skipped_extension_counts,
    discover,
    inventory_source,
    is_exiftool_original_backup,
    scan_source,
)


def test_skipped_report_uses_plain_exiftool_backup_label(tmp_path: Path) -> None:
    (tmp_path / "holiday.jpg").write_bytes(b"live")
    (tmp_path / "holiday.jpg_original").write_bytes(b"backup")
    (tmp_path / "clip.mp4_original").write_bytes(b"vbackup")

    skipped = _skipped_extension_counts(scan_source(tmp_path))
    assert skipped["exiftool_backups"] == {EXIFTOOL_BACKUP_LABEL: 2}
    assert ".jpg_original" not in skipped["exiftool_backups"]
    assert ".jpg_original" not in skipped["unrecognized"]

    inv = inventory_source(tmp_path)
    assert inv.skipped["exiftool_backups"] == {EXIFTOOL_BACKUP_LABEL: 2}
    assert inv.files == 1


def test_discover_inherits_scan_refusal_under_all_files(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"a")
    (tmp_path / "a.jpg_original").write_bytes(b"b")
    assert [p.name for p in discover(tmp_path, all_files=True)] == ["a.jpg"]


def test_mutation_stem_endswith_original_wrongly_refuses_legitimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matcher that looks before the extension would refuse vacation_original.jpg."""

    def stem_endswith_original(path: Path | str) -> bool:
        return Path(path).stem.endswith("_original")

    monkeypatch.setattr(organizer, "is_exiftool_original_backup", stem_endswith_original)
    assert organizer.is_exiftool_original_backup("vacation_original.jpg")
    assert not is_exiftool_original_backup("vacation_original.jpg")


def test_mutation_jpg_only_misses_other_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    """A JPEG-only suffix check would let clip.mp4_original through as media under --all-files."""

    def jpg_only(path: Path | str) -> bool:
        return Path(path).name.endswith(".jpg_original")

    monkeypatch.setattr(organizer, "is_exiftool_original_backup", jpg_only)
    assert not organizer.is_exiftool_original_backup("clip.mp4_original")
    assert is_exiftool_original_backup("clip.mp4_original")


def test_mutation_skipping_refuse_under_all_files_promotes_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the refuse door is removed, --all-files organizes the sidecar as media."""
    (tmp_path / "holiday.jpg").write_bytes(b"live")
    (tmp_path / "holiday.jpg_original").write_bytes(b"backup")

    def no_refuse(source: Path, *, all_files: bool = False):
        media: list[Path] = []
        documents: list[Path] = []
        unrecognized: list[Path] = []
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(source).parts):
                continue
            ext = path.suffix.lower()
            if all_files or ext in organizer.MEDIA_EXTENSIONS:
                media.append(path)
            elif ext in organizer.DOCUMENT_EXTENSIONS:
                documents.append(path)
            else:
                unrecognized.append(path)
        return organizer.SourceScan(media=media, documents=documents, unrecognized=unrecognized)

    monkeypatch.setattr(organizer, "scan_source", no_refuse)
    broken = organizer.scan_source(tmp_path, all_files=True)
    assert sorted(p.name for p in broken.media) == ["holiday.jpg", "holiday.jpg_original"]

    # Production still refuses.
    good = scan_source(tmp_path, all_files=True)
    assert [p.name for p in good.media] == ["holiday.jpg"]
    assert [p.name for p in good.exiftool_backups] == ["holiday.jpg_original"]


def test_mutation_extension_count_loses_plain_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reporting by suffix alone would show '.jpg_original: 1' instead of 'exiftool backup'."""
    (tmp_path / "holiday.jpg_original").write_bytes(b"backup")

    def by_suffix(scan: organizer.SourceScan) -> dict[str, dict[str, int]]:
        return {
            "documents": dict(Counter(p.suffix.lower() or "(no ext)" for p in scan.documents)),
            "unrecognized": dict(
                Counter(p.suffix.lower() or "(no ext)" for p in scan.unrecognized)
            ),
            "exiftool_backups": dict(
                Counter(p.suffix.lower() or "(no ext)" for p in scan.exiftool_backups)
            ),
        }

    monkeypatch.setattr(organizer, "_skipped_extension_counts", by_suffix)
    broken = organizer._skipped_extension_counts(scan_source(tmp_path))
    assert EXIFTOOL_BACKUP_LABEL not in broken["exiftool_backups"]
    assert broken["exiftool_backups"] == {".jpg_original": 1}

    good = _skipped_extension_counts(scan_source(tmp_path))
    assert good["exiftool_backups"] == {EXIFTOOL_BACKUP_LABEL: 1}
