"""A folder attach cannot list is named, and its files are not quietly dropped.

**Measured before it was fixed**, on a scratch drive with a real ``chmod 000`` folder: five files
on the drive, three of them under the locked folder. ``attach_drive`` reported
``linked=2, unreadable=0, absent=3`` and wrote two ``file_copies`` rows. The three files were
physically present and got no copy row, so ``verify`` could not check them, ``status`` would not
count them toward 3-2-1 and ``where`` could not find them.

Two things made that worse than silence. ``rglob`` swallows ``PermissionError`` by design, so an
unlistable subtree simply does not appear - the files were never candidates, which is why
``unreadable`` (a per-*file* count, incremented where a hash fails) read **0** rather than 3.
And ``absent`` means *"catalogued files whose copy is not actually on the drive"*, so the one
number that moved was stating the opposite of the truth about a drive holding those copies.

``organizer.scan_source`` already solved this for the source side with
``Path.walk(on_error=...)``; this is the same construction on the custody side.

**Folders are named without a count, files are counted** - the asymmetry
``SourceScan.unreadable_dirs`` already carries (`IMPLEMENTATION_STANDARDS.md` §9): the walk never
went inside, so any number would be invented.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from truestill_app.service.drives import attach_drive
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file

# One condition, never two stacked decorators - see `test_platform_skips_collect_everywhere.py`.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs POSIX permissions and a non-root user",
)

_UUID = "DRIVE-1"
_LOCKED = "Camera/2015/09"
_LAYOUT = {
    "Camera/2014/08/open-a.jpg": b"bytes-open-a",
    "Camera/2014/08/open-b.jpg": b"bytes-open-b",
    f"{_LOCKED}/locked-a.jpg": b"bytes-locked-a",
    f"{_LOCKED}/locked-b.jpg": b"bytes-locked-b",
    f"{_LOCKED}/locked-c.jpg": b"bytes-locked-c",
}


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """A drive holding an organized library whose per-drive copy rows are gone (re-attach)."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    shas: dict[str, str] = {}
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Drive")
        for relative, payload in _LAYOUT.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            shas[relative] = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{Path(relative).name}",
                original_name=Path(relative).name,
                sha256=shas[relative],
                copy_sha256=shas[relative],
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=_UUID,
            )
        catalog._conn.execute("DELETE FROM file_copies WHERE drive_uuid = ?", (_UUID,))
        catalog._conn.commit()
    return db, root, shas


@pytest.fixture
def locked(drive: tuple[Path, Path, dict[str, str]]) -> tuple[Path, Path, dict[str, str]]:
    """`drive`, with one folder the current user cannot list. Restored however the test ends."""
    db, root, shas = drive
    folder = root / _LOCKED
    folder.chmod(0o000)
    try:
        yield db, root, shas  # type: ignore[misc]
    finally:
        folder.chmod(stat.S_IRWXU)


def _recorded(db: Path) -> set[str]:
    with Catalog(db) as catalog:
        rows = catalog._conn.execute("SELECT relative FROM file_copies")
        return {str(r["relative"]) for r in rows}


def test_the_fixture_really_denies_the_folder(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """Precondition asserted in the body, not merely set in the fixture (§4).

    `chmod 000` is a no-op for root, and this file's own skip is what keeps that true - if the
    skip were ever narrowed, every assertion below would pass while testing nothing.
    """
    _db, root, _shas = locked
    assert not os.access(root / _LOCKED, os.R_OK), "the folder is still readable - no condition"


def test_an_unreadable_folder_on_the_drive_is_named(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """The fact must survive the walk. Named, never a bare number, never nothing."""
    db, root, _shas = locked

    result = attach_drive(root, db, write=True)

    assert result.unreadable_dirs == (_LOCKED,), (
        f"a folder attach could not list was not named: {result.unreadable_dirs}"
    )


def test_the_readable_copies_are_still_attached(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """One locked folder must not cost the rest of the drive - the partial-failure policy."""
    db, root, shas = locked

    result = attach_drive(root, db, write=True)

    assert result.linked == 2
    assert _recorded(db) == {r for r in shas if not r.startswith(_LOCKED)}


def test_an_ordinary_drive_names_no_folder(
    drive: tuple[Path, Path, dict[str, str]],
) -> None:
    """The cry-wolf half: a drive with nothing locked must report nothing (§4).

    Without this, a guard that named every folder would pass the test above and be switched off
    the first time it fired on a healthy drive.
    """
    db, root, shas = drive

    result = attach_drive(root, db, write=True)

    assert result.unreadable_dirs == ()
    assert result.linked == len(shas)
