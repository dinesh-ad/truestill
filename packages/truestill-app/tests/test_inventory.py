"""Cheap organize inventory (backlog tt): walk + size, no exiftool or hashing."""

from __future__ import annotations

import os
import sys
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
    monkeypatch.setattr("truestill_app.service.organize.read_metadata", boom_exif)
    monkeypatch.setattr(exif_mod, "read_metadata", boom_exif)
    monkeypatch.setattr(hashing_mod, "sha256_file", boom_sha)
    monkeypatch.setattr(hashing_mod, "perceptual_hash", boom_phash)
    monkeypatch.setattr(scan_mod, "compute_hashes", boom_compute)
    monkeypatch.setattr("truestill_app.service.organize.resolve", boom_compute)

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
        # Comes from the walk `scan_source` already did - no open, no read. It is here because
        # dropping it let "Look inside" answer "nothing to organize" about a folder it had
        # failed to open; the `calls` assertion below is what keeps it cheap.
        "skipped_folders",
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
    expensive-call guard above would fire. Pin that wiring explicitly.

    Patched on ``service.organize``, the module that owns both functions - **not** on the
    ``service`` facade, which is where this pointed until the F10 split made it a re-export.
    ``organize_inventory`` and ``organize_preview`` are neighbours in one module, so an
    accidental call resolves through that module's globals and never touches the facade
    binding: with the old target this test passed with the very defect it names injected.
    Proven by mutation both ways.
    """
    _write(tmp_path / "a.jpg", b"x")
    seen: list[str] = []

    def fake_preview(*_a: object, **_k: object) -> dict[str, object]:
        seen.append("preview")
        return {"tier": "dedup", "files": 1, "photos": 1}

    monkeypatch.setattr("truestill_app.service.organize.organize_preview", fake_preview)
    organize_inventory(tmp_path)
    assert seen == []  # inventory must not route through the full preview


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs POSIX permissions and a non-root user",
)
def test_inventory_reports_a_folder_it_could_not_open(tmp_path: Path) -> None:
    """The cheap tier has to say what it could not see.

    `SourceInventory.unreadable_dirs` has always carried this; the payload dropped it, so
    "Look inside" could answer *Nothing to organize here* about a folder it had failed to open.
    Guarded here rather than only in the browser, where the payload is stubbed.
    """
    _write(tmp_path / "keep.jpg", b"\xff\xd8" + b"x" * 900)
    locked = tmp_path / "locked"
    locked.mkdir()
    _write(locked / "hidden.jpg", b"\xff\xd8" + b"y" * 900)
    locked.chmod(0o000)
    try:
        result = organize_inventory(tmp_path)
    finally:
        locked.chmod(0o755)

    # `(aer)`: the field is now `skipped_folders`, one structure per REASON. The promise this
    # pinned is unchanged - the payload names the folder it could not open - so the assertion
    # reaches it through the new shape rather than being relaxed, and now also states WHICH
    # reason, which the flat list could not.
    groups = result["skipped_folders"]
    assert [g["reason"] for g in groups] == ["unreadable"]
    assert [Path(p).name for p in groups[0]["folders"]] == ["locked"]
    assert groups[0]["total"] == 1
    assert groups[0]["remedy"], "the payload must carry the remedy; the browser has no map"


def test_an_ordinary_inventory_reports_no_skipped_folders(tmp_path: Path) -> None:
    """Anti-cry-wolf: a clean folder must not grow a warning."""
    _write(tmp_path / "a.jpg", b"\xff\xd8" + b"x" * 900)
    # `(aer)`: a group with nothing in it is ABSENT, not empty - the census's rule, now shared by
    # the folder groups. An ordinary folder must not sprout a row saying it has no hidden ones.
    assert organize_inventory(tmp_path)["skipped_folders"] == []


def test_a_hidden_folder_reaches_the_app_payload_with_its_own_remedy(tmp_path: Path) -> None:
    """`(aer)`: the payload carried unreadable folders and NOT hidden ones.

    A user with an album in `.MyAlbum` reached no app surface at all - the same silence the CLI
    had, in the half nobody had looked at. One structure covers both reasons now, so a third
    cannot be added to core and quietly miss a surface.

    ⚠ **The remedy travels in the payload**, already worded. `app.js` holds no map from reason to
    sentence: it used to hold a THIRD copy of the unreadable remedy, worded differently from the
    CLI's two, which is what a `reason`-only payload would have preserved.
    """
    (tmp_path / ".MyAlbum").mkdir()
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8")

    groups = organize_inventory(tmp_path)["skipped_folders"]

    assert [g["reason"] for g in groups] == ["hidden"]
    hidden = groups[0]
    assert [Path(p).name for p in hidden["folders"]] == [".MyAlbum"]
    assert "hidden" in hidden["label"]
    assert "rename" in hidden["remedy"], "the remedy is missing, so the browser has nothing to say"
    assert hidden["total"] == 1


def test_a_skipped_folder_group_never_carries_a_count_of_what_is_inside(tmp_path: Path) -> None:
    """⚠ The cry-wolf half, and the rule `c027dd3` wrote down.

    `total` counts FOLDERS. The walk did not enter them, so the number of files inside is exactly
    what is unknown and no key may state it. The type carries no such field, so this asserts the
    shape a future "improvement" would have to break.
    """
    album = tmp_path / ".MyAlbum"
    album.mkdir()
    for index in range(7):
        (album / f"held-{index}.jpg").write_bytes(b"\xff\xd8")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8")

    group = organize_inventory(tmp_path)["skipped_folders"][0]

    assert group["total"] == 1, "total counts folders, and there is one folder"
    assert set(group) == {"reason", "label", "remedy", "folders", "total"}, (
        f"a key appeared that could carry a file count: {sorted(group)}"
    )


def test_a_long_folder_list_elides_and_says_how_many_it_did_not_show(tmp_path: Path) -> None:
    """`(aer)` problem 4: `analyze` capped at 20 and `organize` printed the list uncapped.

    Two surfaces disagreeing about one list, so a tree with hundreds of hidden folders buried its
    own report on one of them. The cap lives in core now (`FOLDER_PREVIEW`) and `total` carries the
    real number, so the "and N more" line comes from one place and they cannot part company again.

    ⚠ Truncation is never silent (§9): a capped list that does not say it was capped reads as a
    complete one, which is `_duplicate_report`'s rule applied to folders.

    ⚠ **THE NUMBERS HERE ARE ABSOLUTE, NOT `FOLDER_PREVIEW + 5`.** Written in terms of the constant
    it guards, this test adapts to any value of it and passes at 20, at 100,000 and at zero -
    §4's twenty-ninth member. A mutation raising the cap to 100,000 **survived** until it was
    rewritten this way. What the world imposes is that a report must not bury itself, so the
    assertion is that 25 hidden albums produce at most a couple of dozen lines.
    """
    made = 25
    for index in range(made):
        (tmp_path / f".album-{index:03d}").mkdir()
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8")

    group = organize_inventory(tmp_path)["skipped_folders"][0]

    assert group["total"] == made, "the real number must survive the cap"
    assert len(group["folders"]) < made, "the list was not capped at all"
    assert len(group["folders"]) <= 24, (
        f"{len(group['folders'])} folder lines is a report burying itself"
    )
    assert group["folders"], "capped to nothing is not a cap, it is a silence"
