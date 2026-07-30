"""Event review over HTTP: reviewing trips on an already-organized drive, then applying to disk."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest
from PIL import Image
from starlette.testclient import TestClient
from truestill_app import service
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.event_review import propose as core_propose
from truestill_core.events import slugify

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": _TOKEN})


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


def test_merge_via_http_names_the_combined_trip_and_moves_it_on_disk(
    client: TestClient, tmp_path: Path
) -> None:
    """Merging two gap-separated day-events over HTTP (the 13.3b inversion): the detector did not
    join these two weeks, so the user does it by hand, and the result is a TRIP -- never a
    concatenated event -- because a manual merge must obey the same §3e/§3f rules detection does
    (`trip_review.merge_review_cards`), which a raw event-item concatenation could not enforce.

    Closes the window 13.3b left open: naming used to persist a merged trip to the catalog with
    no way to reach disk (13.4 not yet built). Now it previews and applies exactly like a named
    event always has, landing every file under the trip's own header folder (Stage 2d, 13.4).
    """
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10), (datetime(2026, 6, 21, 9), 10)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert proposed["ok"] is True
    assert len(proposed["cards"]) == 2
    assert all(c["kind"] == "event" for c in proposed["cards"])  # too far apart to auto-join
    sid = proposed["session"]

    merged = client.post(f"/api/events/{sid}/merge", json={"indices": [0, 1]}).json()
    assert len(merged["cards"]) == 1
    card = merged["cards"][0]
    assert card["kind"] == "trip"
    assert card["count"] == 20
    assert [d["date"] for d in card["days"]] == ["2026-06-14", "2026-06-21"]

    named = client.post(f"/api/events/{sid}/apply", json={"names": ["Trip"]}).json()
    assert named == {"events": 0, "trips": 1}

    started = client.post(f"/api/events/{sid}/preview", json={}).json()
    preview = _stream_until_done(client, started["job_id"])["summary"]
    assert len(preview["moves"]) == 20  # all 20 files move under the trip's header folder
    assert all("2026-06-14 - Trip" in m["new"] for m in preview["moves"])

    job = client.post(f"/api/events/{sid}/apply-to-disk", json={}).json()
    done = _stream_until_done(client, job["job_id"])
    groups = done["summary"]["groups"]
    assert len(groups) == 1
    assert groups[0]["kind"] == "trip"
    assert groups[0]["name"] == "Trip"
    landed_14 = list(drive.rglob("2026-06-14 - Trip/2026-06-14/*.jpg"))
    landed_21 = list(drive.rglob("2026-06-14 - Trip/2026-06-21/*.jpg"))
    assert len(landed_14) == 10
    assert len(landed_21) == 10


def test_merge_via_http_refuses_across_a_year_boundary(client: TestClient, tmp_path: Path) -> None:
    """The HTTP layer must surface §3e's refusal, not swallow it: nothing merges, and the caller
    gets the reason back so the screen can show it (never a silent no-op)."""
    src = tmp_path / "src"
    _source(src, [(datetime(2025, 12, 30, 9), 8), (datetime(2026, 1, 2, 9), 8)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["cards"]) == 2
    sid = proposed["session"]

    result = client.post(f"/api/events/{sid}/merge", json={"indices": [0, 1]}).json()
    assert "error" in result
    assert "year boundary" in result["error"]

    # refused: the session's two cards are untouched, not partially merged into one trip.
    named = client.post(f"/api/events/{sid}/apply", json={"names": ["A", "B"]}).json()
    assert named == {"events": 2, "trips": 0}


def _stream_until_done(client: TestClient, job_id: str) -> dict:
    with client.stream("GET", f"/api/jobs/{job_id}/events?token={_TOKEN}") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event["type"] == "done":
                    return event
    pytest.fail("job never reached a done event")  # pragma: no cover


def test_apply_to_disk_reports_one_row_per_named_group_with_its_real_folder(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """13.3a + (qq): each named group's reveal path is absolute under the drive mount.

    A drive-relative parent alone makes ``/api/reveal`` resolve against the server cwd and
    fail. Removing the join in ``_reveal_folder_on_drive`` fails the absolute/under-drive and
    reveal-ok assertions below (mutation proof).
    """
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10), (datetime(2026, 6, 21, 9), 10)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["cards"]) == 2
    sid = proposed["session"]

    named = client.post(f"/api/events/{sid}/apply", json={"names": ["Goa", "Paris"]}).json()
    assert named == {"events": 2, "trips": 0}

    started = client.post(f"/api/events/{sid}/preview", json={})
    _stream_until_done(client, started.json()["job_id"])  # exercised by the test above
    job = client.post(f"/api/events/{sid}/apply-to-disk", json={}).json()
    done = _stream_until_done(client, job["job_id"])

    groups = done["summary"]["groups"]
    assert len(groups) == 2  # NOT collapsed into one aggregate row
    assert {group["kind"] for group in groups} == {"event"}
    by_name = {group["name"]: group for group in groups}
    assert set(by_name) == {"Goa", "Paris"}
    monkeypatch.setattr("truestill_app.service.drives.shutil.which", lambda _name: "/usr/bin/true")
    monkeypatch.setattr("truestill_app.service.drives.subprocess.Popen", lambda *_a, **_k: None)
    for name, expected_day in (("Goa", "2026-06-14"), ("Paris", "2026-06-21")):
        group = by_name[name]
        assert group["start"].startswith(expected_day)
        reveal = Path(group["path"])
        assert reveal.is_absolute()
        assert reveal.is_relative_to(drive)
        assert reveal.is_dir()
        landed = list(reveal.glob("*.jpg"))
        assert len(landed) == 10  # the reported path is the REAL folder, not guessed
        opened = client.post(f"/api/reveal?token={_TOKEN}", json={"path": group["path"]}).json()
        assert opened == {"ok": True, "path": group["path"]}


def test_mutation_reveal_folder_without_drive_join_is_not_under_the_mount(
    tmp_path: Path,
) -> None:
    """(qq) without the join: a bare relative parent is not under the drive and is not a dir."""
    drive = tmp_path / "DriveA"
    relative = "2026/2026-06/2026-06-14 - Goa/photo.jpg"
    joined = service._reveal_folder_on_drive(drive, relative, up=1)
    bare = Path(PurePosixPath(relative).parent.as_posix())
    assert joined == drive / "2026/2026-06/2026-06-14 - Goa"
    assert not bare.is_absolute() or not bare.is_relative_to(drive)
    assert bare != joined
    # The pre-fix shape fed to Path(...).is_dir() against cwd - almost never a real folder.
    assert not Path(str(PurePosixPath(relative).parent)).is_dir()


def test_split_via_http_names_both_halves(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 12)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["cards"]) == 1
    assert proposed["cards"][0]["kind"] == "event"
    sid = proposed["session"]

    split = client.post(f"/api/events/{sid}/split", json={"index": 0, "at": 5}).json()
    assert sorted(c["count"] for c in split["cards"]) == [5, 7]

    named = client.post(f"/api/events/{sid}/apply", json={"names": ["First", "Second"]}).json()
    assert named == {"events": 2, "trips": 0}  # both halves named


def test_organizing_does_not_auto_skip_clusters(client: TestClient, tmp_path: Path) -> None:
    """Secondary follow-on safety: organizing must apply only *saved* trips, never record skips
    for unnamed clusters -- otherwise fresh camera photos would vanish from the Trips screen."""
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10)])
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)  # organize with NO trips named yet

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    assert len(proposed["cards"]) == 1  # the cluster is still reviewable (not auto-skipped)


def test_propose_bundles_a_detected_multi_day_run_into_one_trip_card(
    client: TestClient, tmp_path: Path
) -> None:
    """13.3b's inversion, proven over HTTP: a genuine multi-day run (`detect_trips`, unchanged)
    assembles into ONE card labelled "trip"; a standalone active day elsewhere still renders as
    its own card labelled "event" - never both called "trip", the collision 13.2 flagged."""
    src = tmp_path / "src"
    _source(
        src,
        [
            (datetime(2026, 6, 14, 9), 8),
            (datetime(2026, 6, 15, 9), 8),
            (datetime(2026, 6, 30, 9), 8),  # far enough away not to bridge into the same run
        ],
    )
    drive = tmp_path / "DriveA"
    _drive_with_library(client, src, drive)

    proposed = client.post("/api/events/propose", json={"path": str(drive)}).json()
    cards = proposed["cards"]
    assert len(cards) == 2  # NOT three day-cards - the two consecutive days are one trip

    by_kind = {c["kind"]: c for c in cards}
    assert set(by_kind) == {"trip", "event"}
    trip = by_kind["trip"]
    assert trip["collapsed"] is False
    assert trip["start"] == "2026-06-14"
    assert trip["end"] == "2026-06-15"
    assert trip["count"] == 16
    assert [d["date"] for d in trip["days"]] == ["2026-06-14", "2026-06-15"]


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
    assert list(drive.rglob("* - Goa/*.jpg")), "a saved trip was not applied at organize time"


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

    started = client.post(
        "/api/ingest/preview",
        json={"takeout": str(tmp_path / "Takeout"), "destination": str(tmp_path / "out")},
    ).json()
    report = _stream_until_done(client, started["job_id"])["summary"]
    assert report["files"] == 1
    assert report["dates_photo_taken"] == 1
