"""`truestill rescan`: it reads, it reports, and it changes nothing.

The move case is measured rather than assumed. On a scratch drive on 2026-08-07 a hand-moved
file was shown to reach `service/drives.py` line 363 with `sha in attached`, be hashed, and then
land in **no** bucket - `attach_drive` returned `linked=0, unmatched=0, unreadable=0, absent=0`
about a drive whose record named a path with nothing at it. These fixtures reproduce that drive.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from truestill_cli import cli as cli_module
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hash_cache import cache_path_for
from truestill_core.hashing import sha256_file

_UUID = "DRIVE-RESCAN-1"
_LAYOUT = {
    "Camera/2014/08/a.jpg": b"bytes-of-a",
    "Camera/2014/08/b.jpg": b"bytes-of-b",
    "Camera/2015/09/c.jpg": b"bytes-of-c",
}


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path]:
    """A registered drive whose three copies are recorded where they really are."""
    root, db = tmp_path / "drive", tmp_path / "c.sqlite"
    root.mkdir(parents=True)
    create_marker(root, label="Scratch", uuid=_UUID)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Scratch")
        for relative, payload in _LAYOUT.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            catalog.record_uploaded(
                source_path=f"/src/{Path(relative).name}",
                original_name=Path(relative).name,
                sha256=sha256_file(path),
                copy_sha256=sha256_file(path),
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=_UUID,
            )
    return root, db


def _run(root: Path, db: Path) -> int:
    return main(["rescan", str(root), "--db", str(db)])


def _copies(db: Path) -> dict[str, str]:
    with Catalog(db) as catalog:
        return {
            str(r["sha256"]): str(r["relative"])
            for r in catalog._conn.execute("SELECT sha256, relative FROM file_copies")
        }


def test_an_untouched_drive_reconciles_and_exits_zero(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The cry-wolf half: an ordinary drive must produce a quiet report and a zero exit."""
    root, db = drive
    assert _run(root, db) == 0
    out = capsys.readouterr().out
    assert "Everything the catalog records for this drive is where it says it is." in out
    assert "MOVED" not in out
    assert "NOT ACCOUNTED FOR" not in out


def test_a_hand_moved_file_is_reported_as_moved_and_names_both_paths(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """THE CASE THIS EXISTS FOR - and `verify` calls the same file MISSING (`(aba)` symptom 1)."""
    root, db = drive
    (root / "Camera/2014/08/a.jpg").rename(root / "Camera/2015/09/a.jpg")

    assert _run(root, db) == 1, "a drive that did not reconcile must not exit 0"
    out = capsys.readouterr().out
    assert "MOVED: 1" in out
    assert "Camera/2014/08/a.jpg  ->  Camera/2015/09/a.jpg" in out
    assert "NOT ACCOUNTED FOR" not in out, "a file that is right there must not read as missing"


def test_a_file_copied_in_by_hand_is_reported_as_unrecorded(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, db = drive
    (root / "Camera/2015/09/new.jpg").write_bytes(b"bytes-of-new")

    assert _run(root, db) == 1
    out = capsys.readouterr().out
    assert "ON THE DRIVE, NOT IN THE CATALOG: 1" in out
    assert "Camera/2015/09/new.jpg" in out


def test_a_deleted_file_is_not_accounted_for_and_is_never_guessed_at(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, db = drive
    (root / "Camera/2014/08/a.jpg").unlink()

    assert _run(root, db) == 1
    out = capsys.readouterr().out
    assert "NOT ACCOUNTED FOR: 1" in out
    assert "Truestill does not guess which" in out


def test_rescan_changes_nothing_at_all(drive: tuple[Path, Path]) -> None:
    """Read-only, asserted on the two things it could damage: the drive and the record.

    Compared by CONTENT, not by mtime: a run that rewrote a row with identical values would
    pass an mtime check on some filesystems and is still a write this command must not make.
    """
    root, db = drive
    (root / "Camera/2014/08/a.jpg").rename(root / "Camera/2015/09/a.jpg")

    before_disk = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    before_rows = _copies(db)

    _run(root, db)

    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == (
        before_disk
    ), "rescan wrote to the drive"
    assert _copies(db) == before_rows, "rescan changed the catalog"
    # Asked via `cache_path_for`, never by retyping the name: a hardcoded filename that is
    # not the real one passes whether the cache is written or not, and a mutation to a
    # writable cache proved exactly that before this line was corrected.
    assert not cache_path_for(db).exists(), (
        f"a read-only cache must never be created, found {cache_path_for(db)}"
    )


def test_the_report_says_what_it_cannot_tell_you(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A count with no route to fixing it is the defect the at-risk banner was corrected for.

    Three claims have to survive any rewording: it is a snapshot, it is not an integrity check,
    and nothing repairs what it finds yet.
    """
    root, db = drive
    _run(root, db)
    out = capsys.readouterr().out
    assert "snapshot" in out
    assert "truestill verify" in out
    assert "No command repairs any of the above yet" in out


def test_a_missing_catalog_is_refused_rather_than_created(tmp_path: Path) -> None:
    """Creating one would report the whole drive as unrecorded - a frightening false answer."""
    root, db = tmp_path / "drive", tmp_path / "absent.sqlite"
    root.mkdir()
    create_marker(root, label="Scratch", uuid=_UUID)

    assert main(["rescan", str(root), "--db", str(db)]) == 2
    assert not db.exists(), "rescan created a catalog it was told to read"


def test_a_folder_that_is_not_a_drive_is_refused(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert main(["rescan", str(plain), "--db", str(tmp_path / "c.sqlite")]) == 2


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs POSIX permissions and a non-root user",
)
def test_an_unreadable_folder_makes_the_report_say_it_is_incomplete(
    drive: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The interlock, built before the dangerous operation exists.

    Every file behind a locked folder reads as NOT ACCOUNTED FOR whether it is there or not.
    Removing records on that evidence is the Lightroom failure; the report has to say so.
    """
    root, db = drive
    locked = root / "Camera/2015/09"
    locked.chmod(0o000)
    try:
        assert not os.access(locked, os.R_OK), "the folder is still readable - no condition"
        assert _run(root, db) == 1
        out = capsys.readouterr().out
        assert "SOME OF THIS DRIVE COULD NOT BE READ" in out
        assert "Camera/2015/09" in out
        assert "treat that number as a floor rather than an answer" in out
    finally:
        locked.chmod(stat.S_IRWXU)


def test_a_file_where_the_catalog_says_it_is_is_never_read(
    drive: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE COST RULE, pinned - it is the difference between 14 s and 15 hours.

    Location is a question about paths. Re-hashing every copy to answer it would read the whole
    library over the connection it sits on: measured 3.9 MB/s on a cloud mount, so ~15 h for
    196 GiB, to learn what a stat already said. Nothing else fails if this regresses - the
    report stays correct and merely takes all day - so it needs its own assertion.

    Patched on `truestill_cli.cli`, which is where `_rescan_hashes` resolves the name; patching
    `truestill_core.hashing` would not reach the caller (ENGINEERING_STANDARD 4).
    """
    root, db = drive
    (root / "Camera/2014/08/a.jpg").rename(root / "Camera/2015/09/a.jpg")

    read: list[str] = []
    real = cli_module.sha256_file

    def counted(path: Path) -> str:
        read.append(Path(path).relative_to(root).as_posix())
        return real(path)

    monkeypatch.setattr(cli_module, "sha256_file", counted)
    _run(root, db)

    assert read == ["Camera/2015/09/a.jpg"], (
        "only the file that was not where the catalog said should have been read"
    )
    assert "Camera/2014/08/b.jpg" not in read
    assert "Camera/2015/09/c.jpg" not in read
