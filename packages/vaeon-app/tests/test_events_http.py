"""Event review over HTTP: reviewing trips on an already-organized drive, then applying to disk."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image
from starlette.testclient import TestClient
from vaeon_app import service
from vaeon_app.server import create_app
from vaeon_core.catalog import Catalog
from vaeon_core.drive import create_marker
from vaeon_core.event_review import propose as core_propose
from vaeon_core.events import slugify

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-vaeon-token": _TOKEN})


def _drive_with_library(client: TestClient, src: Path, drive: Path) -> None:
    """Organize a clustered source onto a connected (marked) drive, so trips can be reviewed in place."""
    drive.mkdir()
    create_marker(drive, "BackupA")
    started = client.post("/api/organize/run", json={"source": str(src), "destination": str(drive)})
    job_id = started.json()["job_id"]
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:") and json.loads(line[5:].strip())["type"] in (
                "done",
                "error",
            ):
                break


def _camera_image(path: Path, when: datetime, colour: int) -> None:
    """A real camera photo: Make/Model (-> Camera category) and DateTimeOriginal (-> dated)."""
    Image.new("RGB", (32, 32), (colour % 256, 40, 60)).save(path, "JPEG")
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-q",
            "-m",
            "-Make=TestCam",
            "-Model=X100",
            f"-DateTimeOriginal={when:%Y:%m:%d %H:%M:%S}",
            str(path),
        ],
        check=True,
    )


def _source(root: Path, groups: list[tuple[datetime, int]]) -> None:
    root.mkdir()
    n = 0
    for base, count in groups:
        for k in range(count):
            _camera_image(root / f"i{n:03d}.jpg", base + timedelta(minutes=20 * k), colour=n)
            n += 1


def test_merge_then_apply_to_disk_relocates_into_event_folder(
    client: TestClient, tmp_path: Path
) -> None:
    """The full in-place trip flow: propose on a drive -> merge -> name -> preview -> apply moves."""
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10), (datetime(2026, 6, 21, 9), 10)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert proposed["ok"] is True
    assert len(proposed["clusters"]) == 2
    sid = proposed["session"]

    merged = client.post(f"/api/events/{sid}/merge", json={"indices": [0, 1]}).json()
    assert len(merged["clusters"]) == 1
    assert merged["clusters"][0]["count"] == 20

    named = client.post(f"/api/events/{sid}/apply", json={"names": ["Trip"]}).json()
    assert named["events"] == 1  # one trip named (links files.event_id)

    preview = client.post(f"/api/events/{sid}/preview", json={}).json()
    # all 20 files move under the merged event's START month/folder.
    assert len(preview["moves"]) == 20
    assert all("20260614_trip" in m["new"] for m in preview["moves"])

    job = client.post(f"/api/events/{sid}/apply-to-disk", json={}).json()
    with client.stream("GET", f"/api/jobs/{job['job_id']}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:") and json.loads(line[5:].strip())["type"] == "done":
                break
    landed = list(drive.rglob("20260614_trip/*.jpg"))
    assert len(landed) == 20  # the trip folder exists on disk with all 20 photos


def test_split_via_http_names_both_halves(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 12)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["clusters"]) == 1
    sid = proposed["session"]

    split = client.post(f"/api/events/{sid}/split", json={"index": 0, "at": 5}).json()
    assert sorted(c["count"] for c in split["clusters"]) == [5, 7]

    named = client.post(f"/api/events/{sid}/apply", json={"names": ["First", "Second"]}).json()
    assert named["events"] == 2  # both halves named


def test_organizing_does_not_auto_skip_clusters(client: TestClient, tmp_path: Path) -> None:
    """Secondary follow-on safety: organizing must apply only *saved* trips, never record skips
    for unnamed clusters -- otherwise fresh camera photos would vanish from the Trips screen."""
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)  # organize with NO trips named yet

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["clusters"]) == 1  # the cluster is still reviewable (not auto-skipped)


def test_organize_applies_a_previously_saved_trip(client: TestClient, tmp_path: Path) -> None:
    """Secondary follow-on: a source whose cluster is already a named event lands under its trip
    folder at organize time (matched by signature). Set up via the core so the files are genuinely
    fresh to the catalog (identical content would otherwise be de-duplicated, not re-placed)."""
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10)])
    db = tmp_path / "c.sqlite"

    # Record the event for this source's cluster WITHOUT cataloguing the files.
    resolutions, metadata = service.plan_resolve(src, db)
    cluster = core_propose(resolutions, metadata)[0]
    with Catalog(db) as catalog:
        catalog.record_event(
            name="Goa",
            slug=slugify("Goa"),
            start_date=cluster.start.isoformat(),
            file_count=cluster.count,
            signature=cluster.signature,
        )

    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)  # now organize the fresh files
    assert list(drive.rglob("*_goa/*.jpg")), "a saved trip was not applied at organize time"


def test_propose_rejects_a_non_drive_path(client: TestClient, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    r = client.post("/api/events/propose", json={"path": str(plain)}).json()
    assert r["ok"] is False
    assert "drive" in r["error"]


def test_ingest_preview_report(client: TestClient, tmp_path: Path) -> None:
    year = tmp_path / "Takeout" / "Photos from 2023"
    year.mkdir(parents=True)
    Image.new("RGB", (32, 32), (9, 9, 9)).save(year / "a.jpg", "JPEG")
    (year / "a.jpg.json").write_text(
        '{"photoTakenTime":{"timestamp":"1692113136"}}', encoding="utf-8"
    )

    report = client.post(
        "/api/ingest/preview",
        json={"takeout": str(tmp_path / "Takeout"), "destination": str(tmp_path / "out")},
    ).json()
    assert report["files"] == 1
    assert report["dates_photo_taken"] == 1
