"""Folder-picker + library-status endpoints (the UI v2 home screen's backend)."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
from truestill_core.catalog import Catalog


def test_library_status_is_honest_when_empty(client: TestClient) -> None:
    s = client.get("/api/library/status").json()
    assert set(s) == {
        "library_path",
        # Where the user SAID the library lives, and whether they have been asked - `(abx)`,
        # 2026-08-12. Two flat keys beside `library_path` rather than one nested object, because
        # they answer different questions from different sources: `library_path` is OBSERVED
        # (written after a run, cleared when unreachable) and `library_root` is DECLARED (stated
        # once, never auto-cleared). Folding them together would lose exactly the distinction the
        # entry exists for. `needs_library_root` is the gate - no declaration AND no files -
        # computed here so the rule has one home rather than being re-derived in the browser.
        "library_root",
        "needs_library_root",
        "backup_path",
        "files",
        "photos",
        "videos",
        "audio",
        "by_format",
        "places",
        # The AGE of the custody claim, added 2026-08-10 for `(abg)`. Not new tracking:
        # `last_verified` has been on `drives` all along and is already shown per drive; these
        # two carry it to the number a person reads. `custody_checked_at` is the OLDEST check
        # across the places counted and is None when any of them has never been checked, in
        # which case `never_checked_drives` NAMES them - no date would be true of the whole
        # claim, and the name is the only clue to what happened.
        "custody_checked_at",
        "never_checked_drives",
        "single_copy",
        # Per-file custody, added 2026-08-05. `places` counts DRIVES and stays for callers that
        # want it, but no sentence about files may be written against it again.
        "files_no_copy",
        "files_one_copy",
        "redundancy_floor",
        # Files that HAVE a copy, and the weakest of those. The rail reports on these; a file
        # with no copy at all is a Stats finding and must not drag the rail's floor to zero.
        "files_on_a_drive",
        "held_floor",
        "bytes",
        "catalog_path",
        "catalog_presence",
        "catalog_detail",
        "catalog_tone",
    }
    assert s["photos"] == 0
    assert s["videos"] == 0
    assert s["places"] == 0  # honest zero -> never a fake count
    # An empty library has no exposed files and no redundancy to claim; the strip reads
    # "nothing organized yet" rather than reassuring about nothing.
    assert s["files_no_copy"] == 0
    assert s["files_one_copy"] == 0
    assert s["redundancy_floor"] == 0
    assert s["files_on_a_drive"] == 0
    assert s["held_floor"] == 0
    assert s["catalog_path"].endswith("c.sqlite")
    assert s["catalog_presence"] in ("will_create", "empty")  # created on open may flip
    assert "error" not in (s.get("catalog_detail") or "").lower()


def test_library_status_empty_with_drives_is_alert(client: TestClient, tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Cabinet")
    s = client.get("/api/library/status").json()
    assert s["catalog_presence"] == "empty_with_drives"
    assert s["catalog_tone"] == "alert"
    assert "0 files but 1 drive" in s["catalog_detail"]
    assert s["files"] == 0


def _seed_media(db: Path) -> None:
    from truestill_core.catalog import Catalog  # noqa: PLC0415 - test-local

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="BackupA")
        rows = [
            ("IMG_1.jpg", "Camera/2023/08/IMG_1.jpg"),
            ("IMG_2.heic", "Camera/2023/08/IMG_2.heic"),
            ("VID_1.mp4", "Camera/2023/08/VID_1.mp4"),
        ]
        for i, (name, rel) in enumerate(rows):
            sha = f"{i:064x}"
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=1000,
                captured_at=None,
                category="Camera",
                relative=rel,
                drive_uuid="D1",
            )


def test_library_status_splits_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    s = client.get("/api/library/status").json()
    assert s["photos"] == 2  # jpg + heic
    assert s["videos"] == 1  # mp4
    assert s["by_format"]["photos"] == {"jpg": 1, "heic": 1}
    assert s["by_format"]["videos"] == {"mp4": 1}


def test_drives_split_photos_and_videos(client: TestClient, tmp_path: Path) -> None:
    _seed_media(tmp_path / "c.sqlite")
    payload = client.get("/api/drives").json()
    assert set(payload) == {"drives", "at_risk"}
    drives = payload["drives"]
    assert len(drives) == 1
    assert set(drives[0]) == {
        "label",
        "uuid",
        "files",
        "photos",
        "videos",
        "audio",
        "size",
        "last_seen",
        "last_verified",
        "path",
        "reach",
        # Added 2026-08-09 with the drive card's decisions lines. ONE nested field rather than
        # five flat ones, so this contract grows by a single key and a consumer that does not
        # care about decisions is unchanged.
        "decisions",
        # Added 2026-08-11 - `(abg)` Stage 2. Copies recorded here that a check looked for and
        # did not find, and when. Two flat keys rather than one nested field, unlike `decisions`
        # above: a count and its date are a single fact read together on one line, and nesting
        # them would put a `.length` between the card and the number it prints.
        "not_found",
        "not_found_at",
    }
    assert drives[0]["photos"] == 2
    assert drives[0]["videos"] == 1
    assert set(payload["at_risk"][0]) == {"name", "drive"}


def test_fs_dirs_returns_roots_when_no_path(client: TestClient) -> None:
    data = client.get("/api/fs/dirs").json()
    assert set(data) == {"path", "parent", "roots", "entries"}
    assert any(r["label"] == "Home" for r in data["roots"])
    assert data["entries"] == []


def test_fs_dirs_lists_subdirectories(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "sub-a").mkdir()
    (tmp_path / "sub-b").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    data = client.get("/api/fs/dirs", params={"path": str(tmp_path)}).json()
    assert set(data) == {"path", "parent", "roots", "entries"}
    names = [e["name"] for e in data["entries"]]
    assert names == ["sub-a", "sub-b"]  # dirs only, hidden excluded, sorted


def test_fs_validate_counts_media(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    v = client.get("/api/fs/validate", params={"path": str(tmp_path)}).json()
    assert set(v) == {
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert v["is_dir"] is True
    assert v["media"] == 2  # jpg + mp4, not the txt


def test_fs_validate_missing_path(client: TestClient, tmp_path: Path) -> None:
    v = client.get("/api/fs/validate", params={"path": str(tmp_path / "nope")}).json()
    # resolve() succeeds for a missing leaf; the full resolved key set is returned with exists=False.
    assert set(v) == {
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert v["exists"] is False
    assert v["media"] == 0


def test_fs_create_makes_a_new_backup_folder(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "new" / "BackupA"  # a nested, not-yet-existing destination
    r = client.post("/api/fs/create", json={"path": str(target)}).json()
    assert set(r) == {
        "created",
        "exists",
        "is_dir",
        "readable",
        "writable",
        "is_drive",
        "media",
        "media_capped",
        "unreadable",
    }
    assert r["created"] is True
    assert r["is_dir"] is True
    assert r["writable"] is True
    assert target.is_dir()


def test_clean_empty_preview_and_apply_key_sets(client: TestClient, tmp_path: Path) -> None:
    """Empty-folder cleanup JSON shape for the post-move offer (shared with completion cards)."""
    root = tmp_path / "drive"
    (root / "Camera" / "2013" / "09").mkdir(parents=True)
    emptied = ["Camera/2013/09", "Camera/2013", "Camera"]

    preview = client.post(
        "/api/clean-empty/preview", json={"path": str(root), "emptied": emptied}
    ).json()
    assert set(preview) == {"ok", "path", "backend", "removable", "occupied"}
    assert preview["ok"] is True
    assert "Camera/2013/09" in preview["removable"]

    applied = client.post(
        "/api/clean-empty/apply", json={"path": str(root), "emptied": emptied}
    ).json()
    assert set(applied) == {"ok", "path", "removed", "trashed", "deleted", "failures"}
    assert applied["ok"] is True
    # Removal may trash, delete, or fail (gio trash often refuses under /tmp); key set is the pin.
    assert isinstance(applied["removed"], int)
    assert isinstance(applied["failures"], list)
