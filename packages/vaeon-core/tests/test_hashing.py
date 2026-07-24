"""SHA-256 identity and perceptual similarity."""

from __future__ import annotations

from pathlib import Path

from vaeon_core.hashing import hamming_distance, perceptual_hash, sha256_file


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
