"""Progress reporting and cooperative cancellation on the long operations."""

from __future__ import annotations

import threading
from pathlib import Path

from vaeon_core.hashing import sha256_file
from vaeon_core.scan import compute_hashes
from vaeon_core.verify import CopyStatus, CopyToVerify, verify_copies


def _make_files(root: Path, n: int) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        p = root / f"f{i}.bin"
        p.write_bytes(
            f"content-{i}".encode()
        )  # distinct sizes -> unique, but we force hashing below
        paths.append(p)
    return paths


def test_compute_hashes_reports_progress(tmp_path: Path) -> None:
    # identical content -> same size -> all get hashed (size pre-filter includes them)
    paths = []
    (tmp_path).mkdir(exist_ok=True)
    for i in range(6):
        p = tmp_path / f"f{i}.bin"
        p.write_bytes(b"same-size-content")
        paths.append(p)

    seen: list[tuple[int, int]] = []
    compute_hashes(paths, progress=lambda d, t: seen.append((d, t)))
    assert seen  # progress was reported
    assert seen[-1] == (6, 6)  # finished
    assert [d for d, _ in seen] == sorted(d for d, _ in seen)  # monotonic


def test_compute_hashes_cancel_stops_early(tmp_path: Path) -> None:
    paths = _make_files(tmp_path, 8)
    cancel = threading.Event()
    cancel.set()  # already cancelled before the loop starts
    result = compute_hashes(paths, cancel=cancel)
    assert len(result) < len(paths)  # did not process everything


def test_verify_reports_progress_including_missing(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    root.mkdir()
    good = root / "good.bin"
    good.write_bytes(b"ok")
    copies = [
        CopyToVerify("1", "good.bin", sha256_file(good)),
        CopyToVerify("2", "gone.bin", "0" * 64),  # missing
    ]
    seen: list[tuple[int, int]] = []
    results = verify_copies(copies, root, progress=lambda d, t: seen.append((d, t)))
    assert seen[-1] == (2, 2)
    assert {r.status for r in results} == {CopyStatus.VERIFIED, CopyStatus.MISSING}


def test_verify_cancel_stops_early(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    root.mkdir()
    for i in range(6):
        (root / f"f{i}.bin").write_bytes(b"data")
    copies = [CopyToVerify(str(i), f"f{i}.bin", "0" * 64) for i in range(6)]
    cancel = threading.Event()
    cancel.set()
    results = verify_copies(copies, root, cancel=cancel)
    assert len(results) < len(copies)  # stopped before hashing all present files
