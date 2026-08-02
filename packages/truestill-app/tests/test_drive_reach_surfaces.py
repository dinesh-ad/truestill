"""The drive listing says whether each drive is here, on both surfaces and in the same words.

`(yy)` design pass, Lightroom lesson 1: offline is an expected state, not an error. The payload
carries `reach` so the app and the CLI cannot describe the same drive differently - the same
reason `models.status_label` exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from truestill_app.service.drives import list_drives
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint


def _registered(db: Path, root: Path, label: str) -> str:
    """A drive in the catalog whose location has been recorded, as verify/init now do."""
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, label)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
    return marker.uuid


def test_a_present_drive_reads_as_connected(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    _registered(db, tmp_path / "DriveA", "Photos HDD")

    (row,) = list_drives(db)

    assert row["reach"] == "connected"
    assert row["path"] == str(tmp_path / "DriveA")


def test_an_absent_drive_reads_as_offline_and_offers_no_path(tmp_path: Path) -> None:
    """Offline, not missing and not an error - and no "Check now" for a folder that is gone."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "DriveA"
    _registered(db, root, "Photos HDD")
    for child in root.iterdir():
        child.unlink()
    root.rmdir()

    (row,) = list_drives(db)

    assert row["reach"] == "offline"
    assert row["path"] is None, (
        "a remembered path for an absent drive must not become an action that cannot work"
    )
    assert row["files"] == 0
    assert row["label"] == "Photos HDD", "the drive is still known; only its whereabouts are not"


def test_looking_twice_does_not_downgrade_offline_to_unknown(tmp_path: Path) -> None:
    """The hint is read, not taken.

    `take_live_path_hint` clears a dead path, which was right when the hint was only a
    convenience. It is now the one thing that lets a drive be called offline at all, so clearing
    it would make truestill forget it ever knew where the drive was - after a single listing.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "DriveA"
    _registered(db, root, "Photos HDD")
    for child in root.iterdir():
        child.unlink()
    root.rmdir()

    first = list_drives(db)[0]["reach"]
    second = list_drives(db)[0]["reach"]

    assert first == "offline"
    assert second == "offline", "the second look forgot where the drive had been"


def test_a_drive_never_located_reads_as_unknown(tmp_path: Path) -> None:
    """Cry-wolf half: ignorance must not be reported as a lost backup."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "DriveA"
    root.mkdir()
    marker = create_marker(root, "Photos HDD")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)  # no hint recorded

    (row,) = list_drives(db)

    assert row["reach"] == "unknown"
    assert row["path"] is None


def test_the_cli_listing_names_the_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both surfaces, same vocabulary. The CLI had no reachability information at all before."""
    db = tmp_path / "c.sqlite"
    here = tmp_path / "Here"
    gone = tmp_path / "Gone"
    _registered(db, here, "Present HDD")
    _registered(db, gone, "Absent HDD")
    for child in gone.iterdir():
        child.unlink()
    gone.rmdir()

    assert main(["drives", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "STATUS" in out
    assert re.search(r"Present HDD.*connected", out)
    assert re.search(r"Absent HDD.*offline", out)


def test_an_unregistered_folder_is_not_a_drive_at_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf half for the listing: a folder nobody registered is absent from it, not offline."""
    db = tmp_path / "c.sqlite"
    _registered(db, tmp_path / "DriveA", "Photos HDD")
    (tmp_path / "RandomFolder").mkdir()

    assert main(["drives", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "RandomFolder" not in out
    assert out.count("connected") == 1


def test_the_cli_records_where_it_saw_a_drive_so_the_listing_can_say_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without this the CLI has no reachability data at all and can only ever say "unknown".

    The fixtures above write the hint themselves, so they prove the *rendering* and prove
    nothing about who records it. This drives the real commands: `--init` and `verify` are the
    two moments the CLI holds a resolved drive root and a catalog at once.
    """
    db = tmp_path / "c.sqlite"
    root = tmp_path / "DriveA"
    root.mkdir()

    assert main(["drives", "--init", str(root), "--label", "Photos HDD", "--db", str(db)]) == 0
    with Catalog(db) as catalog:
        marker_uuid = next(iter(catalog.list_drives()))["uuid"]
        assert catalog.get_setting(drive_path_hint(str(marker_uuid))) == str(root), (
            "--init knows exactly where the drive is; not recording it leaves the listing blind"
        )

    # Now forget it, and let `verify` be the one to record it.
    with Catalog(db) as catalog:
        catalog.clear_setting(drive_path_hint(str(marker_uuid)))
    assert list_drives(db)[0]["reach"] == "unknown", "fixture check: the hint really is gone"

    assert main(["verify", str(root), "--db", str(db)]) == 0
    capsys.readouterr()

    assert list_drives(db)[0]["reach"] == "connected", (
        "verify resolved this drive at a real path and must remember it"
    )
