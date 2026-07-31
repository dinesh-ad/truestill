"""Attach finds a copy by its content, not by a path the catalog remembers.

**The defect, measured on the real library.** ``attach_drive`` located copies through
``files.relative`` - a *per-content* column written once at organize time and **never updated
afterwards**. ``migrate-layout`` rewrites ``file_copies.relative`` (``Catalog.relocate_copy``)
and leaves the per-content one at the pre-migration path; there is no ``UPDATE files ...
relative`` anywhere in ``catalog.py``. On the maintainer's catalog **0 of 2,300** of those paths
still exist on the drive.

**What that costs, precisely.** On a *fully attached* drive it costs nothing: the already-known
filter skips every row before a path is read. The damage lands on **re-attach**, where the
drive's copy rows are gone and attach has real work to do - measured at **linked=0, absent=2,300
while the drive physically held 2,269 of those files**. Attach was correct exactly while it had
nothing to do and failed completely on the disaster-recovery path.

**Why matching by content, and not the two alternatives.** Reading another drive's
``file_copies.relative`` rescued **212 of 2,300 (9%)**, because drives are on different layouts -
one drive had ``2014/2014-08/2014-08 - Everyday/x.jpg`` where the other had
``2014/2014-08/2014-08-14 - Wayanad/2014-08-16/x.jpg``. Re-rendering the expected path needs the
drive's scheme *and* its event and trip folder names, which is the same brittleness one layer up.
A hash is true regardless of layout or migration history - which is what the drive marker already
promises (`IMPLEMENTATION_STANDARDS.md` §3.1: identity is never a path).

**These fixtures are migrated on purpose.** A fresh-catalog test passes against the broken code
and proves nothing about the state a real library is in - which is exactly how this survived.
"""

from __future__ import annotations

import errno
import sqlite3
from pathlib import Path

import pytest
from truestill_app.service.drives import attach_drive
from truestill_core.catalog import Catalog
from truestill_core.destinations import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout import PRESETS, scheme_from_string
from truestill_core.migrate import run_migration

_UUID = "DRIVE-1"


def _organized(db: Path, root: Path, names: tuple[str, ...]) -> dict[str, str]:
    """A drive organized under the *old* category-first layout. Returns ``{name: sha256}``."""
    shas: dict[str, str] = {}
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Drive")
        for name in names:
            relative = f"Camera/2014/08/{name}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"bytes-of-{name}".encode())
            sha = sha256_file(path)
            shas[name] = sha
            catalog.record_uploaded(
                source_path=f"/src/{name}",
                original_name=name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=_UUID,
            )
    return shas


def _migrate(db: Path, root: Path) -> None:
    """Re-lay the drive out. Rewrites file_copies.relative; files.relative is left behind."""
    scheme = scheme_from_string(PRESETS["year-month-event"].timeline)
    with Catalog(db) as catalog:
        run_migration(catalog, LocalDestination(root), _UUID, scheme, apply=True)


def _forget_the_drives_copies(db: Path) -> None:
    """The re-attach case: this drive's per-drive rows are gone, the files are still there."""
    with Catalog(db) as catalog:
        catalog._conn.execute("DELETE FROM file_copies WHERE drive_uuid = ?", (_UUID,))
        catalog._conn.commit()


def _recorded(db: Path) -> dict[str, str]:
    with Catalog(db) as catalog:
        rows: list[sqlite3.Row] = list(
            catalog._conn.execute("SELECT sha256, relative FROM file_copies")
        )
    return {r["sha256"]: r["relative"] for r in rows}


@pytest.fixture
def migrated(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """A migrated drive whose copy rows have been lost - the state that broke attach."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    shas = _organized(db, root, ("a.jpg", "b.jpg", "c.jpg"))
    _migrate(db, root)
    _forget_the_drives_copies(db)
    return db, root, shas


def test_the_fixture_really_is_migrated_and_stale(
    migrated: tuple[Path, Path, dict[str, str]],
) -> None:
    """The fixture must reproduce the defect, or every test below proves nothing.

    Guard-rule 1: a regression fixture is validated against the bug it guards. If migration ever
    starts maintaining ``files.relative``, this fails and says the premise has moved.
    """
    db, root, shas = migrated
    with Catalog(db) as catalog:
        rows = catalog.organized_files()
    assert rows, "the fixture recorded no organized files"
    stale = [r for r in rows if not (root / str(r["relative"])).is_file()]
    assert len(stale) == len(shas), (
        "files.relative still points at real files - the fixture is not migrated, "
        "and a test built on it would pass against the broken code"
    )


# --- the promise ----------------------------------------------------------------------------


def test_attach_finds_every_copy_after_a_migration(
    migrated: tuple[Path, Path, dict[str, str]],
) -> None:
    """The measured failure, as a test: 0 linked / all absent, on files that are really there."""
    db, root, shas = migrated

    result = attach_drive(root, db, write=True)

    assert result.linked == len(shas), "attach missed copies that are on the drive"
    assert result.absent == 0
    recorded = _recorded(db)
    assert set(recorded) == set(shas.values())


def test_attach_records_the_path_the_file_is_actually_at(
    migrated: tuple[Path, Path, dict[str, str]],
) -> None:
    """Not merely *that* it was found - the recorded path must be the migrated one.

    Recording the stale path would relink the row and leave the next verify looking in the
    wrong place, which is the same defect wearing a different hat.
    """
    db, root, shas = migrated
    attach_drive(root, db, write=True)

    recorded = _recorded(db)
    # Without this the loop below is vacuous: nothing recorded means nothing asserted, and the
    # test passes against the very code it was written to fail on.
    assert len(recorded) == len(shas), "nothing was recorded, so the loop below proves nothing"
    with Catalog(db) as catalog:
        stale = {str(r["sha256"]): str(r["relative"]) for r in catalog.organized_files()}
    for sha, relative in recorded.items():
        assert (root / relative).is_file(), f"recorded a path that does not exist: {relative}"
        assert sha256_file(root / relative) == sha
        # The claim, stated directly rather than through a prefix that the preset happens to
        # keep: what was recorded is not the path the per-content column still remembers.
        assert relative != stale[sha], "recorded the stale pre-migration path"


def test_a_drive_with_no_copies_at_all_is_still_attached(tmp_path: Path) -> None:
    """The case attach was originally written for, and it takes the same route.

    A library organized before its folder was registered has ``files`` rows and no
    ``file_copies`` rows. There is no per-drive path to read, so nothing is read: the drive is
    walked and each file identified by its hash. One code path for both cases, which is why the
    migrated case stopped being special.
    """
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    shas = _organized(db, root, ("x.jpg", "y.jpg"))
    _forget_the_drives_copies(db)  # never registered: no per-drive rows ever existed

    result = attach_drive(root, db, write=True)

    assert result.linked == 2
    assert set(_recorded(db)) == set(shas.values())


# --- what must NOT happen -------------------------------------------------------------------


def test_a_file_the_catalog_does_not_know_is_not_attached(
    migrated: tuple[Path, Path, dict[str, str]],
) -> None:
    """Cry-wolf half: walking the drive must not sweep in files truestill never organized.

    Attach links *catalogued* content. A stray file is counted so the walk is not silent about
    what it read (§9), and left alone - claiming it would invent a copy of nothing.
    """
    db, root, shas = migrated
    (root / "holiday-snap-from-a-friend.jpg").write_bytes(b"not ours")

    result = attach_drive(root, db, write=True)

    assert result.linked == len(shas)
    assert result.unmatched == 1, "a file on the drive that is not catalogued must be counted"
    assert len(_recorded(db)) == len(shas)


def test_a_genuinely_missing_file_is_still_absent(
    migrated: tuple[Path, Path, dict[str, str]],
) -> None:
    """Cry-wolf half: content-matching must not turn 'not here' into a false attachment."""
    db, root, shas = migrated
    with Catalog(db) as catalog:
        gone = catalog.copy_relative(shas["b.jpg"], _UUID)
    assert gone is None  # rows were forgotten; find it on disk instead
    for path in root.rglob("b.jpg"):
        path.unlink()

    result = attach_drive(root, db, write=True)

    assert result.linked == len(shas) - 1
    assert result.absent == 1
    assert shas["b.jpg"] not in _recorded(db)


def test_an_unreadable_file_is_counted_and_never_guessed_at(
    migrated: tuple[Path, Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that cannot be read cannot be identified, and is not guessed at.

    Condition 1 made "present, no hash to check against" a real state - but that state needs a
    *known* copy to attach it to. Identified by content, an unreadable file has no identity at
    all, so attach counts it and leaves its catalog row absent rather than picking a row that
    looks likely. A wrong association would be recorded as fact and verify would confirm it.
    """
    db, root, shas = migrated
    real = sha256_file

    def boom(path: Path) -> str:
        if path.name == "b.jpg":
            raise OSError(errno.EIO, "Input/output error", str(path))
        return real(path)

    monkeypatch.setattr("truestill_app.service.drives.sha256_file", boom)

    result = attach_drive(root, db, write=True)

    assert result.unreadable == 1, "an unreadable file must be counted, never folded into linked"
    assert result.linked == len(shas) - 1
    assert result.absent == 1, "its catalog row is still not accounted for on this drive"
    assert shas["b.jpg"] not in _recorded(db), "attach guessed at a file it could not read"


def test_a_preview_attaches_nothing_and_reads_nothing(
    migrated: tuple[Path, Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preview purity (§5) survives the new route: no hashing, no rows, still a usable count."""
    db, root, shas = migrated
    monkeypatch.setattr(
        "truestill_app.service.drives.sha256_file",
        lambda path: pytest.fail(f"a preview read {path}"),
    )

    result = attach_drive(root, db, write=False)

    assert result.linked == len(shas), "the preview must still state the scale of the read"
    assert _recorded(db) == {}
