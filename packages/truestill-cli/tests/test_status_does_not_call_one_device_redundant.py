"""`truestill status` stops calling two folders of one stick redundant. `(aiy)`

**Measured in soak ten**, with the stick physically removed and nothing reachable:

    All catalogued content has at least two drive copies. Nicely redundant.

⚠ **`reclaim` was fixed first because it deletes** (`e6ef82c`). Until this, the two commands
answered the same question differently in one sitting - `reclaim` warned and `status` reassured.

🔑 **THE PREDICATE IS NOT RE-IMPLEMENTED HERE.** `drive.library_independence` resolves the
population and the devices and asks `drive.copy_independence`, the same function `reclaim` asks
about a different population. The wording is `drive.LIBRARY_REDUNDANCY`, core's one home.

⚠ **THE REGRESSION TO FEAR IS THE FALSE NEGATIVE**: a user with two genuinely separate drives must
still read good news. `test_two_real_filesystems_still_read_as_redundant` uses **two real
filesystems**, discovered at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file

_CANDIDATES = ("/dev/shm", f"/run/user/{os.getuid()}" if os.name == "posix" else "", "/tmp")


def _second_filesystem(here: Path) -> Path | None:
    """A writable directory on a different device from ``here``, or ``None``."""
    try:
        mine = here.stat().st_dev
    except OSError:  # pragma: no cover
        return None
    for candidate in _CANDIDATES:
        if not candidate:
            continue
        root = Path(candidate)
        try:
            if root.is_dir() and root.stat().st_dev != mine and os.access(root, os.W_OK):
                return root
        except OSError:
            continue
    return None


def _library_on(db: Path, roots: list[Path], source: Path) -> None:
    """One file, copied onto every root and recorded as a copy on each."""
    content = b"one-photo"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    sha = sha256_file(source)
    with Catalog(db) as catalog:
        for i, root in enumerate(roots):
            root.mkdir(parents=True, exist_ok=True)
            copy = root / "Camera/a.jpg"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(content)
            marker = create_marker(root, f"Drive {i}")
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))
            catalog.record_uploaded(
                source_path=str(source),
                original_name=source.name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=len(content),
                captured_at=None,
                category="Camera",
                relative="Camera/a.jpg",
                drive_uuid=marker.uuid,
            )


def test_two_drives_under_one_root_are_not_called_redundant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE DEFECT REPRODUCED.** No corpus, no loop device, no second filesystem needed.

    Two registered drives inside one `tmp_path` are one device by construction - soak ten's shape.
    """
    db = tmp_path / "c.sqlite"
    _library_on(db, [tmp_path / "stick/drive", tmp_path / "stick/backup"], tmp_path / "src/a.jpg")

    assert main(["status", "--db", str(db)]) == 0

    out = capsys.readouterr()
    text = out.out + out.err
    assert "at least two drive copies" in text, "the count is honest and must still be reported"
    assert "Nicely redundant" not in text, "the phrase soak ten caught is still printed"
    assert "ONE device" in text, "the user was not told both copies share a failure domain"


def test_two_real_filesystems_still_read_as_redundant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **THE REGRESSION.** Two genuinely separate drives must still read as good news."""
    other = _second_filesystem(tmp_path)
    if other is None:  # pragma: no cover - depends on the machine, not the code
        pytest.skip("this machine exposes one filesystem; the case needs two real ones")
    b = other / f"truestill-status-{os.getpid()}"
    try:
        db = tmp_path / "c.sqlite"
        _library_on(db, [tmp_path / "drive", b], tmp_path / "src/a.jpg")

        assert main(["status", "--db", str(db)]) == 0

        text = capsys.readouterr().out
        assert "on separate devices" in text, "a genuinely redundant library was not reassured"
        assert "WARNING" not in text
        assert "cannot tell" not in text, "both drives were connected and could be asked"
    finally:
        for path in sorted(b.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        b.rmdir()


def test_a_drive_it_cannot_see_is_reported_as_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The common case - a drive in a drawer. Stated, never a verdict, and never blocking."""
    db = tmp_path / "c.sqlite"
    _library_on(db, [tmp_path / "drive", tmp_path / "second"], tmp_path / "src/a.jpg")
    with Catalog(db) as catalog:
        for row in catalog.list_drives():
            if str(row["label"]) == "Drive 1":
                catalog.set_setting(drive_path_hint(str(row["uuid"])), str(tmp_path / "drawer"))

    assert main(["status", "--db", str(db)]) == 0, "unknown must never change the exit code"

    text = capsys.readouterr().out
    assert "cannot tell whether the copies are on separate devices" in text
    assert "ONE device" not in text, "unknown was reported as a proven verdict"
    assert "on separate devices, so" not in text, "unknown was reported as reassurance"
