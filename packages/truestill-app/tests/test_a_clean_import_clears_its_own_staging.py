"""A finished import removes the tree it unpacked, and only that one. `(aht)`, ruled 2026-09-12.

The rules being guarded, each with its own test and its own opposite:

* **delete on success** - the product made the tree and the photographs are in the library;
* **keep on cancel or failure** - the run did not finish, and re-extracting a 200 GB export to
  retry is not a remedy;
* **scope by identity, never by age** - GitLab's cron swept backup temporaries older than 24
  hours and ate imports that were still running. A second export's tree is not this run's
  business, however old it is.
"""

from __future__ import annotations

import io
import json
import threading
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image
from truestill_app import service
from truestill_core.archive_extract import STAGING_DIRNAME

_SIDECAR = json.dumps({"photoTakenTime": {"timestamp": "1403000000"}}).encode()


def _jpeg(seed: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (seed * 37 % 256, seed * 11 % 256, 90)).save(buffer, "JPEG")
    return buffer.getvalue()


def _archive(directory: Path, stem: str, count: int, *, first: int = 0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for i in range(first, first + count):
            name = f"Takeout/Google Photos/Photos from 2014/IMG_{i:04d}.jpg"
            archive.writestr(name, _jpeg(i + 1))
            archive.writestr(f"{name}.json", _SIDECAR)
    return path


def _unpack_and_preview(source: Path, destination: Path, db: Path) -> dict[str, Any]:
    return dict(
        service.archive_ingest_run(source, destination, db)(lambda _p: None, threading.Event())
    )


def _trees(destination: Path) -> list[Path]:
    root = destination / STAGING_DIRNAME
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def test_a_clean_import_removes_the_tree_it_unpacked(tmp_path: Path) -> None:
    """⚠ **THE RULING.** 200 GB on a real Takeout, on the user's photo drive, where no OS cleaner
    will ever reach it. Asserted on the bytes, not on a returned flag."""
    source, destination, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(source, "takeout-001", 3)
    destination.mkdir()
    preview = _unpack_and_preview(source, destination, db)
    assert _trees(destination), "nothing was staged, so the deletion below proves nothing"

    summary = dict(
        service.ingest_run(Path(preview["source"]), destination, db)(
            lambda _p: None, threading.Event()
        )
    )

    assert summary["organized"] == 3, "the import did not happen, so of course nothing is staged"
    assert summary["finished_clean"] is True
    assert _trees(destination) == []
    assert "staging_bytes" not in summary, "the card would name a folder that is gone"


def test_a_cancelled_import_keeps_the_tree_and_reports_it(tmp_path: Path) -> None:
    """⚠ **The half that stops this becoming GitLab's second mistake.** A run the user stopped
    must not also destroy the extraction they would retry from."""
    source, destination, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(source, "takeout-001", 3)
    destination.mkdir()
    preview = _unpack_and_preview(source, destination, db)

    cancel = threading.Event()
    cancel.set()
    summary = dict(
        service.ingest_run(Path(preview["source"]), destination, db)(lambda _p: None, cancel)
    )

    assert _trees(destination), "a cancelled run threw away the extraction"
    assert int(summary["staging_bytes"]) > 0
    assert summary["staging_path"] == str(destination / STAGING_DIRNAME)


def test_a_second_exports_tree_is_left_alone(tmp_path: Path) -> None:
    """⚠ **SCOPED BY IDENTITY, NEVER BY AGE.** Two exports staged on one drive; importing the
    first must not touch the second, which nothing has asked about."""
    source_a, source_b = tmp_path / "a", tmp_path / "b"
    destination, db = tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(source_a, "takeout-A", 2)
    _archive(source_b, "takeout-B", 2, first=50)
    destination.mkdir()
    preview_a = _unpack_and_preview(source_a, destination, db)
    _unpack_and_preview(source_b, destination, db)
    assert len(_trees(destination)) == 2, "the fixture did not stage two trees"

    service.ingest_run(Path(preview_a["source"]), destination, db)(
        lambda _p: None, threading.Event()
    )

    left = _trees(destination)
    assert len(left) == 1, "importing one export removed another export's extraction"
    assert left[0].name != Path(preview_a["source"]).name


def test_an_ordinary_organize_never_touches_staging(tmp_path: Path) -> None:
    """An organize run is given no tree to own, so it removes none - even one sitting right
    there on the destination it is writing to."""
    destination, db = tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(tmp_path / "src", "takeout-001", 2)
    destination.mkdir()
    _unpack_and_preview(tmp_path / "src", destination, db)
    loose = tmp_path / "Loose"
    loose.mkdir()
    (loose / "a.jpg").write_bytes(_jpeg(99))

    service.organize_run(loose, destination, db)(lambda _p: None, threading.Event())

    assert _trees(destination), "an organize deleted an extraction it was never given"


def test_a_tampered_journal_leaves_the_tree_and_the_run_still_succeeds(tmp_path: Path) -> None:
    """⚠ **A refusal must not turn a successful import into a failed one.** The journal is
    rewritten to name somewhere else; the import still lands every file, and the card reports the
    tree that is still there rather than saying nothing."""
    source, destination, db = tmp_path / "src", tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(source, "takeout-001", 3)
    destination.mkdir()
    preview = _unpack_and_preview(source, destination, db)
    outside = tmp_path / "Photos"
    outside.mkdir()
    (outside / "wedding.jpg").write_bytes(b"\xff\xd8irreplaceable")
    journal = next((destination / STAGING_DIRNAME).glob("*.json"))
    journal.write_text(json.dumps({"staging_root": str(outside), "sources": []}))

    summary = dict(
        service.ingest_run(Path(preview["source"]), destination, db)(
            lambda _p: None, threading.Event()
        )
    )

    assert summary["organized"] == 3, "a tampered journal failed a run that worked"
    assert (outside / "wedding.jpg").exists()
    assert _trees(destination), "the refused record's tree was removed anyway"
    assert int(summary["staging_bytes"]) > 0, "the leftover was not reported"


def test_an_organize_pointed_straight_at_a_staging_tree_still_leaves_it(tmp_path: Path) -> None:
    """⚠ **WRITTEN BECAUSE A MUTATION SURVIVED.** Dropping the `ingest is not None` condition
    changed nothing in any test above: the identity match already fails when an organize's source
    is an ordinary folder. This is the case where it does NOT fail - a user pointing `organize` at
    the staging tree itself, so `source` and `staging_root` are the same path.

    It must still be kept. `(aht)`'s own defence is that **copy mode never deletes a source**, and
    here the tree is the source the user chose rather than one this run unpacked for itself. The
    two conditions are not redundant; one asks *which* tree and the other asks *whose*.
    """
    destination, db = tmp_path / "dest", tmp_path / "c.sqlite"
    _archive(tmp_path / "src", "takeout-001", 2)
    destination.mkdir()
    preview = _unpack_and_preview(tmp_path / "src", destination, db)
    staged = Path(preview["source"])
    assert staged.is_dir(), "the fixture did not stage a tree to point at"

    service.organize_run(staged, destination, db)(lambda _p: None, threading.Event())

    assert staged.is_dir(), "an organize deleted the very folder it was asked to copy from"
