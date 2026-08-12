"""Origin detection: derive an open-ended folder label from a file's own evidence.

Rules run in a fixed priority order and the **first** match wins. The order is
load-bearing:

1. **Screenshot markers** -- first, because a screenshot often *also* carries device
   ``Make``/``Model``, which would otherwise misfile it as a camera photo.
2. **Filename conventions** -- messengers strip metadata on send, so the filename stamp
   is frequently the only durable evidence of origin. Table-driven and extensible.
   **Stands down when the file names the camera that took it** -- see below.
3. **Editing/authoring software** -- a ``Software`` tag that names an application means
   the file came out of that application; the folder is named after it, on the fly.
4. **Capture device** -- genuine camera metadata. Optionally split per device.
5. **Capture filename convention** -- the device's own ``IMG_``/``VID_`` naming, for the files
   rule 4 declined because their ``Make``/``Model`` was blank. Weaker evidence than rule 4 and
   deliberately below it, but still positive evidence of origin rather than the absence of
   evidence to the contrary -- which is all rule 6 has.
6. **Saved** -- origin cannot be proven (metadata-stripped social/web saves, or no evidence):
   anything landing here is a signal that a new rule may be worth adding.

Nothing here enumerates the possible folder names. Rules 2-4 all *derive* labels, so a
library containing Signal, Snapseed or a flatbed scanner grows those folders by itself.

**Why rule 2 defers instead of being moved below rule 4.** A file can arrive through a
messenger and still carry the camera's own record: WhatsApp's *send as document* preserves
EXIF, and truestill already trusts that EXIF enough to take the file's capture date from it.
Filing it by its name anyway meant one chain trusting exactly what the other discarded. The
repair is a stand-down in rule 2 (:func:`capture_device_model`) rather than a reordering,
because **reordering changes every convention at once and this changes only the files that
carry capture evidence**: below rule 4, a messenger filename would also lose to rule 3, which
is unreachable today (`BACKLOG.md` ``(aaq)``) but would, the day ``Software`` is requested,
start claiming messenger files for whichever app last touched them. The screenshot rules stay
ahead of both -- a screenshot carries the phone's ``Make``/``Model`` and is not a photograph
of anything.

**The accepted consequence, which is a behaviour change and not a side effect:** a photo
someone forwards back to you, or that you sent as a document and later re-imported, rejoins
the dated timeline instead of sitting in the messenger bin. It is your photo, with your
camera's evidence on it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from truestill_core.models import (
    SAVED_LABEL,
    CategoryMatch,
    Confidence,
    RuleName,
    strip_component_tail,
)

#: The label both screenshot rules emit.
SCREENSHOT_LABEL = "Screenshots"

#: The label every camera rule emits. Two rules now reach the timeline and both must spell it
#: the same way: a second spelling would not raise anything, it would quietly open a second
#: folder next to the first.
CAMERA_LABEL = "Camera"

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
#:
#: **Deliberately absent: Skype, Slack, iMessage.** Not an oversight and not "not yet" - no
#: convention for them could be stated with confidence, and this table has a second job
#: (`is_messenger_filename` makes the date chain refuse these names), so a guessed pattern costs
#: real photos their real dates. A refusal to guess belongs on the record next to the guesses
#: that were made. Adding one later, once a real file shows the shape, is one line.
NAME_PATTERNS: tuple[NamePattern, ...] = (
    NamePattern(
        "WhatsApp",
        re.compile(r"^(?:IMG|VID|AUD|PTT|DOC|STK)-\d{8}-WA\d+", re.IGNORECASE),
        "-WA<n> stamp",
    ),
    # WhatsApp writes four naming conventions and this table held one, so the date chain read the
    # other three as CAPTURE dates - a send date filed as the day the photo was taken. The ruling
    # in `messenger-dates-research.md` was right; the list it delegates to was short. Measured in
    # `date-resolver-corpus-measurement.md` §3.1.
    #
    # **Neither shape below is evidenced by a file.** Searching both sample corpora and the whole
    # 2,276-file reference library for any messenger-named file returns four, all
    # `IMG-20140817-WA00NN.jpg`. These are documented conventions, not files anyone here has seen,
    # and that is worth stating rather than presenting them as observed.
    NamePattern(
        "WhatsApp",
        re.compile(
            r"^WhatsApp (?:Image|Video|Audio|Document|Animated Gif|Ptt) \d{4}-\d{2}-\d{2} at ",
            re.IGNORECASE,
        ),
        "Desktop/Web save naming",
    ),
    # The least specific entry in this table, kept because its failure direction is the safe one:
    # a false positive costs a file its filename date (`Undated/`, plus this bin), which is a gap
    # a user can see and fix. The false negative it replaces was a WRONG date. The full dashed
    # datetime is what keeps it narrow - a bare `PHOTO-` prefix would not earn its place.
    NamePattern(
        "WhatsApp",
        re.compile(r"^(?:PHOTO|VIDEO|AUDIO)-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", re.IGNORECASE),
        "iOS share-to-Files naming",
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
    # The `E...` alternative needs a **non-hex character** to fire. Without one it claimed any MD5
    # hash beginning with `e` - roughly one hash-named JPEG in sixteen, from browser saves and some
    # cloud exports - and filed the photo under `Twitter/`. Six real files in the sample corpora
    # (`(ade)`, measured 2026-08-12).
    #
    # **The discriminator is the character set, not the case.** `re.IGNORECASE` is what let a
    # lowercase hash match `E`, but tightening to a capital `E` alone would still claim an
    # UPPERCASED hash, which is the same string shouted. A Twitter media id is base64url, so over
    # 15 characters it carries a letter beyond `f` or a `-`/`_` with overwhelming probability; hex,
    # by definition, never can.
    NamePattern(
        "Twitter",
        re.compile(
            r"^(?:twitter_|E(?=[A-Za-z0-9_-]*[g-zG-Z_-])[A-Za-z0-9_-]{12,}\.jpg$)",
            re.IGNORECASE,
        ),
        "name prefix",
    ),
    NamePattern("Line", re.compile(r"^line_\d+", re.IGNORECASE), "name prefix"),
    NamePattern(
        "Downloads",
        re.compile(r"^(?:download|unnamed|image)\s*\(\d+\)", re.IGNORECASE),
        "browser save naming",
    ),
)


@dataclass(frozen=True, slots=True)
class CapturePattern:
    """A filename convention a **capture device** writes for itself."""

    pattern: re.Pattern[str]
    note: str


#: Capture conventions - deliberately **not** :data:`NAME_PATTERNS`, and the separation is the
#: point rather than tidiness. That table has a second job: `is_messenger_filename` uses it to
#: make the date chain **refuse** those names as capture dates, because a messenger stamps when
#: a file was sent. A device's own name stamps when the shutter fired, so an entry added there
#: would silently cost these files their dates - the opposite of what this rule is for.
#:
#: Shaped like the date chain's own patterns (`dates._COMPACT_DATE`): a real century, a real
#: month, a real day, a real time, and no digit may follow. So this claims a file only when the
#: name carries an instant the date chain would also read, rather than on a prefix alone.
CAMERA_NAME_PATTERNS: tuple[CapturePattern, ...] = (
    CapturePattern(
        re.compile(
            r"^(?:IMG|VID)_(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])"
            r"_(?:[01]\d|2[0-3])[0-5]\d[0-5]\d(?!\d)",
            re.IGNORECASE,
        ),
        "Android IMG_/VID_ date-and-time naming",
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


def deterministic_side_bin_labels() -> frozenset[str]:
    """Labels only a **side-bin** rule can produce, whatever the metadata.

    The screenshot rules, the messenger/social conventions and the `Saved` fallback all emit a
    label from a fixed set. The two open-ended rules do not: `software` names a folder after
    whatever an app stamped, and `device` under ``--by-device`` names it after the hardware -
    so a label outside this set could have come from either, and the migration must not guess.
    """
    return frozenset({SCREENSHOT_LABEL, SAVED_LABEL} | {entry.label for entry in NAME_PATTERNS})


def is_messenger_filename(name: str) -> bool:
    """Whether a filename follows a messenger/social convention (`NAME_PATTERNS`).

    Used by the date chain to refuse those filenames as a *capture* date. Every pattern in
    `NAME_PATTERNS` belongs to an app that stamps the moment a file was **sent, received or
    exported**, which is not the moment the photo was taken and is often years later.

    O(len(NAME_PATTERNS)) anchored regex matches - constant in library size.
    """
    return any(entry.pattern.match(name) for entry in NAME_PATTERNS)


def sanitize_label(raw: str, fallback: str = SAVED_LABEL) -> str:
    """Make an arbitrary metadata string safe to use as a directory name.

    The tail is trimmed **after** the length cap, not only before it. Trimming first and
    cutting second is what made this non-idempotent: a 60-character cut landing on a dot kept
    it, and a later pass removed it, so the same camera model yielded two labels. See
    :func:`truestill_core.models.strip_component_tail` for why a trailing dot is a
    cross-platform defect rather than an untidiness.
    """
    cleaned = _UNSAFE_CHARS.sub(" ", raw)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip(" .")
    cleaned = strip_component_tail(cleaned[:_MAX_LABEL_LEN])
    return cleaned or fallback


def _text(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return "" if value is None else str(value).strip()


def capture_device_model(metadata: dict[str, Any]) -> str:
    """The capture device this file names, or ``""`` if it names none.

    **One definition read by two rules**, so "did a camera take this?" cannot be answered two
    ways: `rule_device` needs the value to label the folder, and `rule_filename_convention`
    needs the answer to know whether to stand down (see the module docstring).

    ``Model`` alone counts - video containers routinely carry one with no ``Make``. A ``Make``
    alone does not, and neither does a date, a coordinate or a lens. That is not caution: the
    deferral hands the file to the *rest of the chain*, and `rule_device` is the only rule
    downstream that claims a camera photo. Standing down on evidence it cannot use would drop
    the file past every remaining rule into `Saved` - origin unknown - discarding the camera
    reading and the messenger reading in one move.
    """
    return _text(metadata, "Model") or _text(metadata, "SamsungModel")


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
            label=SCREENSHOT_LABEL,
            reason="EXIF SamsungCaptureInfo=Screenshot",
            confidence=Confidence.HIGH,
            rule=RuleName.SCREENSHOT_METADATA,
        )
    return None


def rule_screenshot_name(path: Path, _metadata: dict[str, Any]) -> CategoryMatch | None:
    """Cross-platform screenshot filename conventions."""
    if _SCREENSHOT_NAME.match(path.name):
        return CategoryMatch(
            label=SCREENSHOT_LABEL,
            reason="filename matches screenshot naming",
            confidence=Confidence.MEDIUM,
            rule=RuleName.SCREENSHOT_NAME,
        )
    return None


def rule_filename_convention(path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
    """Table-driven messenger/app filename conventions, unless the file names its camera.

    The stand-down is the whole reason this rule reads metadata at all; the module docstring
    carries the argument for it.
    """
    if capture_device_model(metadata):
        return None
    for entry in NAME_PATTERNS:
        if entry.pattern.match(path.name):
            return CategoryMatch(
                label=entry.label,
                reason=f"filename matches {entry.label} convention ({entry.note})",
                confidence=Confidence.MEDIUM,
                rule=RuleName.FILENAME_CONVENTION,
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
        rule=RuleName.SOFTWARE,
    )


def make_device_rule(*, by_device: bool) -> Rule:
    """Build the capture-device rule.

    With ``by_device`` the folder is named after the hardware (``Samsung SM-A546B``),
    which is itself discovered from the file. Otherwise all capture devices share a
    single ``Camera`` folder.
    """

    def rule_device(_path: Path, metadata: dict[str, Any]) -> CategoryMatch | None:
        make = _text(metadata, "Make")
        model = capture_device_model(metadata)
        lens = _text(metadata, "LensModel")

        if not model:
            return None
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
            label = sanitize_label(f"{make} {model}".strip(), fallback=CAMERA_LABEL)
        else:
            label = CAMERA_LABEL

        return CategoryMatch(
            label=label,
            reason=f"capture metadata present ({detail})",
            confidence=Confidence.MEDIUM,
            rule=RuleName.DEVICE,
        )

    return rule_device


def rule_camera_filename(path: Path, _metadata: dict[str, Any]) -> CategoryMatch | None:
    """A device's own capture-filename convention, when the device left no tags to read.

    **Runs after the device rule, and only reaches files it declined.** Real ``Make``/``Model``
    is the stronger evidence and stays the stronger evidence; this fills the gap it cannot
    reach. Found on a real library where fifteen ``IMG_`` photos and two ``VID_`` videos carried
    a good ``DateTimeOriginal`` and **empty** ``Make``/``Model``, so nothing downstream could
    claim them and all seventeen fell to ``Saved`` - which in that library was every file it
    held. `(aar)`'s asymmetry in a new place: trusted enough to date from, not to file.

    **Why a convention and not a bare embedded date**, which is the cheaper predicate and the
    wrong one. A film saved from the web carries a ``CreateDate`` too, so "has a timestamp and
    no messenger signal" would sweep downloads into a personal timeline. ``IMG_``/``VID_`` plus
    a full date *and* time is the device's own signature: positive evidence of origin, rather
    than the absence of evidence to the contrary. ``IMG_1234.JPG`` - the iPhone and Canon
    convention - is deliberately **not** claimed: it is a counter, and it carries no evidence
    at all beyond a prefix.
    """
    for entry in CAMERA_NAME_PATTERNS:
        if entry.pattern.match(path.name):
            return CategoryMatch(
                label=CAMERA_LABEL,
                reason=f"filename follows a capture convention ({entry.note})",
                confidence=Confidence.MEDIUM,
                rule=RuleName.CAMERA_FILENAME,
            )
    return None


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
        rule=RuleName.SAVED_HEURISTIC,
    )


def build_rules(*, by_device: bool = False) -> tuple[Rule, ...]:
    """Assemble the ordered rule chain."""
    return (
        rule_screenshot_metadata,
        rule_screenshot_name,
        rule_filename_convention,
        rule_software,
        make_device_rule(by_device=by_device),
        rule_camera_filename,
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
        rule=RuleName.FALLBACK,
    )
