"""`truestill backup` copies the library to a second drive. `(ahf)` stage 2.

**Why this exists.** Backup was one of three mutating runs that lived only in the app, which
`PROJECT_STATUS.md` §1b's fourth exit condition forbids. It is also the surface `(ahd)` proved the
cost of: a guard that sits at "the only caller" is invisible until a second surface exists.

⚠ **THIS REFUSES AN UNREGISTERED FOLDER RATHER THAN REGISTERING IT**, and that is a ruling rather
than an omission. The app auto-attaches, which is right for a screen where the user just picked a
folder and can see what happened. On a terminal it would make one command do two things and the
second silently - **registering is a distinct act with its own guard**, `(agr)` part 1's ghost
refusal, and a command that mints a drive id as a side effect of backing up is how a ghost drive
gets created from a shell.

⚠ **NULL FINDING, and it is why no new wording was written**: `_drive_or_explain` already refuses
a folder that is not a drive and already names the remedy - `truestill drives --init <path>` - and
already refuses a ghost path. Checked before authoring a core constant for it. A core sentence
would also have been wrong: it would put a terminal command inside a string the app renders.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file


def _library(tmp_path: Path, *, register_target: bool = True) -> tuple[Path, Path, Path]:
    """A registered source drive with three files, and a target that may or may not be one."""
    db = tmp_path / "c.sqlite"
    src, dst = tmp_path / "Library", tmp_path / "Backup"
    src.mkdir(parents=True)
    dst.mkdir(parents=True)
    marker = create_marker(src, label="Library")
    if register_target:
        create_marker(dst, label="Backup")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for index, colour in enumerate(("navy", "olive", "maroon")):
            relative = f"Camera/2014/p{index}.jpg"
            path = src / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40 + index, 30 + index), colour).save(path)
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/p{index}.jpg",
                original_name=f"p{index}.jpg",
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )
    return db, src, dst


def _copies_on_target(dst: Path) -> int:
    return len([p for p in dst.rglob("*") if p.is_file() and not p.name.startswith(".")])


# ------------------------------------------------------------------------------- the refusals


def test_an_unregistered_target_is_refused_and_the_remedy_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The regression. Registering as a side effect is what this refuses to do."""
    db, src, dst = _library(tmp_path, register_target=False)

    assert main(["backup", str(src), str(dst), "--db", str(db), "--apply"]) == 2
    err = capsys.readouterr().err
    assert "is not a Truestill drive" in err
    assert "truestill drives --init" in err, "the refusal does not name the missing step"
    assert _copies_on_target(dst) == 0, "a refused backup copied something"


def test_a_ghost_path_is_refused(tmp_path: Path) -> None:
    """⚠ The state `(agr)` part 1 exists for: a folder where a known drive was recorded and its
    marker is gone. Writing there would shadow a library the catalog still believes in."""
    db, src, dst = _library(tmp_path)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="GHOST", label="Old Backup")
        # A ghost is a RECORDED EXPECTATION, not a filesystem state - `ghost_drive_at`'s whole
        # conclusion. The hint is what makes this path a known drive's home.
        catalog.set_setting(drive_path_hint("GHOST"), str(dst))
    (dst / ".truestill-drive.json").unlink()

    assert main(["backup", str(src), str(dst), "--db", str(db), "--apply"]) == 2
    assert _copies_on_target(dst) == 0


def test_the_same_drive_twice_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db, src, _dst = _library(tmp_path)
    assert main(["backup", str(src), str(src), "--db", str(db), "--apply"]) == 2
    assert "same drive" in capsys.readouterr().err


# ------------------------------------------------------------------------ preview and apply


def test_a_preview_writes_nothing_to_the_destination_or_the_catalog(tmp_path: Path) -> None:
    """Dry-run is the default, proved by bytes rather than by the absence of a message.

    ⚠ The catalog is settled with two opens **before** the baseline: a single load can hide a
    lazy first-run write inside it - schema creation, a settings default, a cleared hint.
    """
    db, src, dst = _library(tmp_path)
    with Catalog(db):
        pass
    with Catalog(db):
        pass
    before_db = db.read_bytes()
    before_files = {p: p.read_bytes() for p in sorted(dst.rglob("*")) if p.is_file()}

    assert main(["backup", str(src), str(dst), "--db", str(db)]) == 0

    assert db.read_bytes() == before_db, "the preview wrote to the catalog"
    assert {p: p.read_bytes() for p in sorted(dst.rglob("*")) if p.is_file()} == before_files


def test_the_preview_says_what_backup_does_not_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The reassurance costs a sentence and is what the field evidence says people want.**

    `docs/user-evidence-log.md` records users running with no backups because the tooling felt
    dangerous. "It copies, it never deletes, the source is untouched" is the thing a person needs
    before letting a tool near a second drive.
    """
    db, src, dst = _library(tmp_path)
    assert main(["backup", str(src), str(dst), "--db", str(db)]) == 0

    out = capsys.readouterr().out
    assert "Copies only" in out
    assert "deleted" in out, "the preview does not say nothing is deleted"
    assert "Preview only" in out, "the preview does not say it wrote nothing"


def test_apply_copies_and_records(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Cry-wolf half: a registered drive with `--apply` must still back up."""
    db, src, dst = _library(tmp_path)

    assert main(["backup", str(src), str(dst), "--db", str(db), "--apply"]) == 0, (
        capsys.readouterr().out
    )
    assert _copies_on_target(dst) == 3, "the backup copied nothing"
    with Catalog(db) as catalog:
        rows = catalog._conn.execute("SELECT COUNT(*) AS n FROM file_copies").fetchone()
    assert int(rows["n"]) == 6, "each file should be recorded on both drives"


def test_a_second_run_copies_nothing_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Idempotent, and it says so rather than reporting a second successful copy of nothing."""
    db, src, dst = _library(tmp_path)
    main(["backup", str(src), str(dst), "--db", str(db), "--apply"])
    capsys.readouterr()

    assert main(["backup", str(src), str(dst), "--db", str(db), "--apply"]) == 0
    assert "Nothing to copy" in capsys.readouterr().out
