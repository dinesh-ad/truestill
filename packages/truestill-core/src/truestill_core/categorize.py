"""Origin detection: derive an open-ended folder label from a file's own evidence.

Rules run in a fixed priority order and the **first** match wins. The order is
load-bearing:

1. **Screenshot markers** -- first, because a screenshot often *also* carries device
   ``Make``/``Model``, which would otherwise misfile it as a camera photo.
2. **Filename conventions** -- messengers strip metadata on send, so the filename stamp
   is frequently the only durable evidence of origin. Table-driven and extensible.
3. **Editing/authoring software** -- a ``Software`` tag that names an application means
   the file came out of that application; the folder is named after it, on the fly.
4. **Capture device** -- genuine camera metadata. Optionally split per device.
5. **Saved** -- origin cannot be proven (metadata-stripped social/web saves, or no evidence):
   anything landing here is a signal that a new rule may be worth adding.

Nothing here enumerates the possible folder names. Rules 2-4 all *derive* labels, so a
library containing Signal, Snapseed or a flatbed scanner grows those folders by itself.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from truestill_core.models import SAVED_LABEL, CategoryMatch, Confidence

# --------------------------------------------------------------------------------------
# Filename convention table
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NamePattern:
    """A filename convention that identifies a file's origin."""

    label: str
    pattern: re.Pattern[str]
    note: str


#: Extensible. Adding an entry here is the whole cost of supporting a new source.
#: Ordered: earlier entries win when two conventions could both match.
NAME_PATTERNS: tuple[NamePattern, ...] = (
    NamePattern(
        "WhatsApp",
        re.compile(r"^(?:IMG|VID|AUD|PTT|DOC|STK)-\d{8}-WA\d+", re.IGNORECASE),
        "-WA<n> stamp",
    ),
    NamePattern(
        "Telegram",
        re.compile(r"^(?:photo|video|audio|file)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", re.I),
        "mobile save-to-gallery naming",
    ),
    NamePattern(
        "Telegram",
        re.compile(r"^(?:photo|video|audio|file)_\d+@\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2}", re.I),
        "Desktop export naming",
    ),
    NamePattern(
        "Signal", re.compile(r"^signal-\d{4}-\d{2}-\d{2}", re.IGNORECASE), "signal- prefix"
    ),
    NamePattern("Instagram", re.compile(r"^(?:instagram|insta)[_-]", re.IGNORECASE), "name prefix"),
    NamePattern("Snapchat", re.compile(r"^snapchat[_-]", re.IGNORECASE), "name prefix"),
    NamePattern(
        "Facebook", re.compile(r"^(?:FB_IMG|FB_VID|received_)", re.IGNORECASE), "FB naming"
    ),
    NamePattern("Messenger", re.compile(r"^messenger_", re.IGNORECASE), "name prefix"),
    NamePattern("Viber", re.compile(r"^viber_", re.IGNORECASE), "name prefix"),
    NamePattern(
        "WeChat", re.compile(r"^(?:mmexport|wx_camera_)\d+", re.IGNORECASE), "WeChat naming"
    ),
    NamePattern("Discord", re.compile(r"^discord_", re.IGNORECASE), "name prefix"),
    NamePattern(
        "Twitter",
        re.compile(r"^(?:twitter_|E[A-Za-z0-9_-]{12,}\.jpg$)", re.IGNORECASE),
        "name prefix",
    ),
    NamePattern("Line", re.compile(r"^line_\d+", re.IGNORECASE), "name prefix"),
    NamePattern(
        "Downloads",
        re.compile(r"^(?:download|unnamed|image)\s*\(\d+\)", re.IGNORECASE),
        "browser save naming",
    ),
)

# "Screenshot_20260721_001427_App.jpg", "Screenshot from 2024-01-01.png", "Screen Shot ..."
_SCREENSHOT_NAME = re.compile(r"^screen[ _-]?shot[ _\-.]", re.IGNORECASE)

# --------------------------------------------------------------------------------------
# Label hygiene
# --------------------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_MAX_LABEL_LEN = 60

#: ``Software`` values that name an operating system rather than an application. These
#: identify nothing useful about origin, so the software rule declines them.
_GENERIC_SOFTWARE = frozenset({"android", "ios", "iphone os", "windows", "picasa uploader"})


def sanitize_label(raw: str, fallback: str = SAVED_LABEL) -> str:
    """Make an arbitrary metadata string safe to use as a directory name."""
    cleaned = _UNSAFE_CHARS.sub(" ", raw)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip(" .")
    cleaned = cleaned[:_MAX_LABEL_LEN].strip()
    return cleaned or fallback


def _text(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return "" if value is None else str(value).strip()


def _software_family(raw: str) -> str:
    """Reduce a ``Software`` string to its application name.

    ``"Adobe Photoshop 24.0 (Windows)"`` -> ``"Adobe Photoshop"``.
    ``"Android BP4A.251205.006.A546BXXSKFZF3"`` -> ``"Android"`` (then declined as generic).

    Leading words are kept until the first token containing a digit, which is where
    version strings and build identifiers reliably begin.
    """
    words: list[str] = []
    for token in raw.split():
        if any(char.isdigit() for char in token):
            break
        words.append(token)
    return " ".join(words).strip("(),-")


# --------------------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------------------

Rule = Callable[[Path, dict[str, Any]], CategoryMatch | None]


def rule_screenshot_metadata(_path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
    """Vendor MakerNotes that state outright that a file is a screen capture."""
    if _text(metadata, "SamsungCaptureInfo").casefold() == "screenshot":
        return CategoryMatch(
            label="Screenshots",
            reason="EXIF SamsungCaptureInfo=Screenshot",
            confidence=Confidence.HIGH,
            rule="screenshot_metadata",
        )
    return None


def rule_screenshot_name(path: Path, _metadata: dict[str, Any]) -> CategoryMatch | None:
    """Cross-platform screenshot filename conventions."""
    if _SCREENSHOT_NAME.match(path.name):
        return CategoryMatch(
            label="Screenshots",
            reason="filename matches screenshot naming",
            confidence=Confidence.MEDIUM,
            rule="screenshot_name",
        )
    return None


def rule_filename_convention(path: Path, _metadata: dict[str, Any]) -> CategoryMatch | None:
    """Table-driven messenger/app filename conventions."""
    for entry in NAME_PATTERNS:
        if entry.pattern.match(path.name):
            return CategoryMatch(
                label=entry.label,
                reason=f"filename matches {entry.label} convention ({entry.note})",
                confidence=Confidence.MEDIUM,
                rule="filename_convention",
            )
    return None


def rule_software(_path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
    """Name a folder after the application that wrote the file.

    This is the main open-ended path: any application that stamps ``Software`` gets its
    own folder without appearing anywhere in this file.
    """
    raw = _text(metadata, "Software")
    if not raw:
        return None

    family = _software_family(raw)
    if not family or family.casefold() in _GENERIC_SOFTWARE:
        return None

    return CategoryMatch(
        label=sanitize_label(family),
        reason=f"Software tag names an application ({raw})",
        confidence=Confidence.LOW,
        rule="software",
    )


def make_device_rule(*, by_device: bool) -> Rule:
    """Build the capture-device rule.

    With ``by_device`` the folder is named after the hardware (``Samsung SM-A546B``),
    which is itself discovered from the file. Otherwise all capture devices share a
    single ``Camera`` folder.
    """

    def rule_device(_path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
        make = _text(metadata, "Make")
        model = _text(metadata, "Model") or _text(metadata, "SamsungModel")
        lens = _text(metadata, "LensModel")

        if not model:
            return None
        # A model with no make is still capture evidence (common in video containers),
        # but a make alone is not.
        detail = ", ".join(
            part
            for part in (
                f"Make={make}" if make else "",
                f"Model={model}",
                f"LensModel={lens}" if lens else "",
            )
            if part
        )

        if by_device:
            label = sanitize_label(f"{make} {model}".strip(), fallback="Camera")
        else:
            label = "Camera"

        return CategoryMatch(
            label=label,
            reason=f"capture metadata present ({detail})",
            confidence=Confidence.MEDIUM,
            rule="device",
        )

    return rule_device


#: Below this pixel count, an image with no camera EXIF is almost certainly a social/web
#: save (platforms downscale to ~1080px wide, well under 2 MP) rather than a lost original.
#: Real phone/camera photos are 12 MP and up.
_SOCIAL_MAX_PIXELS = 2_000_000


def _dimensions(metadata: dict[str, Any]) -> tuple[int, int] | None:
    try:
        width = int(metadata["ImageWidth"])
        height = int(metadata["ImageHeight"])
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def rule_saved_heuristic(_path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
    """Flag a metadata-stripped, low-resolution image as a social/web save.

    Runs after the device rule, so genuine camera photos are already claimed. A small image
    carrying no ``Make``/``Model`` is characteristic of a platform re-upload (Instagram,
    Facebook, a web download) that stripped the EXIF -- not a full-resolution original.
    """
    if _text(metadata, "Make") or _text(metadata, "Model"):
        return None
    dims = _dimensions(metadata)
    if dims is None:
        return None
    width, height = dims
    if width * height > _SOCIAL_MAX_PIXELS:
        return None
    return CategoryMatch(
        label=SAVED_LABEL,
        reason=f"no camera EXIF and low resolution ({width}x{height}) -- likely a social/web save",
        confidence=Confidence.LOW,
        rule="saved_heuristic",
    )


def build_rules(*, by_device: bool = False) -> tuple[Rule, ...]:
    """Assemble the ordered rule chain."""
    return (
        rule_screenshot_metadata,
        rule_screenshot_name,
        rule_filename_convention,
        rule_software,
        make_device_rule(by_device=by_device),
        rule_saved_heuristic,
    )


def categorize(
    path: Path,
    metadata: dict[str, Any],
    rules: tuple[Rule, ...] | None = None,
) -> CategoryMatch:
    """Return the derived folder label and the evidence behind it. First match wins."""
    for rule in rules or build_rules():
        match = rule(path, metadata)
        if match is not None:
            return match

    return CategoryMatch(
        label=SAVED_LABEL,
        reason="no origin evidence in filename, software or device metadata",
        confidence=Confidence.LOW,
        rule="fallback",
    )
