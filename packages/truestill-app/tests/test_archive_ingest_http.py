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
from truestill_app.jobs import DRIVE_BUSY_CODE
from truestill_app.server import create_app
from truestill_core.archive_extract import STAGING_DIRNAME
from truestill_core.drive_lock import lock_for

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


# --- the unpack holds the drive ---------------------------------------------------------------


def test_an_unpack_refuses_while_another_process_holds_the_drive(tmp_path: Path) -> None:
    """⚠ **The behaviour change `(agg)` is, asserted through the real lock rather than a mock.**

    Unpacking writes a staging tree onto the destination drive, so it now declares `mutating=True`
    and takes `(aaw)`'s cross-process lock. Before 2026-08-23 it declared `"import preview"` and
    `mutating=False`, so this request **proceeded and wrote**, interleaving with whatever the
    other process was doing to the same drive.

    **`lock_for` is used rather than patched**: the property is that the OS refuses a second
    holder, and a stubbed lock would assert that this test can stub a lock. `(aaw)` made the same
    choice for the same reason.

    ⚠ **The holder here stands for a CLI `organize --apply`**, which is the reachable case -
    `cli._run_holding_the_drive` takes exactly this lock. A second *tab* was already refused
    before this change, by the unconditional in-process claim, which is why that is not what this
    test drives.
    """
    destination = tmp_path / "drive"
    destination.mkdir()
    source = tmp_path / "archives"
    _part(source, 1, {"Takeout/Google Photos/2014/IMG_1.jpg": b"x" * 64})

    with lock_for(destination, operation="organize"):
        client = _client(tmp_path / "c.sqlite")
        response = client.post(
            "/api/ingest/archives/run",
            json={"takeout": str(source), "destination": str(destination)},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False, f"the unpack ran while another process held the drive: {body}"
    assert body["code"] == DRIVE_BUSY_CODE
    assert "organize" in body["error"], "the refusal does not name what is holding the drive"

    staged = destination / STAGING_DIRNAME
    assert not staged.exists(), (
        "a refused unpack still wrote a staging tree; the refusal must happen before any byte"
    )


def test_an_unpack_proceeds_when_nothing_holds_the_drive(tmp_path: Path) -> None:
    """The cry-wolf half. A lock that refuses every unpack would satisfy the test above."""
    destination = tmp_path / "drive"
    destination.mkdir()
    source = tmp_path / "archives"
    _part(source, 1, {"Takeout/Google Photos/2014/IMG_1.jpg": b"x" * 64})

    client = _client(tmp_path / "c.sqlite")
    response = client.post(
        "/api/ingest/archives/run",
        json={"takeout": str(source), "destination": str(destination)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("code") != DRIVE_BUSY_CODE, f"refused with nothing holding the drive: {body}"
