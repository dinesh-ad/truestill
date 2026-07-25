"""SHA-256 identity and perceptual similarity."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from PIL import Image
from vaeon_core.hashing import (
    MAX_PERCEPTUAL_PIXELS,
    hamming_distance,
    perceptual_hash,
    sha256_file,
)


def test_sha256_is_stable_and_content_based(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"hello world")
    b.write_bytes(b"hello world")
    assert sha256_file(a) == sha256_file(b)

    b.write_bytes(b"different")
    assert sha256_file(a) != sha256_file(b)


def test_perceptual_hash_none_for_non_image(tmp_path: Path) -> None:
    path = tmp_path / "not-an-image.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42 not really a video")
    assert perceptual_hash(path) is None


def test_perceptual_hash_is_hex_for_image(gradient_png: Path) -> None:
    value = perceptual_hash(gradient_png)
    assert value is not None
    int(value, 16)  # parseable as hex
    assert len(value) == 16  # 64-bit dHash


def test_recompressed_image_is_perceptually_close(
    gradient_png: Path,
    gradient_jpeg_recompressed: Path,
) -> None:
    """Different bytes, same picture -> small Hamming distance."""
    png = perceptual_hash(gradient_png)
    jpg = perceptual_hash(gradient_jpeg_recompressed)
    assert png is not None
    assert jpg is not None
    assert sha256_file(gradient_png) != sha256_file(gradient_jpeg_recompressed)
    assert hamming_distance(png, jpg) <= 10


def test_hamming_distance_basics() -> None:
    assert hamming_distance("00", "00") == 0
    assert hamming_distance("00", "01") == 1
    assert hamming_distance("00", "ff") == 8


# -- very large images: deliberate policy, never a raw warning -----------------------------


def test_ceiling_is_deliberately_high_for_real_photography() -> None:
    # 144 MP (the corpus image that tripped Pillow's ~89 MP default) must sit under our ceiling.
    assert MAX_PERCEPTUAL_PIXELS >= 200_000_000


def test_large_image_hashes_without_leaking_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the guard so a tiny image is treated as "large" -- no giant allocation in the test.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    path = tmp_path / "pano.png"
    Image.new("RGB", (12, 12), (9, 40, 80)).save(path)  # 144 px -> warn band (100..200)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any leaked warning fails the test
        result = perceptual_hash(path)
    assert result is not None  # hashed fine; the bomb warning was suppressed inside the call


def test_gigapixel_image_skips_perceptual_but_keeps_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    path = tmp_path / "huge.png"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(path)  # 4096 px > 2x100 -> DecompressionBombError
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert perceptual_hash(path) is None  # perceptual skipped gracefully, no crash/warning
    assert sha256_file(path)  # SHA-256 exact dedup still works
