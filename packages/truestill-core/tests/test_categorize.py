"""Rules must be data-driven: new sources create new folders without code changes."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.categorize import build_rules, categorize, sanitize_label
from truestill_core.models import SAVED_LABEL, Confidence


def test_screenshot_metadata_beats_camera_exif() -> None:
    """A screenshot carrying device tags must not be filed as a camera photo."""
    match = categorize(
        Path("IMG_0001.jpg"),
        {"SamsungCaptureInfo": "Screenshot", "Make": "samsung", "Model": "SM-A546B"},
    )
    assert match.label == "Screenshots"
    assert match.confidence is Confidence.HIGH


def test_screenshot_filename_fallback() -> None:
    match = categorize(Path("Screenshot_20260721_001427_EDF & MOI.jpg"), {})
    assert match.label == "Screenshots"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("IMG-20250804-WA0020.jpg", "WhatsApp"),
        ("VID-20250804-WA0020.mp4", "WhatsApp"),
        ("PTT-20250804-WA0001.opus", "WhatsApp"),
        ("photo_2024-01-15_12-30-45.jpg", "Telegram"),
        ("photo_1@29-10-2021_09-30-00.jpg", "Telegram"),
        ("signal-2024-03-02-101112.jpg", "Signal"),
        ("FB_IMG_1600000000000.jpg", "Facebook"),
    ],
)
def test_filename_conventions(filename: str, expected: str) -> None:
    assert categorize(Path(filename), {}).label == expected


def test_camera_exif_wins_over_whatsapp_naming() -> None:
    """**Reversed 2026-08-02** (`BACKLOG.md` ``(aar)``). It read *"messenger naming is stronger
    evidence of origin than surviving device tags"*, and that premise did not survive contact
    with a measurement: the same file's EXIF was already being trusted to supply its capture
    *date*, so calling it untrustworthy for *origin* was one chain contradicting the other.
    Surviving device tags are the camera's own record of taking the picture; a filename records
    how a copy travelled afterwards.

    The behaviour this test used to hold is not gone, it is narrowed - see
    `test_evidence_beats_filename.py`, where the stripped case (the common one) is pinned in
    place alongside all fourteen conventions.
    """
    match = categorize(
        Path("VID-20250804-WA0020.mp4"),
        {"Make": "samsung", "Model": "SM-A546B"},
    )
    assert match.label == "Camera"


def test_unknown_software_creates_its_own_label() -> None:
    """The open-ended path: an app we have never heard of gets its own folder."""
    match = categorize(Path("edit.jpg"), {"Software": "Snapseed 2.19.1.303051424"})
    assert match.label == "Snapseed"
    assert match.rule == "software"


def test_generic_os_software_is_declined() -> None:
    """'Android <build id>' identifies an OS, not an origin, so it must not become a folder."""
    match = categorize(
        Path("random.jpg"),
        {"Software": "Android BP4A.251205.006.A546BXXSKFZF3"},
    )
    assert match.label != "Android"


def test_camera_label_default_and_by_device() -> None:
    meta = {"Make": "samsung", "Model": "SM-A546B", "LensModel": "wide"}

    default = categorize(Path("x.jpg"), meta, build_rules(by_device=False))
    assert default.label == "Camera"

    per_device = categorize(Path("x.jpg"), meta, build_rules(by_device=True))
    assert per_device.label == "samsung SM-A546B"


def test_no_evidence_falls_through_to_saved() -> None:
    match = categorize(Path("mystery.jpg"), {})
    assert match.label == SAVED_LABEL
    assert match.rule == "fallback"


def test_low_res_no_exif_is_flagged_as_social_save() -> None:
    """A small image with no camera EXIF is a likely social/web save, not a lost original."""
    match = categorize(Path("received.jpg"), {"ImageWidth": 1080, "ImageHeight": 1080})
    assert match.label == SAVED_LABEL
    assert match.rule == "saved_heuristic"


def test_full_res_no_exif_is_not_forced_to_saved_by_heuristic() -> None:
    """A high-resolution image without Make/Model should not be assumed a social save."""
    match = categorize(Path("big.jpg"), {"ImageWidth": 4000, "ImageHeight": 3000})
    assert match.rule != "saved_heuristic"


def test_camera_exif_beats_saved_heuristic() -> None:
    """Even if small, a file with real camera EXIF is Camera, not a social save."""
    match = categorize(
        Path("tiny_cam.jpg"),
        {"Make": "samsung", "Model": "SM-A546B", "ImageWidth": 800, "ImageHeight": 600},
    )
    assert match.label == "Camera"


def test_sanitize_label_strips_path_separators() -> None:
    assert "/" not in sanitize_label("Adobe/Photoshop")
    assert sanitize_label("   ") == SAVED_LABEL
    assert len(sanitize_label("x" * 200)) <= 60


# --- (ade): the Twitter convention must not claim a hex hash ------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "e6d9eca2c7405e13cfb850b7d0ef7476.jpg",  # all six of these are real corpus files
        "ef1f8a057bb6056674fad92f6b8c0acd.jpg",
        "e18bb52107598f65b81b02be2c6c5124.jpg",
        "E6D9ECA2C7405E13CFB850B7D0EF7476.jpg",  # uppercase hex - the same string, shouted
        "eedcba9876543210fedcba9876543210.jpg",
    ],
)
def test_an_md5_named_jpeg_is_not_a_twitter_file(name: str) -> None:
    """`(ade)`. `^(?:twitter_|E[A-Za-z0-9_-]{12,}\\.jpg$)` is compiled `re.IGNORECASE`, so its `E`
    alternative claimed **any hex hash beginning with `e`** - one JPEG in sixteen from any
    hash-named source (browser saves, some cloud exports). Six real files in the sample corpora.

    It costs no date, since such names carry none; it files someone's photo under `Twitter/`.
    """
    assert categorize(Path(name), {}).label != "Twitter"


@pytest.mark.parametrize(
    "name",
    [
        "EqZbFmXXsAAy-Lc.jpg",  # the real shape: base64url, mixed case, and a '-'
        "E_lRz9RXsAIq7Ru.jpg",
        "EtGjKlMnOpQrStU.jpg",
        "Ezzzzzzzzzzzzzz.jpg",
    ],
)
def test_a_real_twitter_media_id_is_still_claimed(name: str) -> None:
    """CRY-WOLF HALF. Twitter media ids are base64url, so they carry letters beyond `f` or a
    `-`/`_` - characters hex cannot produce. That is the discriminator, rather than case, because
    an uppercased hash is still a hash.
    """
    assert categorize(Path(name), {}).label == "Twitter"
