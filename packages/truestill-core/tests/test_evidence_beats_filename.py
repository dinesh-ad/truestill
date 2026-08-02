"""A file that carries its camera's own record is a camera photo, however it arrived (`(aar)`).

**The defect, measured on three fixtures in one organize run.** A photo sent through WhatsApp
*as a document* keeps its full EXIF - `Make`, `Model`, GPS and `DateTimeOriginal`. Truestill
dated the copy from that EXIF (`20250801_143000`, `date_source=exif`) and then filed it under
`WhatsApp/` on the strength of its filename. The same metadata dict, read twice in one pass,
was trusted by the date chain and ignored by the categorisation chain.

**What must NOT move, and it is the common case.** WhatsApp strips EXIF on a normal send, so
the compressed copy of the same photo has no capture evidence at all. It belongs in the
messenger bin, and it must stay in `WhatsApp/Undated/` rather than in a folder named for the
day it was sent (R1). Two of the tests here exist only to hold that still.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from truestill_cli.cli import main
from truestill_core.categorize import (
    NAME_PATTERNS,
    build_rules,
    capture_device_model,
    categorize,
    make_device_rule,
)
from truestill_core.models import RuleName

#: The iPhone that took every fixture photo below.
_DEVICE = {"Make": "Apple", "Model": "iPhone 15 Pro", "LensModel": "iPhone 15 Pro back camera"}

#: One filename per entry in `NAME_PATTERNS`, in the same order. The count is asserted, so a
#: pattern added without a sample fails here rather than going quietly unexercised.
_ONE_NAME_PER_PATTERN: tuple[str, ...] = (
    "IMG-20250804-WA0020.jpg",
    "photo_2024-01-15_12-30-45.jpg",
    "photo_1@29-10-2021_09-30-00.jpg",
    "signal-2024-03-02-101112.jpg",
    "instagram_1600000000.jpg",
    "snapchat-1600000000.jpg",
    "FB_IMG_1600000000000.jpg",
    "messenger_1600000000.jpg",
    "viber_image_2024.jpg",
    "mmexport1600000000.jpg",
    "discord_attachment.jpg",
    "twitter_1600000000.jpg",
    "line_1600000000.jpg",
    "download (3).jpg",
)


def test_a_messenger_filename_no_longer_beats_the_camera_that_took_the_photo() -> None:
    """The defect at rule level. Sent as a document, so the EXIF survived the trip."""
    match = categorize(Path("IMG-20250801-WA0001.jpg"), dict(_DEVICE))

    assert match.label == "Camera"
    assert match.rule == RuleName.DEVICE


def test_the_evidence_the_date_chain_trusts_is_the_evidence_the_folder_uses() -> None:
    """The inconsistency stated as a property, not as one example.

    `resolve_capture_datetime` takes `DateTimeOriginal` from this file without hesitating.
    Categorising it by filename anyway is one chain trusting what the other discards.
    """
    metadata = {**_DEVICE, "DateTimeOriginal": "2025:08:01 14:30:00"}

    assert capture_device_model(metadata), "fixture check: this file names its capture device"
    assert categorize(Path("IMG-20250801-WA0001.jpg"), metadata).rule == RuleName.DEVICE


def test_a_stripped_messenger_file_is_still_a_messenger_file() -> None:
    """Cry-wolf half, and the majority case: a normal send leaves nothing to go on."""
    match = categorize(Path("IMG-20250801-WA0002.jpg"), {"ImageWidth": 1024, "ImageHeight": 768})

    assert match.label == "WhatsApp"
    assert match.rule == RuleName.FILENAME_CONVENTION


def test_a_make_with_no_model_does_not_strand_the_file() -> None:
    """The trap in the deferral, and the reason the predicate is `Model` and not `Make`.

    `rule_device` needs a model; a make alone does not satisfy it. Deferring on evidence the
    downstream rule cannot use would drop the file past **every** rule to `Saved` - origin
    unknown - losing the camera reading and the messenger reading in one move.
    """
    match = categorize(Path("IMG-20250801-WA0003.jpg"), {"Make": "Apple"})

    assert match.label == "WhatsApp"
    assert match.rule == RuleName.FILENAME_CONVENTION


@pytest.mark.parametrize("tag", ["DateTimeOriginal", "GPSLatitude", "LensModel"])
def test_a_date_or_a_place_or_a_lens_is_not_a_capture_device(tag: str) -> None:
    """Each of these travels with files no camera produced, and none names a device.

    A messenger re-encode can carry a copied `DateTimeOriginal`; a coordinate says where, not
    what. Deferring on any of them would empty the messenger bin for the wrong reason.
    """
    match = categorize(Path("IMG-20250801-WA0004.jpg"), {tag: "2015:06:15 10:30:00"})

    assert match.label == "WhatsApp"


@pytest.mark.parametrize(
    ("name", "entry"), list(zip(_ONE_NAME_PER_PATTERN, NAME_PATTERNS, strict=True))
)
def test_every_filename_convention_still_fires_without_camera_evidence(
    name: str, entry: Any
) -> None:
    """The whole table, not a sample of it: the deferral must cost nothing when there is
    nothing to defer to."""
    assert categorize(Path(name), {}).label == entry.label


def test_the_sample_table_covers_every_pattern() -> None:
    """Anti-vacuity for the parametrization above."""
    assert len(_ONE_NAME_PER_PATTERN) == len(NAME_PATTERNS)


def test_a_screenshot_carrying_device_tags_is_still_a_screenshot() -> None:
    """The screenshot rules run ahead of both, and that precedence is untouched.

    A Samsung screenshot carries `Make`/`Model` from the phone that drew it. It is not a
    photograph of anything, and neither the filename rule's deferral nor the device rule may
    claim it.
    """
    by_metadata = categorize(
        Path("IMG-20250801-WA0005.jpg"), {**_DEVICE, "SamsungCaptureInfo": "Screenshot"}
    )
    by_name = categorize(Path("Screenshot_20260721_001427_App.jpg"), dict(_DEVICE))

    assert by_metadata.label == "Screenshots"
    assert by_metadata.rule == RuleName.SCREENSHOT_METADATA
    assert by_name.label == "Screenshots"
    assert by_name.rule == RuleName.SCREENSHOT_NAME


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"Make": "Apple"},
        {"Model": "iPhone 15 Pro"},
        {"SamsungModel": "SM-A546B"},
        {"Make": "Apple", "Model": "iPhone 15 Pro"},
        {"DateTimeOriginal": "2025:08:01 14:30:00"},
    ],
)
def test_the_two_rules_read_one_definition_of_capture_evidence(metadata: dict[str, str]) -> None:
    """The twin defect this repo has paid for twice: a repair that reaches one copy.

    `rule_filename_convention` stands down exactly when `rule_device` will claim the file. If
    the two ever disagree there is a metadata shape that no rule claims, and it lands in
    `Saved` with its origin thrown away.
    """
    device_fires = make_device_rule(by_device=False)(Path("x.jpg"), metadata) is not None

    assert bool(capture_device_model(metadata)) == device_fires


# --------------------------------------------------------------------------------------
# End to end: the measurement from `(aar)`, run against real files and real exiftool
# --------------------------------------------------------------------------------------

_HAS_EXIFTOOL = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def _photo(path: Path, *, device: bool, when: str | None) -> None:
    """A JPEG of seeded noise, so no two fixtures are near-duplicates of each other."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (64, 64))
    seed = sum(path.name.encode())
    image.putdata(
        [((seed * i) % 256, (seed * i * 7) % 256, (i * 13) % 256) for i in range(64 * 64)]
    )
    image.save(path, "JPEG")

    args = ["exiftool", "-overwrite_original", "-q", "-m"]
    if device:
        args += [f"-{tag}={value}" for tag, value in _DEVICE.items()]
        args += ["-GPSLatitude=48.8584", "-GPSLatitudeRef=N"]
        args += ["-GPSLongitude=2.2945", "-GPSLongitudeRef=E"]
    if when is not None:
        args.append(f"-DateTimeOriginal={when}")
    if not device and when is None:
        args = ["exiftool", "-overwrite_original", "-q", "-m", "-all="]
    subprocess.run([*args, str(path)], check=True)


@_HAS_EXIFTOOL
def test_the_three_fixture_measurement_end_to_end(tmp_path: Path) -> None:
    """`(aar)`'s measurement, asserted on the paths an organize run actually writes.

    Both halves in one run deliberately: the fix has to move one file and leave the other
    exactly where it was, and a run that only ever sees one of them cannot show that.
    """
    src = tmp_path / "src"
    _photo(src / "IMG_4021.jpg", device=True, when="2025:08:01 15:05:00")
    _photo(src / "IMG-20250801-WA0001.jpg", device=True, when="2025:08:01 14:30:00")
    _photo(src / "IMG-20250801-WA0002.jpg", device=False, when=None)

    out = tmp_path / "out"
    assert (
        main(["organize", str(src), str(out), "--apply", "--db", str(tmp_path / "c.sqlite")]) == 0
    )

    written = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.jpg"))

    assert written == [
        "2025/2025-08/2025-08 - Everyday/20250801_143000_IMG-20250801-WA0001.jpg",
        "2025/2025-08/2025-08 - Everyday/20250801_150500_IMG_4021.jpg",
        "WhatsApp/Undated/IMG-20250801-WA0002.jpg",
    ]


@_HAS_EXIFTOOL
def test_the_rejoining_file_keeps_the_date_it_always_had(tmp_path: Path) -> None:
    """Placement changed; dating did not. The stamp is the same one the side-binned copy got.

    Worth pinning separately: the date chain still refuses the `-WA` filename as a capture
    date (R1) and still reads the EXIF. Nothing about this fix touches that, and a future
    reader should be able to see that it did not.
    """
    src = tmp_path / "src"
    _photo(src / "IMG-20250801-WA0001.jpg", device=True, when="2025:08:01 14:30:00")

    out = tmp_path / "out"
    assert (
        main(["organize", str(src), str(out), "--apply", "--db", str(tmp_path / "c.sqlite")]) == 0
    )

    written = [p.name for p in out.rglob("*.jpg")]

    assert written == ["20250801_143000_IMG-20250801-WA0001.jpg"]


def test_the_rule_chain_is_the_one_these_tests_reason_about() -> None:
    """Anti-vacuity: every assertion above depends on where the filename rule sits.

    If the chain were reordered instead, these tests would still pass while the reasoning in
    `categorize.py` described something else. The positions are the subject, so they are pinned.
    """
    names = [getattr(rule, "__name__", "rule_device") for rule in build_rules()]

    assert names == [
        "rule_screenshot_metadata",
        "rule_screenshot_name",
        "rule_filename_convention",
        "rule_software",
        "rule_device",
        "rule_saved_heuristic",
    ]
