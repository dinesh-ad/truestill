"""Copy the library to a second drive: per-drive presence, verify-after-write, free-space guard."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import TOKEN
from PIL import Image
from starlette.testclient import TestClient
from truestill_app import service
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker


def _finish(client: TestClient, job_id: str) -> dict:
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event["type"] in ("done", "error"):
                    return event
    message = "job never finished"
    raise AssertionError(message)


def _library_on(client: TestClient, drive: Path, n: int) -> None:
    src = drive.parent / f"src-{drive.name}"
    src.mkdir()
    for i in range(n):
        Image.new("RGB", (16, 16), (i * 7 % 256, 30, 60)).save(src / f"p{i}.jpg", "JPEG")
    drive.mkdir()
    create_marker(drive, drive.name)
    started = client.post("/api/organize/run", json={"source": str(src), "destination": str(drive)})
    _finish(client, started.json()["job_id"])


def test_backup_copies_library_and_records_per_drive(client: TestClient, tmp_path: Path) -> None:
    a, b = tmp_path / "DriveA", tmp_path / "DriveB"
    _library_on(client, a, 4)
    b.mkdir()
    create_marker(b, "DriveB")

    preview = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert set(preview) == {
        "ok",
        "from",
        "to",
        "will_register",
        "will_read",
        "count",
        "photos",
        "videos",
        "audio",
        "bytes",
        "free",
        "enough",
    }
    assert preview["ok"] is True
    assert preview["count"] == 4
    assert preview["enough"] is True

    done = _finish(
        client,
        client.post("/api/backup/run", json={"source": str(a), "target": str(b)}).json()["job_id"],
    )
    assert done["type"] == "done"
    assert done["summary"]["copied"] == 4

    # the files are physically on DriveB, byte-verified and recorded as copies there
    assert len(list(b.rglob("*.jpg"))) == 4
    drives = {d["label"]: d for d in client.get(f"/api/drives?token={TOKEN}").json()["drives"]}
    assert drives["DriveB"]["photos"] == 4
    assert client.get(f"/api/drives?token={TOKEN}").json()["at_risk"] == []  # now safe in 2 places

    # second run: everything is already on DriveB -> nothing to copy
    again = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert again["count"] == 0


def test_backup_rejects_the_same_folder_twice(client: TestClient, tmp_path: Path) -> None:
    """Copying a drive onto itself is the one thing still worth refusing outright."""
    a = tmp_path / "DriveA"
    _library_on(client, a, 2)

    same = client.post("/api/backup/preview", json={"source": str(a), "target": str(a)}).json()
    assert set(same) == {"ok", "error"}
    assert same["ok"] is False
    assert "same folder" in same["error"]


def test_backup_accepts_an_unregistered_target_and_says_it_will_register_it(
    client: TestClient, tmp_path: Path
) -> None:
    """An ordinary empty folder is a perfectly good place for a first backup.

    Rejecting it forced a user to run the CLI's `drives --init` -- a concept the app never
    mentions -- before the app's own "copy your library" button would work.
    """
    a = tmp_path / "DriveA"
    _library_on(client, a, 2)
    plain = tmp_path / "plain"
    plain.mkdir()

    r = client.post("/api/backup/preview", json={"source": str(a), "target": str(plain)}).json()

    assert r["ok"] is True
    assert r["count"] == 2  # it knows what would be copied
    assert "plain" in r["will_register"]  # and says the folder will become a backup drive
    assert not (plain / ".truestill-drive.json").exists()  # preview still wrote nothing


def test_backup_warns_and_blocks_when_target_is_too_small(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disk-full mid-copy is the failure this feature exists to prevent: preview must flag it
    and the run must refuse rather than start and stop half-way."""
    a, b = tmp_path / "DriveA", tmp_path / "DriveB"
    _library_on(client, a, 4)
    b.mkdir()
    create_marker(b, "DriveB")

    tiny = SimpleNamespace(total=100, used=99, free=8)  # 8 bytes free
    monkeypatch.setattr("truestill_app.service.backup.shutil.disk_usage", lambda _p: tiny)

    preview = client.post("/api/backup/preview", json={"source": str(a), "target": str(b)}).json()
    assert preview["enough"] is False  # UI blocks the Copy button on this

    done = _finish(
        client,
        client.post("/api/backup/run", json={"source": str(a), "target": str(b)}).json()["job_id"],
    )
    assert done["type"] == "error"
    assert "not enough space" in done["message"]
    assert not list(b.rglob("*.jpg"))  # nothing was copied


def test_the_golden_path_organize_then_back_up(client: TestClient, tmp_path: Path) -> None:
    """The exact sequence a new user walks, end to end, with no CLI and no drive concepts.

    Organize into a plain folder through the app, then follow the Backups screen's own
    guidance and copy that library to a second plain folder. Before this, step two answered
    "the 'from' folder is not a connected truestill drive" -- the app rejecting the library it
    had just built, because organizing never registered its own destination.
    """
    src = tmp_path / "Pictures"
    src.mkdir()
    for i in range(3):
        (src / f"p{i}.jpg").write_bytes(f"golden-path-{i}".encode())
    library = tmp_path / "TruestillLibrary" / "Output"  # a plain folder, as a user would pick
    backup = tmp_path / "BackupDrive"
    backup.mkdir()

    started = client.post(
        "/api/organize/run",
        json={"source": str(src), "destination": str(library), "skip_undated": False},
    )
    done = _finish(client, started.json()["job_id"])
    assert done["type"] == "done"
    assert done["summary"]["organized"] == 3

    # Organizing registered its destination, so the library lives somewhere the app knows.
    status = client.get("/api/library/status").json()
    assert status["places"] == 1
    assert status["library_path"] == str(library)  # and the field prefills from it

    preview = client.post(
        "/api/backup/preview", json={"source": str(library), "target": str(backup)}
    ).json()
    assert preview["ok"] is True
    assert preview["count"] == 3

    started = client.post("/api/backup/run", json={"source": str(library), "target": str(backup)})
    done = _finish(client, started.json()["job_id"])
    assert done["type"] == "done"
    assert done["summary"]["copied"] == 3

    after = client.get("/api/library/status").json()
    assert after["places"] == 2  # the custody strip can now say "safe in 2 places"
    assert after["single_copy"] == 0
    assert after["backup_path"] == str(backup)


def test_a_library_organized_before_registration_is_attached_not_rejected(
    client: TestClient, tmp_path: Path
) -> None:
    """The migration case: a library organized by an older build has files but no marker.

    Backing it up must attach what is really there rather than refuse, and must never claim a
    file it cannot find.
    """
    src = tmp_path / "src"
    src.mkdir()
    for i in range(3):
        (src / f"q{i}.jpg").write_bytes(f"legacy-{i}".encode())
    library = tmp_path / "OldLibrary"

    started = client.post(
        "/api/organize/run",
        json={"source": str(src), "destination": str(library), "skip_undated": False},
    )
    _finish(client, started.json()["job_id"])

    # Rewind to the old state: drop the marker and every recorded copy, keeping `files`.
    (library / ".truestill-drive.json").unlink()
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog._conn.execute("DELETE FROM file_copies")
        catalog._conn.commit()
    assert client.get("/api/library/status").json()["places"] == 0

    attached = service.attach_drive(library, tmp_path / "c.sqlite", write=True)

    assert attached.registered is True
    assert attached.linked == 3  # all three copies were really there
    assert attached.absent == 0
    assert client.get("/api/library/status").json()["places"] == 1


def test_a_completed_copy_reports_photos_and_videos_separately(
    client: TestClient, tmp_path: Path
) -> None:
    """The split rule applies to the backup summary too.

    "Copied 2,269 photo(s)" folded videos into photos and used form-letter grammar. The server
    must hand the UI the counts it needs to say "2,266 photos · 3 videos".
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "shot.jpg").write_bytes(b"a-unique-photo")
    (src / "clip.mp4").write_bytes(b"a-unique-video")
    library = tmp_path / "Library"
    _finish(
        client,
        client.post(
            "/api/organize/run",
            json={"source": str(src), "destination": str(library), "skip_undated": False},
        ).json()["job_id"],
    )
    backup = tmp_path / "Backup"
    backup.mkdir()

    done = _finish(
        client,
        client.post("/api/backup/run", json={"source": str(library), "target": str(backup)}).json()[
            "job_id"
        ],
    )
    s = done["summary"]

    assert s["copied"] == 2
    assert s["photos"] == 1  # counted apart, never folded together
    assert s["videos"] == 1
    assert s["bytes_copied"] > 0  # the completion card's space story
    assert s["verified"] is True  # every copy was re-hashed before being recorded


def test_a_completed_copy_leaves_no_stale_not_a_backup_message(client: TestClient) -> None:
    """The page must not contradict itself.

    After a copy succeeded, the Check section still displayed "this folder isn't a truestill
    backup yet" about the folder now listed above it as a registered drive. Any completed
    operation that changes drive state clears what described the old one.
    """
    app_js = client.get("/static/app.js").text

    assert "async function refreshDriveState()" in app_js
    assert '$("verify-result").innerHTML = "";' in app_js  # the stale verdict is cleared
    assert "refreshDriveState();" in app_js  # and the copy handler calls it


def test_a_drive_card_can_offer_to_check_itself(client: TestClient, tmp_path: Path) -> None:
    """ "last checked: never" is only useful beside the thing that changes it.

    The action is offered only when the drive's folder is known -- drives are identified by
    marker uuid, never by path, so a card whose drive has never been seen at a path states the
    fact without an action it could not honour.
    """
    library = tmp_path / "Library"
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"one-photo")
    _finish(
        client,
        client.post(
            "/api/organize/run",
            json={"source": str(src), "destination": str(library), "skip_undated": False},
        ).json()["job_id"],
    )

    drives = client.get("/api/drives").json()["drives"]
    assert drives[0]["path"] == str(library)  # remembered where it was seen

    app_js = client.get("/static/app.js").text
    assert "drive-check" in app_js
    assert "d.path" in app_js  # rendered conditionally on knowing the path
