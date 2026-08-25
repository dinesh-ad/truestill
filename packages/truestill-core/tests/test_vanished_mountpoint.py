"""Truestill must not rebuild a vanished drive's folders on the local disk.

**The failure this prevents, observed on a real migration.** A cloud FUSE mount drops under
sustained load and the mountpoint reverts to an ordinary empty directory. Writes into it then
*succeed* -- and because every write path calls ``mkdir(parents=True, exist_ok=True)`` first,
Truestill does not merely write into an empty folder: **it reconstructs the whole library tree
on the local disk**, silently filling it. `check_contained` does not help; it is lexical.

**`st_dev` is the signal**, not the mount table, which the same migration proved can lie -- a
dead mount lingers with no process behind it and the directory lists nothing. A mount is a
filesystem, so losing it changes the device id of the root. It also works for a destination
that was never a registered drive, which a marker check cannot.

**A real mount cannot be dropped from a test**, so the device read is injected at
`destinations.base.device_of` -- the module that owns the name, per §4's aiming rule. The
cry-wolf half needs no injection: it runs against a real directory that really does not move.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import truestill_core
from truestill_core.destinations import base
from truestill_core.destinations.base import DestinationDevice, DestinationError, device_of
from truestill_core.destinations.local import LocalDestination


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "drive"
    root.mkdir()
    return root


def _source(tmp_path: Path) -> Path:
    photo = tmp_path / "IMG_0001.jpg"
    photo.write_bytes(b"\xff\xd8" + b"x" * 64)
    return photo


# --- the guard itself ------------------------------------------------------------------------


def test_the_first_sighting_becomes_the_baseline(library: Path) -> None:
    """Nothing to compare against yet, so the first look is adopted rather than refused."""
    guard = DestinationDevice()
    guard.check(library)  # must not raise
    assert guard.baseline == device_of(library)


def test_a_changed_device_is_refused(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The drive was swapped underneath us -- exactly what a dropped mount looks like."""
    guard = DestinationDevice()
    guard.check(library)

    monkeypatch.setattr(base, "device_of", lambda _path: 999_999)
    with pytest.raises(DestinationError) as raised:
        guard.check(library)
    assert str(library) in str(raised.value)


def test_a_root_that_vanished_entirely_is_refused(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable root is a changed root. `None` must not be read as "no opinion"."""
    guard = DestinationDevice()
    guard.check(library)

    monkeypatch.setattr(base, "device_of", lambda _path: None)
    with pytest.raises(DestinationError):
        guard.check(library)


def test_a_destination_that_does_not_exist_yet_is_allowed(tmp_path: Path) -> None:
    """Cry-wolf: organizing into a folder Truestill is about to create must still work.

    There is no baseline to compare against, so the guard stands down until it sees a real
    device. Refusing here would break every first run into a new destination.
    """
    guard = DestinationDevice()
    guard.check(tmp_path / "not-created-yet")  # must not raise
    assert guard.baseline is None


def test_the_baseline_latches_once_a_real_device_appears(tmp_path: Path) -> None:
    """After we create it, later drops must be caught -- so the first real sighting latches."""
    root = tmp_path / "made"
    guard = DestinationDevice()
    guard.check(root)
    root.mkdir()
    guard.check(root)
    assert guard.baseline == device_of(root)


def test_a_stable_destination_never_trips(library: Path) -> None:
    """Cry-wolf, on a real filesystem with no injection: a healthy run is untouched."""
    guard = DestinationDevice()
    for _ in range(50):
        guard.check(library)


# --- the write paths -------------------------------------------------------------------------


def test_upload_creates_nothing_once_the_drive_is_gone(
    library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect, asserted on the filesystem: no rebuilt tree, no bytes, on the local disk."""
    destination = LocalDestination(library)
    photo = _source(tmp_path)
    destination.upload(photo, "2014/2014-08/first.jpg")  # establishes the baseline

    monkeypatch.setattr(base, "device_of", lambda _path: 999_999)
    with pytest.raises(DestinationError):
        destination.upload(photo, "2019/2019-07/second.jpg")

    assert not (library / "2019").exists(), "the folder tree was rebuilt after the drive left"


@pytest.mark.parametrize("method", ["upload", "adopt", "relocate"])
def test_every_creating_write_path_is_guarded(
    method: str, library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All three, not one: a fix reaching one copy and not its twin is this repo's own defect."""
    destination = LocalDestination(library)
    photo = _source(tmp_path)
    destination.upload(photo, "seed.jpg")

    monkeypatch.setattr(base, "device_of", lambda _path: 999_999)
    moving = tmp_path / "moving.jpg"
    moving.write_bytes(b"\xff\xd8y")
    calls = {
        "upload": lambda: destination.upload(photo, "a/b/new.jpg"),
        "adopt": lambda: destination.adopt(moving, "a/b/new.jpg"),
        "relocate": lambda: destination.relocate("seed.jpg", "a/b/new.jpg"),
    }
    with pytest.raises(DestinationError):
        calls[method]()
    assert not (library / "a").exists(), f"{method} rebuilt the tree"


def test_an_ordinary_run_still_creates_its_folders(library: Path, tmp_path: Path) -> None:
    """Cry-wolf for the whole commit: the normal path is completely unchanged."""
    destination = LocalDestination(library)
    photo = _source(tmp_path)

    destination.upload(photo, "2014/2014-08/IMG_0001.jpg")

    written = library / "2014" / "2014-08" / "IMG_0001.jpg"
    assert written.is_file()
    assert written.read_bytes() == photo.read_bytes()


def test_the_refusal_says_what_happened_and_what_to_do(
    library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """House-standard refusal: name it, say nothing was written, give a next step."""
    destination = LocalDestination(library)
    destination.upload(_source(tmp_path), "seed.jpg")

    monkeypatch.setattr(base, "device_of", lambda _path: 999_999)
    with pytest.raises(DestinationError) as raised:
        destination.upload(_source(tmp_path), "a/next.jpg")

    message = str(raised.value).lower()
    assert "nothing was written" in message
    assert "reconnect" in message or "run again" in message
    # The non-obvious part: without this the user has no idea their local disk was at risk.
    assert "this computer" in message or "local" in message


def test_the_backup_copy_loop_is_guarded_too() -> None:
    """The fourth site. `backup` does its own `mkdir` rather than going through a Destination.

    Asserted structurally: the loop needs a real two-drive catalog to run, which would test the
    fixture more than the rule. What must not happen is the guard reaching three write paths and
    missing the one that lives somewhere else - the "fix reached one copy and not its twin"
    defect ENGINEERING_STANDARD.md §4 records as this repo's recurring one.

    ⚠ **This read `truestill_app/service/backup.py` until `(ahf)` stage 1**, and its docstring
    said "this loop is in the app". The loop is `truestill_core.backup` now, so a core test reads
    a core file - which is what it should always have been. The needle moved; the property did
    not, which is the same note the `run.device.check` comment below already carries.
    """
    source = (Path(truestill_core.__file__).parent / "backup.py").read_text(encoding="utf-8")

    # ⚠ Spelled `run.device.check(run.target)` since `(afw)` lifted the loop onto a
    # context object. The needle moved; the property did not.
    guard = source.index("run.device.check(run.target)")
    creates = source.index("dst.parent.mkdir(parents=True, exist_ok=True)")
    assert guard < creates, "the guard must run BEFORE the folder is created, not after"

    # ⚠ **The two halves live in two packages since `(ahf)` stage 1, so each is asserted where
    # it is.** The device is CONSTRUCTED by the panel and CHECKED by the engine; a test that
    # looked for both in one file would pass only until the next move, and the property is that
    # the loop is handed a real device rather than that one file contains both words.
    panel = (
        Path(__file__).resolve().parents[3]
        / "packages/truestill-app/src/truestill_app/service/backup.py"
    ).read_text(encoding="utf-8")
    assert "DestinationDevice()" in panel, "nothing builds the device the copy loop checks"
