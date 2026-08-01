"""The archive-ingest HTTP surface: precheck refuses by code, and confirm runs a job.

These two routes were written before the UI and sat untested in a working tree for a while.
They get the same treatment as everything else rather than a pass for having arrived early.

**Refusals are asserted by CODE, not by message text (guard rule 8).** Five refusals can render
similar-looking sentences, so a test matching on words can pass because a *different* refusal
fired - which is the overlapping-defence class exactly. `refusals` carries the machine-readable
`ArchiveRefusal` value, and that is what both the tests and the UI key on.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app_support import TOKEN
from starlette.testclient import TestClient
from truestill_app.server import create_app

_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _client(db: Path) -> TestClient:
    app = create_app(token=TOKEN, db=db)
    return TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN})


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _part(directory: Path, number: int, entries: dict[str, bytes]) -> Path:
    return _zip(directory / f"takeout-20260801T000000Z-{number:03d}.zip", entries)


def _precheck(client: TestClient, source: Path, destination: Path) -> dict[str, object]:
    response = client.post(
        "/api/ingest/archives/precheck",
        json={"takeout": str(source), "destination": str(destination)},
    )
    assert response.status_code == 200
    return dict(response.json())


def test_a_clean_set_may_proceed_and_reports_its_claim(tmp_path: Path) -> None:
    _zip(tmp_path / "src" / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8" + b"x" * 500})

    body = _precheck(_client(tmp_path / "c.sqlite"), tmp_path / "src", tmp_path / "dest")

    assert body["ok"] is True
    assert body["refusals"] == []
    assert body["claimed_bytes"] == 502
    assert body["media_entries"] == 1
    assert "claim" in str(body["detail"]).lower(), "the figure was not labelled as a claim"


def test_a_missing_part_refuses_with_that_code(tmp_path: Path) -> None:
    """By code, not by words: several refusals read similarly and only the code is unambiguous."""
    for number in (1, 2, 4):
        _part(tmp_path / "src", number, {f"a/IMG_{number}.jpg": b"\xff\xd8x"})

    body = _precheck(_client(tmp_path / "c.sqlite"), tmp_path / "src", tmp_path / "dest")

    assert body["ok"] is False
    assert body["refusals"] == ["missing_part"]
    assert "3" in str(body["detail"])


def test_a_nested_archive_refuses_with_that_code_and_names_the_entry(tmp_path: Path) -> None:
    _zip(tmp_path / "src" / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x", "a/inner.zip": b"PK"})

    body = _precheck(_client(tmp_path / "c.sqlite"), tmp_path / "src", tmp_path / "dest")

    assert body["refusals"] == ["nested_archive"]
    assert "a/inner.zip" in str(body["detail"])


def test_an_unreadable_part_refuses_with_that_code(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.zip").write_bytes(b"not a zip at all")

    body = _precheck(_client(tmp_path / "c.sqlite"), source, tmp_path / "dest")

    assert body["refusals"] == ["unreadable"]
    assert "broken.zip" in str(body["detail"])


def test_an_empty_folder_refuses_rather_than_succeeding_vacuously(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()

    body = _precheck(_client(tmp_path / "c.sqlite"), source, tmp_path / "dest")

    assert body["refusals"] == ["no_archives"]


def test_the_precheck_writes_nothing(tmp_path: Path) -> None:
    """Declining must be free - the destination is not even created."""
    _zip(tmp_path / "src" / "photos.zip", {"a/IMG_1.jpg": b"\xff\xd8x"})
    destination = tmp_path / "dest"

    _precheck(_client(tmp_path / "c.sqlite"), tmp_path / "src", destination)

    assert not destination.exists()


def test_confirming_starts_a_job_rather_than_answering_inline(tmp_path: Path) -> None:
    """Unpacking is long, so it goes through the job machinery like every other long path."""
    _part(tmp_path / "src", 1, {"Takeout/a/IMG_1.jpg": b"\xff\xd8x"})
    _part(tmp_path / "src", 2, {"Takeout/a/IMG_1.jpg.json": _SIDECAR})
    client = _client(tmp_path / "c.sqlite")

    response = client.post(
        "/api/ingest/archives/run",
        json={"takeout": str(tmp_path / "src"), "destination": str(tmp_path / "dest")},
    )

    assert response.status_code == 200
    assert "job_id" in response.json(), f"not a job payload: {response.json()}"
