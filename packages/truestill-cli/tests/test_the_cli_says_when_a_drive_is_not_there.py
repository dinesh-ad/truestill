"""`where` and `status` must not print the same thing whether or not the drive is connected.

⚠ **MEASURED ON REAL HARDWARE, 2026-09-12: THEY DID.** With a genuine external drive ejected -
`/dev/sda` not even enumerated - both commands produced output **byte-identical** to the connected
run. A photograph whose only copy was on that drive was reported as `only on 'AD_2TB'`, with no
indication that AD_2TB was not there, so the file was in zero reachable places and nothing said so.

`status` also DISCARDED its device verdict in that state: `library_independence` is computed for
both branches and only the healthy one printed it, so the sentence vanished exactly when a file
was at risk.

No hardware is needed to pin this: `drive_reach` reads the marker at a remembered path, so
removing the directory is the same code path a pulled drive takes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from truestill_cli.cli import _cmd_status, _cmd_where
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint
from truestill_core.hashing import sha256_file

_LIBRARY = "11111111-1111-4111-8111-111111111111"
_EXTERNAL = "22222222-2222-4222-8222-222222222222"


def _record(catalog: Catalog, source: Path, root: Path, uuid: str, label: str, body: bytes) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(body)
    copy = root / "Camera" / source.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(body)
    create_marker(root, label, uuid=uuid)
    catalog.upsert_drive(uuid=uuid, label=label)
    catalog.set_setting(drive_path_hint(uuid), str(root))
    catalog.record_uploaded(
        source_path=str(source),
        original_name=source.name,
        sha256=sha256_file(source),
        copy_sha256=sha256_file(source),
        perceptual=None,
        size=len(body),
        captured_at=None,
        category="Camera",
        relative=f"Camera/{source.name}",
        drive_uuid=uuid,
    )


@pytest.fixture
def world(tmp_path: Path) -> tuple[Path, Path]:
    """A library that stays and an external drive that can be taken away, with one file on the
    external drive ALONE - the photograph that reaches zero places once it is unplugged."""
    db = tmp_path / "catalog.sqlite"
    library, external = tmp_path / "Library", tmp_path / "AD_2TB"
    with Catalog(db) as catalog:
        shared = b"\xff\xd8shared"
        _record(catalog, tmp_path / "src/shared.jpg", library, _LIBRARY, "Library", shared)
        _record(catalog, tmp_path / "src/shared2.jpg", external, _EXTERNAL, "AD_2TB", shared)
        _record(catalog, tmp_path / "src/only.jpg", external, _EXTERNAL, "AD_2TB", b"\xff\xd8one")
    return db, external


def _eject(external: Path) -> None:
    for child in sorted(external.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    external.rmdir()


def _where(db: Path, term: str, capsys: pytest.CaptureFixture[str]) -> str:
    _cmd_where(argparse.Namespace(db=db, term=term, limit=None))
    return capsys.readouterr().out


def _status(db: Path, capsys: pytest.CaptureFixture[str]) -> str:
    _cmd_status(argparse.Namespace(db=db))
    return capsys.readouterr().out


def test_where_names_the_drive_it_cannot_reach(
    world: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The command whose own help says "even when unplugged".**"""
    db, external = world

    present = _where(db, "only.jpg", capsys)
    _eject(external)
    absent = _where(db, "only.jpg", capsys)

    assert "only.jpg" in present, "the fixture found nothing, so the difference below is free"
    assert "not connected" not in present
    assert "not connected" in absent
    assert present != absent, "where is byte-identical with the drive gone"


def test_status_names_the_drive_it_cannot_reach(
    world: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    db, external = world

    present = _status(db, capsys)
    _eject(external)
    absent = _status(db, capsys)

    assert "only on 'AD_2TB'" in present, "the fixture lost its single-copy file"
    assert "not connected" not in present
    assert "not connected" in absent
    assert present != absent, "status is byte-identical with the drive gone"


def test_status_keeps_its_device_verdict_on_the_at_risk_branch(
    world: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The sentence that vanished exactly when it was worth most.** `(aiy)` put the device
    verdict on the healthy branch; a library with one at-risk file took the other one and printed
    nothing about devices at all."""
    db, external = world
    _eject(external)

    out = _status(db, capsys)

    assert "At risk:" in out, "the at-risk branch did not fire, so this asserts nothing"
    assert "separate devices" in out, "the device verdict is still discarded when a file is at risk"


def test_a_connected_library_is_not_marked(
    world: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **The anti-vacuity anchor.** Every assertion above passes if the note were unconditional.
    A reachable drive is the unremarkable case and must carry no annotation at all."""
    db, external = world
    _eject(external)

    out = _where(db, "shared.jpg", capsys)

    assert "'Library'" in out
    library_line = next(line for line in out.splitlines() if "'Library'" in line)
    assert "not connected" not in library_line, "a connected drive was annotated"
