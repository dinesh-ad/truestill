"""An empty directory where a known drive should be is a refusal, not a new drive.

**The data-loss path this closes.** A FUSE mountpoint with nothing mounted on it is an ordinary
empty directory. Writes into it succeed and land on the computer's own disk; the files are then
**shadowed** the moment the filesystem returns, while still occupying the space. Nothing caught
it: `DestinationDevice` latches the device on FIRST sighting, so a run that starts in this state
adopts the local disk as its baseline; the marker is absent, and absence is what makes both
surfaces mint a *second* identity for a library the catalog already knows.

**Only a recorded path discriminates it**, and that was established by ruling the alternatives
out rather than by preference:

* `os.path.ismount` is true only while something IS mounted - measured `True` for `/proc`,
  `False` for an ordinary directory - so it answers `False` for exactly this case.
* The mount table and `/etc/fstab` keep no record once a FUSE mount is gone.
* Matching the drive LABEL to the directory name is a coin toss: `create_marker` defaults the
  label to that same directory name, so every second `Backup` folder would be refused.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.drive import (
    create_marker,
    drive_path_hint,
    drives_without_a_known_location,
    ghost_drive_at,
    ghost_drive_refusal,
)


class _Settings:
    """The `_SettingsReader` protocol, as a dict - the shape `reach_of` is already tested with."""

    def __init__(self, **values: str) -> None:
        self._values = values

    def get_setting(self, key: str) -> str | None:
        return self._values.get(key)


_UUID = "6f43b678-cf68-4943-9de7-a5309d82a62f"
_DRIVES = ((_UUID, "The Memory Cabinet"),)


def test_an_empty_folder_the_catalog_calls_a_drive_is_a_ghost(tmp_path: Path) -> None:
    """THE CASE THIS EXISTS FOR: the mountpoint is there, the filesystem is not."""
    mountpoint = tmp_path / "CloudDrive" / "The Memory Cabinet"
    mountpoint.mkdir(parents=True)
    settings = _Settings(**{drive_path_hint(_UUID): str(mountpoint)})

    ghost = ghost_drive_at(mountpoint, settings, _DRIVES)

    assert ghost is not None
    assert ghost.uuid == _UUID
    assert ghost.label == "The Memory Cabinet"
    assert ghost.recorded_at == str(mountpoint)


def test_the_same_folder_with_its_marker_present_is_not_a_ghost(tmp_path: Path) -> None:
    """The cry-wolf half. A connected drive must be ordinary, or this fires on every run."""
    root = tmp_path / "drive"
    root.mkdir()
    create_marker(root, label="The Memory Cabinet", uuid=_UUID)
    settings = _Settings(**{drive_path_hint(_UUID): str(root)})

    assert ghost_drive_at(root, settings, _DRIVES) is None


def test_a_brand_new_empty_folder_is_never_a_ghost(tmp_path: Path) -> None:
    """The false-refusal half, and the one that decides whether this can ship.

    Someone organizing into a fresh folder must not be blocked. The signal only fires where the
    catalog itself recorded that path as a drive root, so a path it has never seen is untouched.
    """
    fresh = tmp_path / "new-photos"
    fresh.mkdir()
    settings = _Settings(**{drive_path_hint(_UUID): str(tmp_path / "somewhere-else")})

    assert ghost_drive_at(fresh, settings, _DRIVES) is None


def test_with_no_hint_recorded_it_has_no_opinion(tmp_path: Path) -> None:
    """Fails OPEN. No recorded path means no way to tell, and guessing would block real work."""
    empty = tmp_path / "anywhere"
    empty.mkdir()

    assert ghost_drive_at(empty, _Settings(), _DRIVES) is None


def test_a_legacy_marker_also_counts_as_present(tmp_path: Path) -> None:
    """`.vaeon-drive.json` is still a marker (§3.1), so a pre-rename drive is not a ghost."""
    root = tmp_path / "drive"
    root.mkdir()
    (root / ".vaeon-drive.json").write_text(
        f'{{"uuid": "{_UUID}", "label": "The Memory Cabinet", '
        f'"created": "2024-01-01T00:00:00+00:00"}}',
        encoding="utf-8",
    )
    settings = _Settings(**{drive_path_hint(_UUID): str(root)})

    assert ghost_drive_at(root, settings, _DRIVES) is None


def test_drives_with_no_recorded_location_are_named(tmp_path: Path) -> None:
    """The residue this cannot rule on: no path, so no way to tell one empty folder from another."""
    drives = ((_UUID, "The Memory Cabinet"), ("other", "Output"))
    settings = _Settings(**{drive_path_hint(_UUID): str(tmp_path)})

    assert drives_without_a_known_location(settings, drives) == ("Output",)


def test_the_refusal_says_the_three_things_a_user_cannot_work_out(tmp_path: Path) -> None:
    """The third is the one nobody can discover: the files disappear AND the space stays gone."""
    mountpoint = tmp_path / "The Memory Cabinet"
    mountpoint.mkdir()
    settings = _Settings(**{drive_path_hint(_UUID): str(mountpoint)})
    ghost = ghost_drive_at(mountpoint, settings, _DRIVES)
    assert ghost is not None

    message = ghost_drive_refusal(ghost)

    assert "The Memory Cabinet" in message, "it does not say WHICH drive"
    assert "marker file is not there" in message, "it does not say why it refused"
    assert "DISAPPEAR" in message, "it does not warn that the files vanish when the drive returns"
    assert "using the space" in message, "it does not warn that the disk stays full"
    assert "--force-new-identity" in message, "it does not name the override"
