"""Path-component safety for names a user typed.

An event name became a directory when folders became human-readable, which moves it from a
display string to something ext4, APFS and NTFS all have to accept. Each constraint below is
one a real filesystem (or truestill itself) imposes; the rationale is in
`docs/filename-safety-research.md`.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

import pytest
from truestill_core.layout import (
    MAX_COMPONENT_BYTES,
    EventNaming,
    LayoutTemplate,
    RenderContext,
    disambiguate_event_folders,
)

WHEN = datetime(2014, 8, 20)


def _folder(name: str) -> str:
    directory, _ = LayoutTemplate.parse("{yyyy}")._render(
        RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "s"), event_name=name)
    )
    return directory.name


# --- Windows reserved names ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["CON", "con", "Aux", "NUL", "com1", "LPT9"])
def test_reserved_device_names_are_defused_case_insensitively(name: str) -> None:
    """Reserved on Windows whatever the case; a folder named CON cannot be created at all.

    Tested through a rendered token *value* -- a derived label or an event name -- because a
    fully-literal reserved segment is rejected earlier, at template-validation time.
    """
    rendered = LayoutTemplate.parse("{category}").render(
        RenderContext(category=name, captured_at=WHEN)
    )
    assert rendered.as_posix() == f"_{name}"


def test_a_reserved_name_is_reserved_even_with_an_extension() -> None:
    """`aux.jpg` is still AUX to Windows -- the stem is what is reserved."""
    rendered = LayoutTemplate.parse("{category}").render(
        RenderContext(category="aux.jpg", captured_at=WHEN)
    )
    assert rendered.as_posix() == "_aux.jpg"


# --- trailing dots and spaces --------------------------------------------------------------


@pytest.mark.parametrize("name", ["Trip.", "Trip ", "Trip. . ", "Trip..."])
def test_trailing_dots_and_spaces_are_trimmed(name: str) -> None:
    """Windows strips them silently, so `Trip.` and `Trip` would be one directory, two names."""
    assert _folder(name) == "2014-08-20 - Trip"


# --- Unicode normalization -----------------------------------------------------------------


def test_names_are_normalized_to_nfc() -> None:
    """The same name typed on macOS and on Linux must produce ONE directory, not two.

    NFD and NFC render identically and compare unequal, so without this a re-run could fail to
    recognise its own previous output.
    """
    decomposed = unicodedata.normalize("NFD", "Café Trip")
    composed = unicodedata.normalize("NFC", "Café Trip")
    assert decomposed != composed  # genuinely different byte sequences

    assert _folder(decomposed) == _folder(composed)
    assert unicodedata.is_normalized("NFC", _folder(decomposed))


# --- the 255-BYTE component cap ------------------------------------------------------------


def test_a_component_is_capped_in_bytes_not_characters() -> None:
    """The limit filesystems enforce is bytes; one character can cost four of them."""
    rendered = LayoutTemplate.parse("{category}").render(
        RenderContext(category="😀" * 200, captured_at=WHEN)
    )
    assert len(rendered.as_posix().encode("utf-8")) <= MAX_COMPONENT_BYTES


def test_truncation_never_splits_a_character() -> None:
    """Slicing UTF-8 bytes blindly leaves an invalid sequence, not a shorter name."""
    rendered = LayoutTemplate.parse("{category}").render(
        RenderContext(category="é" * 400, captured_at=WHEN)
    )
    component = rendered.as_posix()
    assert component.encode("utf-8").decode("utf-8") == component  # round-trips cleanly
    assert "�" not in component  # and carries no replacement characters


# --- same-date collisions (truestill's own constraint) --------------------------------------


def test_two_events_that_sanitize_to_one_folder_are_disambiguated() -> None:
    """Their files would otherwise merge silently, which is data loss by presentation."""
    folders = disambiguate_event_folders(
        [("a", WHEN, "goa", "Goa:Trip"), ("b", WHEN, "goa2", "Goa/Trip")]
    )
    assert [f.folder for f in folders] == ["2014-08-20 - Goa_Trip", "2014-08-20 - Goa_Trip (2)"]
    note = folders[1].note
    assert note is not None
    assert "already uses" in note


def test_collisions_are_detected_case_insensitively() -> None:
    """Two folders differing only in case collide on APFS and NTFS."""
    folders = disambiguate_event_folders(
        [("a", WHEN, "s1", "Goa Trip"), ("b", WHEN, "s2", "goa trip")]
    )
    assert folders[0].folder != folders[1].folder
    assert folders[1].folder.endswith("(2)")


def test_events_on_different_dates_never_collide() -> None:
    """The date prefix already separates them; suffixing would be noise."""
    other = datetime(2015, 1, 1)
    folders = disambiguate_event_folders(
        [("a", WHEN, "goa", "Goa Trip"), ("b", other, "goa", "Goa Trip")]
    )
    assert all(not f.folder.endswith("(2)") for f in folders)
    assert all(f.note is None for f in folders)


def test_a_third_collision_keeps_counting() -> None:
    folders = disambiguate_event_folders(
        [("a", WHEN, "s", "Trip"), ("b", WHEN, "s", "Trip"), ("c", WHEN, "s", "Trip")]
    )
    assert [f.folder for f in folders][-1].endswith("(3)")


def test_legacy_slug_naming_is_left_alone() -> None:
    """A pinned library keeps its slug folders, collisions and all -- it is already on disk."""
    folders = disambiguate_event_folders([("a", WHEN, "goa", "Goa Trip")], naming=EventNaming.SLUG)
    assert folders[0].folder == "20140820_goa"
