"""HEIC/HEIF perceptual hashing via pillow-heif, and recognition of the new extensions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from truestill_core.hashing import HEIF_AVAILABLE, HEIF_EXTENSIONS, perceptual_hash
from truestill_core.organizer import MEDIA_EXTENSIONS, scan_source


def _gradient_heic(path: Path, shift: int = 0) -> None:
    img = Image.new("RGB", (64, 64))
    px = img.load()
    assert px is not None
    for y in range(64):
        for x in range(64):
            px[x, y] = ((x * 4 + shift) % 256, (y * 4) % 256, ((x + y) * 2) % 256)
    img.save(path, format="HEIF")


def test_pillow_heif_is_available() -> None:
    # pillow-heif is a declared dependency, so the opener must register.
    assert HEIF_AVAILABLE is True


def test_heic_perceptual_hash_is_real(tmp_path: Path) -> None:
    a = tmp_path / "a.heic"
    _gradient_heic(a)
    ha = perceptual_hash(a)
    assert ha is not None  # was None before pillow-heif
    assert len(ha) == 16  # 64-bit dHash
    assert set(ha) != {"0"}  # a real gradient hash, not the empty/degenerate one

    # Identical HEIC -> identical hash (exact + perceptual dedup can catch it).
    b = tmp_path / "b.heic"
    _gradient_heic(b)
    assert perceptual_hash(b) == ha

    # A visibly different HEIC -> different hash.
    c = tmp_path / "c.heic"
    _gradient_heic(c, shift=120)
    assert perceptual_hash(c) != ha


def test_new_extensions_are_recognized(tmp_path: Path) -> None:
    # A representative sample of the additions: HEIF variant, JPEG alias, and RAW families.
    for name in ("a.hif", "b.jpe", "c.pef", "d.cr3", "e.x3f", "f.gpr"):
        (tmp_path / name).write_bytes(b"x")
    scan = scan_source(tmp_path)
    assert len(scan.media) == 6
    assert scan.unrecognized == []


def test_heif_extensions_are_a_subset_of_media() -> None:
    assert HEIF_EXTENSIONS <= MEDIA_EXTENSIONS
