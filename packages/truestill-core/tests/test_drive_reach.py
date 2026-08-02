"""A registered drive is connected, offline, or not-known-about - and those are three things.

Lightroom's lesson, confirmed in the `(yy)` design pass: a disconnected external drive is an
expected, self-healing state. Reporting it the way a missing file is reported is what makes a
backup tool feel broken. `(aap)` fixed the *message* for an unreachable path; this makes the
*state* first-class so every surface can say the same thing.

**The third state is the point of this file.** A boolean would have to fold "we have never
recorded where this drive lives" into connected or offline, and the offline fold is the
dangerous one: it tells someone their backup drive is gone when truestill simply has no idea
where it is. That is not a corner case - it is the normal state of every drive a CLI-only user
has ever registered.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.drive import (
    DriveReach,
    create_marker,
    drive_path_hint,
    drive_reach,
)


def test_a_drive_at_its_remembered_path_is_connected(tmp_path: Path) -> None:
    root = tmp_path / "DriveA"
    root.mkdir()
    marker = create_marker(root, "Photos HDD")

    assert drive_reach(str(root), marker.uuid) is DriveReach.CONNECTED


def test_a_drive_whose_remembered_path_is_gone_is_offline_not_missing(tmp_path: Path) -> None:
    """The state this whole item exists to name. Unplugged is normal, and self-healing."""
    root = tmp_path / "DriveA"
    root.mkdir()
    marker = create_marker(root, "Photos HDD")
    hint = str(root)

    for child in root.iterdir():
        child.unlink()
    root.rmdir()

    assert drive_reach(hint, marker.uuid) is DriveReach.OFFLINE


def test_a_drive_we_have_never_located_is_unknown_not_offline() -> None:
    """Cry-wolf half, and the reason this is not a boolean.

    A drive registered and used entirely from the CLI had no remembered path until this item
    started writing one. Calling that "offline" would announce a lost backup on the strength of
    truestill's own ignorance.
    """
    assert drive_reach(None, "some-uuid") is DriveReach.UNKNOWN
    assert drive_reach("", "some-uuid") is DriveReach.UNKNOWN


def test_a_different_drive_at_that_path_is_offline(tmp_path: Path) -> None:
    """Someone else's marker is not a yes.

    Two external drives take turns on one mount point. The question is whether *this* drive is
    reachable, so finding a different one there must not answer it.
    """
    root = tmp_path / "Mount"
    root.mkdir()
    create_marker(root, "Some Other Drive")

    assert drive_reach(str(root), "the-drive-we-asked-about") is DriveReach.OFFLINE


def test_a_path_that_is_not_a_drive_at_all_is_offline(tmp_path: Path) -> None:
    """Present but unmarked: the folder exists and this drive is still not there."""
    plain = tmp_path / "JustAFolder"
    plain.mkdir()

    assert drive_reach(str(plain), "some-uuid") is DriveReach.OFFLINE


def test_the_hint_key_is_namespaced_and_stable() -> None:
    """It is a settings key two packages now share; a rename silently orphans stored hints."""
    assert drive_path_hint("abc-123") == "path_hint.drive.abc-123"
