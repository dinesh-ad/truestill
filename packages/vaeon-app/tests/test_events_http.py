"""Event review over HTTP: merge/split (UI-only, no CLI path) against real clustered fixtures."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image
from starlette.testclient import TestClient
from vaeon_app.server import create_app

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")

_TOKEN = "tok"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(token=_TOKEN, db=tmp_path / "c.sqlite")
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-vaeon-token": _TOKEN})


def _camera_image(path: Path, when: datetime, colour: int) -> None:
    """A real camera photo: Make/Model (-> Camera category) and DateTimeOriginal (-> dated)."""
    Image.new("RGB", (32, 32), (colour % 256, 40, 60)).save(path, "JPEG")
    subprocess.run(
        [
            "exiftool", "-overwrite_original", "-q", "-m",
            "-Make=TestCam", "-Model=X100",
            f"-DateTimeOriginal={when:%Y:%m:%d %H:%M:%S}", str(path),
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


def test_merge_two_clusters_via_http(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 10), (datetime(2026, 6, 21, 9), 10)])

    proposed = client.post("/api/events/propose", json={"source": str(src)}).json()
    assert len(proposed["clusters"]) == 2
    sid = proposed["session"]

    merged = client.post(f"/api/events/{sid}/merge", json={"indices": [0, 1]}).json()
    assert len(merged["clusters"]) == 1
    assert merged["clusters"][0]["count"] == 20

    applied = client.post(f"/api/events/{sid}/apply", json={"names": ["Trip"]}).json()
    assert applied["events"] == 20
    # all 20 -- including the June-21 photos -- land under the merged event's START month.
    assert applied["placements"]
    assert all("20260614_trip" in p["relative"] for p in applied["placements"])


def test_split_cluster_via_http(client: TestClient, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _source(src, [(datetime(2026, 6, 14, 9), 12)])

    proposed = client.post("/api/events/propose", json={"source": str(src)}).json()
    assert len(proposed["clusters"]) == 1
    sid = proposed["session"]

    split = client.post(f"/api/events/{sid}/split", json={"index": 0, "at": 5}).json()
    assert sorted(c["count"] for c in split["clusters"]) == [5, 7]

    applied = client.post(f"/api/events/{sid}/apply", json={"names": ["First", "Second"]}).json()
    assert applied["events"] == 12  # both halves named -> all placed


def test_ingest_preview_report(client: TestClient, tmp_path: Path) -> None:
    year = tmp_path / "Takeout" / "Photos from 2023"
    year.mkdir(parents=True)
    Image.new("RGB", (32, 32), (9, 9, 9)).save(year / "a.jpg", "JPEG")
    (year / "a.jpg.json").write_text('{"photoTakenTime":{"timestamp":"1692113136"}}', encoding="utf-8")

    report = client.post(
        "/api/ingest/preview",
        json={"takeout": str(tmp_path / "Takeout"), "destination": str(tmp_path / "out")},
    ).json()
    assert report["files"] == 1
    assert report["dates_photo_taken"] == 1
