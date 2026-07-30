"""Golden matrix for ``organizer.execute`` - the behaviour pin before any Extract Method.

Captured against the pre-extract ``execute()`` loop: for each fixture case, the ActionResult
sequence, destination tree, catalog ``files`` rows, and (where applicable) ``inplace_moves``
journal entries. Expected values are hand-authored from that capture, not dumped from the
code under test - same discipline as ``GOLDEN_PLACEMENTS`` / the Event value-object matrix.

Cases already covered elsewhere (asserted loosely) are re-pinned here as a single equality
harness. **Cancel mid-run had no execute coverage** before this file; that is the new risk.
"""

from __future__ import annotations

import errno
import shutil
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.exif import read_metadata
from truestill_core.hashing import sha256_file
from truestill_core.models import (
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import Relocation, execute
from truestill_core.progress import Progress
from truestill_core.takeout import IngestContext, MetadataWrite

WHEN = datetime(2023, 1, 1, 12, 30)
BAKE_WHEN = datetime(2019, 4, 3, 8, 15)
CAT = CategoryMatch(label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device")

#: Fixed matched_path strings so ActionResult.detail does not embed a machine-local tmp path.
FIXTURE_A = "/fixture/a.jpg"
FIXTURE_ORIG = "/fixture/orig.jpg"

# --- hand-authored goldens (pre-extract capture, 2026-07-30) ------------------------------

GOLDEN_EXACT_RESULTS = (
    ("uploaded", "Camera/2023/01/a.jpg", "", "a.jpg"),
    ("duplicate", None, f"exact match of {FIXTURE_A} [run]", "b.jpg"),
)
GOLDEN_EXACT_TREE = ("Camera/2023/01/a.jpg",)
GOLDEN_EXACT_SHA = "d0a4ae3e45346aec7218029b480d548d63288d4d86298f268c0f5535f02bb419"
GOLDEN_EXACT_FILES = (
    ("a.jpg", GOLDEN_EXACT_SHA, GOLDEN_EXACT_SHA, "Camera/2023/01/a.jpg", "uploaded", "Camera"),
)

GOLDEN_NEAR_RESULTS = (
    ("uploaded", "Camera/2023/01/orig.jpg", "", "orig.jpg"),
    (
        "uploaded",
        "Camera/2023/01/near.jpg",
        f"near-duplicate of {FIXTURE_ORIG} [run, distance=2]",
        "near.jpg",
    ),
)
GOLDEN_NEAR_TREE = ("Camera/2023/01/near.jpg", "Camera/2023/01/orig.jpg")
GOLDEN_NEAR_ORIG_SHA = "60e5fa083eb0c0dc29000ccf83cd481df0f2dd738b1dffe937996bb38ec20002"
GOLDEN_NEAR_NEAR_SHA = "802ffe8e6e5897d22a77dff9dbe06adc78e088dfdcf54850ef1cd83c9f953008"
GOLDEN_NEAR_FILES = (
    (
        "near.jpg",
        GOLDEN_NEAR_NEAR_SHA,
        GOLDEN_NEAR_NEAR_SHA,
        "Camera/2023/01/near.jpg",
        "uploaded",
        "Camera",
    ),
    (
        "orig.jpg",
        GOLDEN_NEAR_ORIG_SHA,
        GOLDEN_NEAR_ORIG_SHA,
        "Camera/2023/01/orig.jpg",
        "uploaded",
        "Camera",
    ),
)

GOLDEN_UNDATED_RESULTS = (
    ("uploaded", "Camera/2023/01/dated.jpg", "", "dated.jpg"),
    ("skipped_undated", None, "no capture date; skipped (--skip-undated)", "undated.jpg"),
)
GOLDEN_UNDATED_TREE = ("Camera/2023/01/dated.jpg",)
GOLDEN_UNDATED_SHA = "32702dab908d494e7a2df28428f12178e02774c4d857eee8b1899dd697d2cba6"
GOLDEN_UNDATED_FILES = (
    (
        "dated.jpg",
        GOLDEN_UNDATED_SHA,
        GOLDEN_UNDATED_SHA,
        "Camera/2023/01/dated.jpg",
        "uploaded",
        "Camera",
    ),
)

GOLDEN_DRY_RESULTS = (("planned", "Camera/2023/01/photo.jpg", "", "photo.jpg"),)
GOLDEN_DRY_TREE: tuple[str, ...] = ()
GOLDEN_DRY_FILES: tuple[tuple[str, ...], ...] = ()

GOLDEN_INPLACE_RESULTS = (
    (
        "moved_in_place",
        "Camera/2023/01/photo.jpg",
        "moved on the drive (no bytes copied)",
        "photo.jpg",
    ),
)
GOLDEN_INPLACE_TREE = ("Camera/2023/01/photo.jpg",)
GOLDEN_INPLACE_SHA = "87aebc08a4ffda73c57104e87acc8e50ff2c04f67de1270dca81512db51a7834"
GOLDEN_INPLACE_FILES = (
    (
        "photo.jpg",
        GOLDEN_INPLACE_SHA,
        GOLDEN_INPLACE_SHA,
        "Camera/2023/01/photo.jpg",
        "uploaded",
        "Camera",
    ),
)
GOLDEN_INPLACE_JOURNAL = ((GOLDEN_INPLACE_SHA, "incoming/photo.jpg", "Camera/2023/01/photo.jpg"),)

GOLDEN_XDEV_RESULTS = (
    ("moved", "Camera/2023/01/photo.jpg", "source removed (copy verified)", "photo.jpg"),
)
GOLDEN_XDEV_TREE = ("Camera/2023/01/photo.jpg",)
GOLDEN_XDEV_SHA = "60863ced8e981e92e28b24a60a9579304cc610a4aad387dc80d8dfcb0d75cd43"
GOLDEN_XDEV_FILES = (
    (
        "photo.jpg",
        GOLDEN_XDEV_SHA,
        GOLDEN_XDEV_SHA,
        "Camera/2023/01/photo.jpg",
        "uploaded",
        "Camera",
    ),
)
GOLDEN_XDEV_JOURNAL: tuple[tuple[str, str, str], ...] = ()

GOLDEN_CANCEL_RESULTS = (("uploaded", "Camera/2023/01/f0.jpg", "", "f0.jpg"),)
GOLDEN_CANCEL_TREE = ("Camera/2023/01/f0.jpg",)
GOLDEN_CANCEL_SHA = "d11ffa1ecfe590c4dd68ceea7c20e4a63b707555e1d02af83647c5fbbf4e3970"
GOLDEN_CANCEL_FILES = (
    (
        "f0.jpg",
        GOLDEN_CANCEL_SHA,
        GOLDEN_CANCEL_SHA,
        "Camera/2023/01/f0.jpg",
        "uploaded",
        "Camera",
    ),
)

GOLDEN_BAKE_RESULTS = (("uploaded", "Camera/2019/04/IMG_0000.jpg", "", "IMG_0000.jpg"),)
GOLDEN_BAKE_TREE = ("Camera/2019/04/IMG_0000.jpg",)
GOLDEN_BAKE_SOURCE_SHA = "f1a60c672fe3e9fe8841ebfcf020a6298bc0156f6ca11662b28ef87776a73312"
GOLDEN_BAKE_COPY_SHA = "2f6c4c69e5a5c3cc05d6c058c26c3bd512e47e912a6b4c57b7bb827af8f58fdc"
GOLDEN_BAKE_FILES = (
    (
        "IMG_0000.jpg",
        GOLDEN_BAKE_SOURCE_SHA,
        GOLDEN_BAKE_COPY_SHA,
        "Camera/2019/04/IMG_0000.jpg",
        "uploaded",
        "Camera",
    ),
)
GOLDEN_BAKE_DTO = "2019:04:03 08:15:00"


def _resolution(
    source: Path,
    relative: str,
    *,
    sha: str | None = None,
    captured: datetime | None = WHEN,
    exact: DuplicateMatch | None = None,
    near: DuplicateMatch | None = None,
) -> Resolution:
    decision = Decision(
        source=source,
        category=CAT,
        captured_at=captured,
        date_source=DateSource.EXIF if captured is not None else DateSource.NONE,
        date_tag="DateTimeOriginal" if captured is not None else None,
        relative=Path(relative),
    )
    return Resolution(
        decision,
        FileHashes(sha if sha is not None else sha256_file(source), None),
        exact,
        near,
    )


def _snap_results(results: list) -> tuple[tuple[str, str | None, str, str], ...]:
    return tuple(
        (
            r.status.value,
            None if r.final_relative is None else r.final_relative.as_posix(),
            r.detail or "",
            r.resolution.decision.source.name,
        )
        for r in results
    )


def _snap_tree(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()))


def _snap_files(catalog: Catalog) -> tuple[tuple[str, ...], ...]:
    rows = catalog._conn.execute(
        "SELECT original_name, sha256, copy_sha256, relative, upload_status, category "
        "FROM files ORDER BY original_name"
    ).fetchall()
    return tuple(tuple(str(c) if c is not None else "" for c in row) for row in rows)


def _snap_journal(catalog: Catalog, run_id: str) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (str(r["sha256"]), str(r["old_relative"]), str(r["new_relative"]))
        for r in catalog.inplace_moves(run_id)
    )


def test_matrix_exact_duplicate(tmp_path: Path) -> None:
    """Already covered loosely in test_organizer; pinned here as full outcome equality."""
    src = tmp_path / "src"
    src.mkdir()
    a = src / "a.jpg"
    b = src / "b.jpg"
    a.write_bytes(b"same-bytes-exact")
    b.write_bytes(b"same-bytes-exact")
    assert sha256_file(a) == GOLDEN_EXACT_SHA
    r1 = _resolution(a, "Camera/2023/01/a.jpg", sha=GOLDEN_EXACT_SHA)
    r2 = _resolution(
        b,
        "Camera/2023/01/b.jpg",
        sha=GOLDEN_EXACT_SHA,
        exact=DuplicateMatch(DuplicateKind.EXACT, matched_path=FIXTURE_A, origin="run"),
    )
    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute([r1, r2], LocalDestination(out), catalog, apply=True)
        assert _snap_results(results) == GOLDEN_EXACT_RESULTS
        assert _snap_tree(out) == GOLDEN_EXACT_TREE
        assert _snap_files(catalog) == GOLDEN_EXACT_FILES
        assert _snap_journal(catalog, "unused") == ()


def test_matrix_near_duplicate(tmp_path: Path) -> None:
    """Already covered loosely; pin status + near-dup detail + both files on disk and in catalog."""
    src = tmp_path / "src"
    src.mkdir()
    orig = src / "orig.jpg"
    near = src / "near.jpg"
    orig.write_bytes(b"original-near-AAAA")
    near.write_bytes(b"near-dup-bytes-BBBB")
    assert sha256_file(orig) == GOLDEN_NEAR_ORIG_SHA
    assert sha256_file(near) == GOLDEN_NEAR_NEAR_SHA
    r1 = _resolution(orig, "Camera/2023/01/orig.jpg", sha=GOLDEN_NEAR_ORIG_SHA)
    r2 = _resolution(
        near,
        "Camera/2023/01/near.jpg",
        sha=GOLDEN_NEAR_NEAR_SHA,
        near=DuplicateMatch(
            DuplicateKind.PERCEPTUAL, matched_path=FIXTURE_ORIG, origin="run", distance=2
        ),
    )
    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute([r1, r2], LocalDestination(out), catalog, apply=True)
        assert _snap_results(results) == GOLDEN_NEAR_RESULTS
        assert _snap_tree(out) == GOLDEN_NEAR_TREE
        assert _snap_files(catalog) == GOLDEN_NEAR_FILES


def test_matrix_undated_skip(tmp_path: Path) -> None:
    """Already covered; pin SKIPPED_UNDATED detail and that undated never reaches catalog/disk."""
    src = tmp_path / "src"
    src.mkdir()
    dated = src / "dated.jpg"
    undated = src / "undated.jpg"
    dated.write_bytes(b"dated-content")
    undated.write_bytes(b"undated-content")
    assert sha256_file(dated) == GOLDEN_UNDATED_SHA
    rd = _resolution(dated, "Camera/2023/01/dated.jpg", sha=GOLDEN_UNDATED_SHA)
    ru = _resolution(undated, "Undated/undated.jpg", captured=None)
    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute([rd, ru], LocalDestination(out), catalog, apply=True, skip_undated=True)
        assert _snap_results(results) == GOLDEN_UNDATED_RESULTS
        assert _snap_tree(out) == GOLDEN_UNDATED_TREE
        assert _snap_files(catalog) == GOLDEN_UNDATED_FILES


def test_matrix_dry_run(tmp_path: Path) -> None:
    """Already covered; pin PLANNED + empty tree + empty catalog."""
    src = tmp_path / "src"
    src.mkdir()
    photo = src / "photo.jpg"
    photo.write_bytes(b"dry-run-bytes")
    rp = _resolution(photo, "Camera/2023/01/photo.jpg")
    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute([rp], LocalDestination(out), catalog, apply=False)
        assert _snap_results(results) == GOLDEN_DRY_RESULTS
        assert _snap_tree(out) == GOLDEN_DRY_TREE
        assert _snap_files(catalog) == GOLDEN_DRY_FILES


def test_matrix_inplace_rename(tmp_path: Path) -> None:
    """Already covered; pin MOVED_IN_PLACE + journal row + catalog + vacated source."""
    root = tmp_path / "drive"
    source = root / "incoming" / "photo.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"inplace-bytes")
    assert sha256_file(source) == GOLDEN_INPLACE_SHA
    rp = _resolution(source, "Camera/2023/01/photo.jpg", sha=GOLDEN_INPLACE_SHA)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.start_inplace_run(
            run_id="run-1", source_root=str(root), dest_root=str(root), drive_uuid="D1"
        )
        results = execute(
            [rp],
            LocalDestination(root),
            catalog,
            apply=True,
            relocation=Relocation(run_id="run-1", source_root=root, dest_root=root),
            drive_uuid="D1",
        )
        assert _snap_results(results) == GOLDEN_INPLACE_RESULTS
        assert _snap_tree(root) == GOLDEN_INPLACE_TREE
        assert _snap_files(catalog) == GOLDEN_INPLACE_FILES
        assert _snap_journal(catalog, "run-1") == GOLDEN_INPLACE_JOURNAL
        assert not source.exists()


def test_matrix_cross_device_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Already covered; pin MOVED (verified copy path), empty journal, source removed."""
    root = tmp_path / "drive"
    source = root / "incoming" / "photo.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"xdev-bytes")
    assert sha256_file(source) == GOLDEN_XDEV_SHA
    rp = _resolution(source, "Camera/2023/01/photo.jpg", sha=GOLDEN_XDEV_SHA)

    def _refuse(*_args: object) -> Path:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(Path, "rename", _refuse)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.start_inplace_run(
            run_id="run-x", source_root=str(root), dest_root=str(root), drive_uuid="D1"
        )
        results = execute(
            [rp],
            LocalDestination(root),
            catalog,
            apply=True,
            move=True,
            relocation=Relocation(run_id="run-x", source_root=root, dest_root=root),
            drive_uuid="D1",
        )
        assert _snap_results(results) == GOLDEN_XDEV_RESULTS
        assert _snap_tree(root) == GOLDEN_XDEV_TREE
        assert _snap_files(catalog) == GOLDEN_XDEV_FILES
        assert _snap_journal(catalog, "run-x") == GOLDEN_XDEV_JOURNAL
        assert not source.exists()


def test_matrix_cancel_mid_run(tmp_path: Path) -> None:
    """NEW: execute cancel was untested. One file lands; the rest are never started."""
    src = tmp_path / "src"
    src.mkdir()
    resolutions = []
    for i in range(3):
        path = src / f"f{i}.jpg"
        path.write_bytes(f"cancel-{i}".encode())
        resolutions.append(_resolution(path, f"Camera/2023/01/f{i}.jpg"))
    assert sha256_file(src / "f0.jpg") == GOLDEN_CANCEL_SHA

    cancel = threading.Event()

    def on_progress(progress: Progress) -> None:
        if progress.done >= 1:
            cancel.set()

    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute(
            resolutions,
            LocalDestination(out),
            catalog,
            apply=True,
            progress=on_progress,
            cancel=cancel,
        )
        assert _snap_results(results) == GOLDEN_CANCEL_RESULTS
        assert _snap_tree(out) == GOLDEN_CANCEL_TREE
        assert _snap_files(catalog) == GOLDEN_CANCEL_FILES
        assert len(results) == 1


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_matrix_takeout_bake(tmp_path: Path) -> None:
    """Already covered; pin UPLOADED + baked DTO + copy_sha256 != source sha256."""
    src = tmp_path / "src"
    src.mkdir()
    photo = src / "IMG_0000.jpg"
    Image.new("RGB", (48, 32), (10, 40, 90)).save(photo, "JPEG")
    assert sha256_file(photo) == GOLDEN_BAKE_SOURCE_SHA
    rp = Resolution(
        Decision(
            source=photo,
            category=CAT,
            captured_at=BAKE_WHEN,
            date_source=DateSource.TAKEOUT,
            date_tag="photoTakenTime",
            relative=Path(f"Camera/{BAKE_WHEN:%Y}/{BAKE_WHEN:%m}/{photo.name}"),
        ),
        FileHashes(GOLDEN_BAKE_SOURCE_SHA, None),
        None,
        None,
    )
    ingest = IngestContext(
        writes={
            str(photo): MetadataWrite(
                taken_at_local=BAKE_WHEN, gps=None, description="from a sidecar"
            )
        }
    )
    out = tmp_path / "out"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        results = execute([rp], LocalDestination(out), catalog, apply=True, ingest=ingest)
        assert _snap_results(results) == GOLDEN_BAKE_RESULTS
        assert _snap_tree(out) == GOLDEN_BAKE_TREE
        assert _snap_files(catalog) == GOLDEN_BAKE_FILES
        copies = list(out.rglob("*.jpg"))
        assert len(copies) == 1
        assert read_metadata(copies)[copies[0]]["DateTimeOriginal"] == GOLDEN_BAKE_DTO
        assert GOLDEN_BAKE_SOURCE_SHA != GOLDEN_BAKE_COPY_SHA
