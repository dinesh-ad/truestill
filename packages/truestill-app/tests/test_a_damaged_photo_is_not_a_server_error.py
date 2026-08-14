"""A photograph whose bytes will not decode answers 422, not 500.

**Measured, not hypothetical: 5 of 4,108 real photographs in the corpus do this.** A JPEG that
stops early raises a plain `OSError` - *"broken data stream when reading image file"*, *"image
file is truncated (31 bytes not processed)"* - which is **not** a subclass of
`UnidentifiedImageError` (verified, not assumed). So it fell past the route's 400/404/415 handlers
and reached the browser as a **500**: one damaged photo in a grid of forty-eight took the tile out
with a server error.

**Why 422 and not 415.** `UnidentifiedImageError` means Pillow could not tell what the file *is*.
This is the opposite: the format is known and supported, and the data is damaged. imgproxy draws
the same line - 422 when a source is reachable but cannot be processed, media-type codes reserved
for media types. 500 would be a lie in the other direction: the server is fine, the photograph is
not.

⚠ **Not salvaged with `ImageFile.LOAD_TRUNCATED_IMAGES`, which is the common remedy.** It would
render the intact prefix, pad the rest, and cache that under the content hash - so a damaged photo
would look fine forever, and the one surface that could tell someone their file is rotting would
be the surface hiding it. This is a custody tool.

The fixtures are **truncated real JPEGs**, built by cutting a valid encode short rather than by
writing junk: a random blob is an unidentifiable format (415) and would exercise the wrong branch.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError
from truestill_app import service
from truestill_core import thumbnails


def _truncated_jpeg(path: Path, keep: float) -> Path:
    """A real JPEG with its tail removed - decodable header, undecodable data."""
    image = Image.new("RGB", (64, 48), "white")
    for x in range(20):
        for y in range(15):
            image.putpixel((x, y), (200, 30, 30))  # content, so the encode is not trivially small
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=95)
    whole = buffer.getvalue()
    path.write_bytes(whole[: int(len(whole) * keep)])
    return path


def test_a_truncated_jpeg_is_not_an_unidentified_image(tmp_path: Path) -> None:
    """The premise, asserted rather than assumed - it is why the 415 branch never caught this.

    If this ever becomes false, the route's existing handler covers the case and this whole file
    is redundant. Asserting it is what makes that discoverable instead of silent.
    """
    broken = _truncated_jpeg(tmp_path / "cut.jpg", keep=0.6)
    with pytest.raises(OSError) as caught, Image.open(broken) as image:  # noqa: PT011
        image.load()
    assert not isinstance(caught.value, UnidentifiedImageError), (
        "a truncated JPEG now raises UnidentifiedImageError, so the route's 415 branch already "
        "handles it and UndecodableImageError is no longer needed"
    )


def test_the_service_reports_a_damaged_photo_as_undecodable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE GUARD, through the function the route actually calls.

    `source_for` is stubbed rather than reimplemented so the wrapping under test is the SERVICE's,
    not the test's. An earlier version of this file caught the OSError and re-raised inside the
    test body, which would have passed with `thumbnail_bytes` doing nothing at all - a guard
    asserting its own copy of the logic.
    """
    broken = _truncated_jpeg(tmp_path / "cut.jpg", keep=0.6)
    monkeypatch.setattr(service.thumbs, "source_for", lambda _sha, _db: broken)

    with pytest.raises(service.UndecodableImageError):
        service.thumbnail_bytes("0" * 64, tmp_path / "catalog.sqlite")


def test_an_intact_photo_still_renders(tmp_path: Path) -> None:
    """Cry-wolf half. A change that made every photo 'damaged' would satisfy the guard above and
    break the product completely."""
    good = tmp_path / "good.jpg"
    Image.new("RGB", (64, 48), "white").save(good, "JPEG")
    data = thumbnails.thumbnail(good, "1" * 64, tmp_path / "cache")
    assert data[:4] == b"RIFF", "an undamaged photo must still produce WebP bytes"
