"""Shared fixtures: small real images so perceptual hashing has something to chew on."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def _gradient(width: int = 64, height: int = 64) -> Image.Image:
    """A picture with structure, not a ramp.

    ⚠ **This was a monotonic left-to-right ramp until `(ahq)`** - `x * 4 % 256` - so every pixel
    exceeded its left neighbour and dHash returned `ffffffffffffffff`, the all-one pole. The
    fixture the repo used to demonstrate *"the perceptual-duplicate case the near-dup tier exists
    to catch"* **carried no distinguishing signal at all**, and paired only because two copies of
    nothing are equal. The checkerboard breaks the monotonicity so adjacent comparisons differ;
    the re-encode still pairs, which is what the tier is for.
    """
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for x in range(width):
        for y in range(height):
            block = 96 if (x // 8 + y // 8) % 2 else 0
            pixels[x, y] = ((x * 4 + block) % 256, y * 4 % 256, (x + y) * 2 % 256)
    return image


@pytest.fixture
def gradient_png(tmp_path: Path) -> Path:
    path = tmp_path / "gradient.png"
    _gradient().save(path, "PNG")
    return path


@pytest.fixture
def gradient_jpeg_recompressed(tmp_path: Path) -> Path:
    """The same picture as ``gradient_png``, re-encoded as low-quality JPEG.

    Different bytes (so a different SHA-256) but the same image -- the perceptual-duplicate
    case the near-dup tier exists to catch.
    """
    path = tmp_path / "gradient_q30.jpg"
    _gradient().save(path, "JPEG", quality=30)
    return path
