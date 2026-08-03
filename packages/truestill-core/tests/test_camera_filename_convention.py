"""A device's own capture-filename convention is evidence of a camera capture.

**Found on a real organize.** `VID_20140817_155317.mp4` and fifteen
`IMG_20140105_181210.jpg` files carried a valid `DateTimeOriginal` - correctly dated, one of
them even UTC-shifted to local - and **empty** `Make`/`Model`, so `rule_device` could not fire
and every one of them fell to `Saved/`. In that library `Saved/` had a **100% false-positive
rate**: all seventeen files in it were Android camera captures.

This is `(aar)`'s asymmetry again, in a new place: trusted enough to *date* from, not trusted
enough to *file*. The predicate is the same shape - "will the device rule fire" - and the
answer here is that it cannot, so the question becomes what other evidence is sufficient.

**A capture-filename convention, not a bare embedded date.** A film saved from the web has a
`CreateDate` too, so "has a timestamp and no messenger signal" would sweep downloaded video
into a personal timeline. `IMG_`/`VID_` plus a full date *and* time is a device's own
signature: positive evidence of origin rather than the mere absence of contrary evidence.

**Its own table, NOT `NAME_PATTERNS`** - which looks like the obvious home and is the wrong
one. That table has a second job: `is_messenger_filename` uses it to **refuse** those filenames
as capture dates, because a messenger stamps when a file was *sent*. An Android name stamps
when the shutter fired. Adding it there would make the date chain reject a perfectly good date.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from truestill_core.categorize import (
    build_rules,
    capture_device_model,
    categorize,
    is_messenger_filename,
)
from truestill_core.dates import resolve_capture_datetime
from truestill_core.models import RuleName


def _label(name: str, **metadata: str) -> str:
    return categorize(Path(name), dict(metadata), build_rules()).label


def _rule(name: str, **metadata: str) -> str:
    return str(categorize(Path(name), dict(metadata), build_rules()).rule)


# --- the defect --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "VID_20140817_155317.mp4",  # the real video, verbatim
        "IMG_20140105_181210.jpg",  # the real photo, verbatim
    ],
)
def test_an_android_capture_name_with_no_device_tags_is_a_camera_capture(name: str) -> None:
    """Empty `Make`/`Model` is what the real files carry - not missing keys, empty strings."""
    assert _label(name, Make="", Model="", DateTimeOriginal="2014:08:17 15:53:17") == "Camera"


def test_a_capture_name_with_no_metadata_at_all_is_still_a_camera_capture() -> None:
    """The filename is the evidence, so it must stand without help from tags."""
    assert _label("VID_20140817_155317.mp4") == "Camera"


def test_the_match_is_attributed_to_its_own_rule() -> None:
    """Provenance: a report must be able to say *why*, and not borrow the device rule's name."""
    assert _rule("IMG_20140105_181210.jpg") == RuleName.CAMERA_FILENAME


# --- real device metadata still wins ---------------------------------------------------------


def test_device_metadata_beats_the_filename() -> None:
    """The stronger evidence must stay stronger; this rule only fills the gap it cannot reach."""
    assert _rule("IMG_20140105_181210.jpg", Make="Canon", Model="Canon IXY 430F") == RuleName.DEVICE


def test_by_device_naming_still_reaches_the_device_rule() -> None:
    """`--by-device` names the folder after the hardware, which needs the device rule to fire."""
    match = categorize(
        Path("IMG_20140105_181210.jpg"),
        {"Make": "samsung", "Model": "SM-A546B"},
        build_rules(by_device=True),
    )
    assert "SM-A546B" in match.label


# --- cry-wolf: the over-claim this predicate exists to avoid ------------------------------------


def test_a_bare_embedded_date_is_not_enough() -> None:
    """The deciding case. A film saved from the web has a `CreateDate` too.

    If this ever returns Camera, the predicate has widened from "the device named this file"
    to "something wrote a timestamp", and downloaded video is in someone's timeline.
    """
    assert _label("holiday-movie.mp4", CreateDate="2014:08:17 15:53:17") != "Camera"


def test_a_messenger_name_is_still_a_messenger_name() -> None:
    """WhatsApp uses hyphens and a WA suffix; it must not be read as a capture convention."""
    assert _label("IMG-20140817-WA0006.jpg") == "WhatsApp"


def test_a_screenshot_still_wins() -> None:
    """Screenshot rules run first and must keep running first."""
    assert _label("Screenshot_20140817_155317.png") != "Camera"


@pytest.mark.parametrize(
    "name",
    [
        "IMG_1234.JPG",  # iPhone/Canon: a counter, no timestamp
        "IMG_20140105.jpg",  # a date but no time - could be a rename
        "VID_2014_08_17_15_53_17.mp4",  # not the convention
        "MYVID_20140817_155317.mp4",  # a prefix that merely contains VID
        "holiday.mp4",
        "DSC_2286.JPG",
    ],
)
def test_names_that_are_not_the_convention_are_not_claimed(name: str) -> None:
    """The pattern is anchored and needs a full date AND time, so a counter cannot pass.

    `IMG_1234.JPG` matters most: it is the iPhone and Canon convention, carries no capture
    information at all, and claiming it would put every unlabelled camera file in the timeline
    on the strength of a prefix.
    """
    assert _label(name) != "Camera"


def test_an_unknown_video_still_lands_in_saved() -> None:
    """The cry-wolf half stated whole: a genuinely unknown origin must stay unknown."""
    assert _label("movie.mp4", CreateDate="2014:08:17 15:53:17") == "Saved"


# --- the date chain must be untouched -----------------------------------------------------------


def test_a_capture_convention_filename_is_not_treated_as_a_messenger_name() -> None:
    """The reason this lives in its own table.

    `is_messenger_filename` drives the date chain's refusal of send-time filenames. An Android
    name records when the shutter fired, so it must NOT be refused - putting the pattern in
    `NAME_PATTERNS` would have silently cost these files their dates.
    """
    assert not is_messenger_filename("IMG_20140105_181210.jpg")
    assert not is_messenger_filename("VID_20140817_155317.mp4")
    assert is_messenger_filename("IMG-20140817-WA0006.jpg")


def test_the_filename_date_still_resolves_for_such_a_file() -> None:
    """End to end: the file keeps its date as well as gaining its category."""
    when, _source, _tag = resolve_capture_datetime(Path("IMG_20140105_181210.jpg"), {}, now=None)
    assert when is not None
    assert when.date().isoformat() == "2014-01-05"


# --- the empty-string question, answered here rather than in a commit message -------------------


@pytest.mark.parametrize(
    "metadata",
    [
        {},  # the tags are absent
        {"Make": "", "Model": ""},  # present and blank - what the seventeen real files carry
        {"Make": None, "Model": None},  # present and null
        {"Make": "   ", "Model": "  "},  # present and whitespace
    ],
    ids=["absent", "blank", "null", "whitespace"],
)
def test_a_blank_device_tag_reads_the_same_as_a_missing_one(metadata: dict[str, object]) -> None:
    """**The mechanism behind the defect, and it is not a bug** - so this rule is additive.

    `Make: ''` rather than absent is what let the seventeen files fall through, which invites
    the theory that the device rule mishandles empty values and that the filename rule is
    compensating for it. It does not. Every rule in the chain reads its tags through one
    function, `_text`, which maps `None` to `""` and strips - so blank, null, whitespace and
    absent are one state at the only place that decides. `capture_device_model` returns `""`
    for all four and `rule_device` declines all four, which is correct: a tag that is present
    and empty asserts nothing about the camera.

    Had this been a bug, the fix would belong in `_text` and this rule would be papering over
    it. Pinned so the answer stays checkable and nobody re-derives it from the same suspicion.
    """
    assert capture_device_model(metadata) == ""
    assert _rule("holiday.jpg", **metadata) != RuleName.DEVICE  # type: ignore[arg-type]


def test_the_one_place_that_decides_is_shared_by_every_rule() -> None:
    """Anti-drift for the test above: the equivalence holds because there is one reader.

    If a rule ever grew its own `metadata.get("Make")`, blank and absent would part company in
    that rule alone and the parametrized test above would still pass, because it only exercises
    the chain's answer. This asserts the structural reason instead.
    """
    source = Path(inspect.getsourcefile(capture_device_model) or "").read_text(encoding="utf-8")
    rules = source.split("# Rules")[-1]
    assert 'metadata.get("Make")' not in rules
    assert 'metadata.get("Model")' not in rules
    assert '_text(metadata, "Make")' in rules  # anti-vacuity: the tags ARE read down there
