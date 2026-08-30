"""The app's rename: preview first, then commit, through the same core the CLI uses. `(aix)` s3

**The last surface.** Stages 1 and 2 built `plan_rename` and `apply_rename` and the CLI called
them; the card said *"already named - renaming is not available here"*.

🔑 **PREVIEW BEFORE COMMIT is the one pattern every tool that moves files on a rename shares** -
Bulk Rename Utility's preview pane, Finder's new name before you confirm, Perforce's *"not
complete until you submit the changelist"*. Not a confirmation dialog: HIG guidance warns against
unnecessary ones, and *"are you sure?"* over an unseen change asks less than a preview answers.

⚠ **The two most load-bearing tests here are the last two.** One says the apply goes through
`apply_rename` and therefore records the `(aix)` stage 2b lease; the other says refusals reach the
screen in core's own words. A second apply path would silently stop renames surviving a catalog
rebuild - `(ahz)`'s measured data loss - and a re-worded refusal is `(afe)`'s shape.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from PIL import Image
from starlette.testclient import TestClient
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file
from truestill_core.migrate import RENAME_WORDING, RenameRefusal

#: Four days, three photographs each. ⚠ **TWELVE, NOT FOUR, AND THE NUMBER IS LOAD-BEARING**:
#: `events.DEFAULT_MIN_FILES` is 8, so a four-photograph trip is below the review screen's floor
#: and never becomes a card at all. The card test passed vacuously on the smaller fixture -
#: "no named card came back" is the failure that caught it.
_DAYS = ["2015-06-02", "2015-06-03", "2015-06-04", "2015-06-05"]
_PER_DAY = 3
_TOTAL = len(_DAYS) * _PER_DAY


def _stamp(paths: list[Path], day: str) -> None:
    """Give these photographs REAL camera EXIF, in one exiftool call per day.

    ⚠ **Bytes with a `.jpg` name are not enough, and that cost this file a rewrite.** `Camera` is
    ambiguous by construction (`label_routes`: the device rule's default label *and* a possible
    `Software` value), so the app resolves it by **re-reading metadata**
    (`_resolve_migration_routes`). A file with no metadata resolves to `fallback`, routes to the
    SIDE BIN, and renders ``Camera/2015/2015-06/`` - **with no trip folder at all**, which is the
    opposite of what a rename does. The fixture has to be photographs for the trip to exist.
    """
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-Make=Canon",
            "-Model=Canon EOS 5D",
            f"-DateTimeOriginal={day.replace('-', ':')} 09:00:00",
            *[str(path) for path in paths],
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def drive(tmp_path: Path, db_path: Path) -> Path:
    """A drive holding one four-day trip named ``Holiday``, and a catalog that knows it."""
    root = tmp_path / "Drive"
    root.mkdir(parents=True)
    marker = create_marker(root, label="Photos HDD")
    with Catalog(db_path) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for index, day in enumerate(_DAYS):
            written: list[Path] = []
            for shot in range(_PER_DAY):
                relative = f"Camera/2015/2015-06/{day} - Holiday/{day}_{shot}.jpg"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                seed = index * _PER_DAY + shot
                Image.new("RGB", (32, 32), (seed * 20 % 256, 90, 200)).save(path, "JPEG")
                written.append(path)
            _stamp(written, day)
            for shot, path in enumerate(written):
                relative = path.relative_to(root).as_posix()
                catalog.record_uploaded(
                    source_path=f"/src/{path.name}",
                    original_name=PurePosixPath(relative).name,
                    sha256=sha256_file(path),
                    copy_sha256=sha256_file(path),
                    perceptual=None,
                    size=path.stat().st_size,
                    captured_at=f"{day}T09:0{shot}:00",
                    category="Camera",
                    relative=relative,
                    drive_uuid=marker.uuid,
                )
        catalog.create_trip(
            name="Holiday", slug="holiday", start_date=_DAYS[0], end_date=_DAYS[-1], days=_DAYS
        )
    return root


def _trip_id(db_path: Path) -> int:
    with Catalog(db_path) as catalog:
        return catalog.named_trips_by_day()[_DAYS[0]].row_id


def _name_now(db_path: Path) -> str | None:
    with Catalog(db_path) as catalog:
        return catalog.named_row_name("trip", _trip_id(db_path))


def _job(client: TestClient, route: str, drive: Path, row_id: int, name: str) -> dict[str, Any]:
    """Start one rename job and return its terminal event. **Both halves are jobs.**"""
    started = client.post(
        route, json={"path": str(drive), "kind": "trip", "row_id": row_id, "name": name}
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert "job_id" in body, f"{route} did not start a job: {body}"
    with client.stream("GET", f"/api/jobs/{body['job_id']}/events") as stream:
        for line in stream.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] != "progress":
                terminal: dict[str, Any] = event
                return terminal
    missing = "the job stream ended with no terminal event"
    raise AssertionError(missing)


def _preview(client: TestClient, drive: Path, row_id: int, name: str) -> dict[str, Any]:
    event = _job(client, "/api/rename/preview", drive, row_id, name)
    assert event["type"] != "error", event
    summary: dict[str, Any] = event["summary"]
    return summary


def _run(client: TestClient, drive: Path, row_id: int, name: str) -> dict[str, Any]:
    return _job(client, "/api/rename/run", drive, row_id, name)


def test_the_card_carries_the_row_the_rename_needs(client: TestClient, drive: Path) -> None:
    """⚠ **The screen cannot rename what it cannot name.** `existing_id` and `existing_name` come
    out of ONE lookup, so the card cannot show one trip's name beside another's id - which would
    move the wrong photographs and look entirely correct doing it.

    The threshold is lowered through the screen's OWN settings route rather than by patching a
    default: `events.DEFAULT_MIN_FILES` is 8, each day here clusters separately, and three
    photographs a day is under it - so a default-threshold fixture proposes nothing and this test
    asserts over an empty list. That is the shape it failed in twice before it was fixed.
    """
    assert client.post("/api/events/settings", json={"min_files": _PER_DAY}).status_code == 200
    response = client.post("/api/events/propose", json={"path": str(drive)})
    assert response.status_code == 200, response.text
    named = [c for c in response.json()["cards"] if c.get("existing_name")]

    assert named, "no already-named card came back, so this proves nothing"
    for card in named:
        assert card["existing_id"] is not None, "a named card carries no row to rename"


def test_the_preview_says_what_would_move_and_writes_nothing(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """THE PREVIEW HALF. It answers the question the field evidence says to answer first."""
    before = sorted(p.relative_to(drive).as_posix() for p in drive.rglob("*.jpg"))

    body = _preview(client, drive, _trip_id(db_path), "Corsica 2015")

    assert body["moves"] == _TOTAL, body
    assert body["refusal"] is None
    assert "Holiday" in str(body["old_folder"]), body
    assert "Corsica 2015" in str(body["new_folder"]), body
    # ⚠ The assertion that makes this a preview rather than an apply.
    assert sorted(p.relative_to(drive).as_posix() for p in drive.rglob("*.jpg")) == before
    assert _name_now(db_path) == "Holiday", "the preview changed the catalog"


def test_a_refusal_reaches_the_screen_in_cores_own_words(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """⚠ **Q1012: `RENAME_WORDING` IS THE ONE HOME AND THE APP RENDERS IT.**

    A refusal the CLI shows and the app swallows is `(afe)`'s shape - two surfaces disagreeing
    about what happened, with the quieter one wrong. This asserts the app's sentence is core's
    sentence, not a lookalike written beside it: the wording is read from the map at test time,
    so re-wording the map moves this test with it and re-wording the app breaks it.
    """
    body = _preview(client, drive, _trip_id(db_path), "Holiday")

    assert body["refusal"] == RENAME_WORDING[RenameRefusal.UNCHANGED], body
    assert body["moves"] == 0


def test_an_empty_name_is_refused_before_anything_moves(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """The second refusal, so the first is not a single-member coincidence."""
    body = _preview(client, drive, _trip_id(db_path), "   ")

    assert body["refusal"] == RENAME_WORDING[RenameRefusal.EMPTY_NAME].format(kind="trip")
    assert _name_now(db_path) == "Holiday"


def test_the_run_moves_the_photographs_and_flips_the_name(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """THE COMMIT HALF, end to end through the HTTP surface and the job machinery."""
    event = _run(client, drive, _trip_id(db_path), "Corsica 2015")

    assert event["type"] != "error", event
    summary = event["summary"]
    assert summary["renamed"] is True, summary
    assert summary["moved"] == _TOTAL, summary
    assert summary["name_now"] == "Corsica 2015"
    assert _name_now(db_path) == "Corsica 2015"
    on_disk = [p.relative_to(drive).as_posix() for p in drive.rglob("*.jpg")]
    assert on_disk, "nothing is on the drive, so this proves nothing"
    assert all("Corsica" in path for path in on_disk), on_disk


def test_the_app_rename_records_the_lease_the_rebuild_guard_needs(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """🔑 **Q1014: THE ROUTE GOES THROUGH `apply_rename`, AND THIS IS HOW WE KNOW.**

    `apply_rename` records an `authored_decisions` lease in the same transaction as the name flip
    (`(aix)` stage 2b). That lease is what lets the drive's decisions document take the new name
    while `(ahz)` step 3 keeps refusing a **rebuilt** catalog holding a stale one.

    ⚠ **A parallel apply path in the app would pass every other test in this file** - the files
    move, the name flips, the screen says so - and would silently reintroduce `(ahz)`'s measured
    data loss, visible only after someone rebuilt a catalog months later. The lease is the
    fingerprint of having gone through core, so it is asserted here rather than assumed.
    """
    _run(client, drive, _trip_id(db_path), "Corsica 2015")

    with Catalog(db_path) as catalog:
        leases = catalog.authored_decisions()

    assert list(leases.values()) == ["Holiday"], (
        f"the app's rename recorded no lease over the old name, so it did not go through "
        f"apply_rename: {leases}"
    )
    assert [section for section, _key in leases] == ["trips"]


def test_the_run_leaves_a_record_of_its_own_kind(
    client: TestClient, drive: Path, db_path: Path
) -> None:
    """A rename moves the user's files, so it records what it did - filed as `rename`.

    ⚠ **Not `migrate`.** A reader asking *"what moved my photographs"* needs to tell a person
    renaming a trip from the layout template changing under everything, and `kind` is the only
    thing that separates them.

    ⚠ **THIS TEST EXISTS BECAUSE A GUARD FOUND THE GAP RATHER THAN BECAUSE ANYONE PLANNED IT.**
    `(aix)` stage 3 shipped a service that moved photographs and wrote no record;
    `test_no_service_writes_a_record_without_a_row_here` is what said so.

    The INDEX line is the assertion, not the detail file: the index is append-only and kept
    forever, while detail is pruned - so the index is what still answers "did this run happen".
    """
    _run(client, drive, _trip_id(db_path), "Corsica 2015")

    index = db_path.parent / "runs" / "index.jsonl"
    assert index.exists(), "the rename wrote no run index line"
    kinds = [json.loads(line)["kind"] for line in index.read_text().splitlines() if line.strip()]
    assert kinds == ["rename"], kinds
