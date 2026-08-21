"""(aeu) HEIF writes a rotation TWICE, and the two consumers each saw only one of them.

**One fact, seen from both ends.** A HEIF file can express a quarter turn as the container
property ``irot`` - which libheif applies while decoding - or as the legacy EXIF ``Orientation``
tag, or as both. Apple writes both. That produced two defects that look unrelated and are not:

| where the rotation lives | pixels (`render`) | payload (`_tile_shape`) |
|---|---|---|
| EXIF only, no `irot` | **was wrong** - fixed by `_pending_heif_orientation` | right |
| `irot` only, EXIF neutral | right - libheif applied it | **wrong** - this file |
| both (Apple) | right | right |

The middle row is `HMD_Nokia_8.3_5G.heif`: `Rotation# = 3`, `Orientation = 1`, stored 4608x3456,
decoded 3456x4608. exiftool reports the **stored** extent, so a payload computed from
``ImageWidth``/``ImageHeight`` plus ``Orientation`` alone calls a portrait photograph landscape.

⚠ **THE TWO SIGNALS ARE REDUNDANT, NEVER ADDITIVE, AND COMPOSING THEM IS THE TRAP.** Measured over
every HEIF/HEIC/AVIF in `metadata-extractor-images`: where both are present they always say the
*same* turn - `Orientation=6` with `Rotation#=3` - so a writer states one rotation twice. Adding
them would turn a 90 into a 180 on exactly the files Apple produces, which is most of them. The
rule is therefore **OR**: the axes swap if either signal is a quarter turn.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from truestill_core.exif import _NUMERIC_TAGS
from truestill_core.hashing import HEIF_AVAILABLE
from truestill_core.thumbnails import upright_size

_EXIFTOOL = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
_HEIF = pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")

#: 200x120 rather than something smaller: the HEIF encoder pads a tiny image out to a 64x64 tile,
#: and exiftool then reports 64x64 as the stored extent - a square, in which a transposition is
#: unobservable. Measured while writing this; 200x120 round-trips faithfully.
_W, _H = 200, 120


def _heif_rotated_in_the_container_only(path: Path) -> None:
    """The `HMD_Nokia_8.3_5G.heif` shape: `irot` present, EXIF orientation neutral.

    Saving *with* an EXIF orientation makes pillow_heif's encoder rotate the pixels and write
    ``irot``; resetting the EXIF tag afterwards leaves the turn recorded only in the container,
    which is what that camera does.
    """
    image = Image.new("RGB", (_W, _H), "white")
    exif = image.getexif()
    exif[274] = 6
    image.save(path, format="HEIF", exif=exif.tobytes())
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-Orientation#=1",
            f"-ExifImageWidth={_W}",
            f"-ExifImageHeight={_H}",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


@_HEIF
@_EXIFTOOL
def test_a_container_rotation_transposes_the_reported_shape(tmp_path: Path) -> None:
    """The payload half of `(aeu)`. A photograph turned by `irot` alone must read as portrait."""
    source = tmp_path / "container-only.heif"
    _heif_rotated_in_the_container_only(source)

    probe = subprocess.run(
        [
            "exiftool",
            "-s3",
            "-Orientation#",
            "-Rotation#",
            "-ImageWidth",
            "-ImageHeight",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    orientation, rotation, width, height = (int(v) for v in probe)
    assert orientation == 1, "PRECONDITION: the EXIF tag must be neutral, or this is the other row"
    assert rotation in {1, 3}, "PRECONDITION: the turn must live in the container"
    assert (width, height) == (_W, _H), "PRECONDITION: exiftool must report the STORED extent"

    assert upright_size(width, height, orientation, container_rotation=rotation) == (_H, _W), (
        "a quarter turn recorded only in the container was ignored, so a portrait photograph is "
        "described as landscape while its thumbnail is drawn portrait"
    )


@pytest.mark.parametrize(
    ("orientation", "rotation", "swapped"),
    [
        (1, None, False),  # no rotation anywhere
        (1, 0, False),  # container says explicitly "no turn"
        (6, None, True),  # EXIF only - the pixels half of (aeu)
        (1, 1, True),  # container only, 90
        (1, 3, True),  # container only, 270 - the Nokia case
        (6, 3, True),  # BOTH, as Apple writes them: still ONE turn, never two
        (1, 2, False),  # container 180: turns the picture, does not swap the axes
        (3, None, False),  # EXIF 180: same
    ],
)
def test_the_two_signals_are_redundant_never_additive(
    orientation: int, rotation: int | None, swapped: bool
) -> None:
    """⚠ The cry-wolf half, and the one that forbids the tempting fix.

    `(6, 3)` is the row that matters: an Apple file states one 90-degree turn in both places.
    Composing them yields 180 and reports a portrait photograph as landscape - so a rule that adds
    the two would break the commonest HEIC there is while looking more thorough.
    """
    expected = (120, 400) if swapped else (400, 120)
    assert upright_size(400, 120, orientation, container_rotation=rotation) == expected


@_EXIFTOOL
def test_the_rotation_tag_is_group_qualified_so_a_maker_note_cannot_impersonate_it() -> None:
    """⚠ `Rotation` is not a unique tag name, and the bare form transposed landscape JPEGs.

    exiftool exposes `[QuickTime] Rotation` - HEIF's `irot`, 0-3 quarter turns - and also
    `[Panasonic] Rotation`, a maker-note tag in an unrelated value space where `1` means
    *"Horizontal (normal)"*. Requesting the bare name collapses the two, so a Panasonic or Leica
    JPEG carrying `Rotation=1` was reported as a quarter turn and its shape came back transposed.

    Found by sampling 300 non-HEIF files after the change - reading the diff would not have shown
    it, because the defect is in a name meaning two things rather than in any line.

    This asserts the *request*, which is the thing that can regress: a future edit that drops the
    group prefix reintroduces the collision, and nothing else here would notice.
    """
    assert "QuickTime:Rotation" in _NUMERIC_TAGS, (
        "the container rotation must be requested group-qualified; the bare `Rotation` also "
        "matches a Panasonic maker-note tag with a different meaning"
    )
    assert "Rotation" not in _NUMERIC_TAGS, "the ambiguous bare name is back"
