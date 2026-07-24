"""Concurrent hashing scan: size pre-filter + pool equivalence."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaeon.hashing import sha256_file
from vaeon.scan import _needs_sha, compute_hashes


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_unique_size_files_skip_sha(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.bin", b"x" * 10)
    b = _write(tmp_path / "b.bin", b"y" * 20)  # different size -> both unique
    result = compute_hashes([a, b])
    assert result[a].sha256 is None
    assert result[b].sha256 is None


def test_colliding_size_files_get_sha(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.bin", b"hello!")  # same size, different content
    b = _write(tmp_path / "b.bin", b"world!")
    result = compute_hashes([a, b])
    assert result[a].sha256 == sha256_file(a)
    assert result[b].sha256 == sha256_file(b)
    assert result[a].sha256 != result[b].sha256


def test_catalog_size_forces_sha(tmp_path: Path) -> None:
    """A unique in-scan size still gets hashed if the catalog has seen that size."""
    a = _write(tmp_path / "a.bin", b"z" * 15)
    without = compute_hashes([a])
    assert without[a].sha256 is None
    with_catalog = compute_hashes([a], catalog_sizes=frozenset({15}))
    assert with_catalog[a].sha256 == sha256_file(a)


def test_needs_sha_logic() -> None:
    sizes = {Path("a"): 100, Path("b"): 100, Path("c"): 200}
    need = _needs_sha(sizes, catalog_sizes=frozenset())
    assert need == {Path("a"), Path("b")}  # c is unique -> skipped
    need_with_catalog = _needs_sha(sizes, catalog_sizes=frozenset({200}))
    assert Path("c") in need_with_catalog


def test_perceptual_computed_even_for_unique_size_image(gradient_png: Path) -> None:
    result = compute_hashes([gradient_png])
    assert result[gradient_png].sha256 is None  # unique size, not hashed
    assert result[gradient_png].perceptual is not None  # but still perceptually hashed


@pytest.mark.parametrize("pool", ["thread", "process"])
def test_pools_produce_identical_results(tmp_path: Path, pool: str) -> None:
    a = _write(tmp_path / "a.bin", b"dup-content")
    b = _write(tmp_path / "b.bin", b"dup-content")  # identical -> same size, hashed
    result = compute_hashes([a, b], pool=pool, workers=2)  # type: ignore[arg-type]
    assert result[a].sha256 == result[b].sha256 == sha256_file(a)


def test_empty_input() -> None:
    assert compute_hashes([]) == {}
