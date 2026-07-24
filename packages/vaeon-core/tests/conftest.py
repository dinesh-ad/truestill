"""Shared fixtures: small real images so perceptual hashing has something to chew on."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def _gradient(width: int = 64, height: int = 64) -> Image.Image:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (x * 4 % 256, y * 4 % 256, (x + y) * 2 % 256)
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
