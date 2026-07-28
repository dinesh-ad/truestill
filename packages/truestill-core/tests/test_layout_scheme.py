"""The layout scheme: routing on evidence, and a quarantine that cannot be typed around.

Two axes decide where a file lands. The **rule** that categorized it picks timeline vs side bin;
whether it belongs to a named **event** picks which timeline template. Neither is a conditional
inside the template grammar -- the grammar stays a description of structure.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.categorize import build_rules
from truestill_core.layout import (
    PRESETS,
    SIDE_BIN_TEMPLATE_STRING,
    TIMELINE_RULE,
    EventNaming,
    LayoutScheme,
    LayoutTemplate,
    Placement,
    RenderContext,
    TemplateError,
    classify,
    parse_timeline_template,
    preview_scheme,
    scheme_from_string,
)

WHEN = datetime(2014, 8, 20, 14, 30)
ALL_RULES = (
    "screenshot_metadata",
    "screenshot_name",
    "filename_convention",
    "software",
    "device",
    "saved_heuristic",
    "fallback",
)


def _scheme() -> LayoutScheme:
    return PRESETS["year-month-event"].scheme()


# --- axis one: the rule, never the label --------------------------------------------------


@pytest.mark.parametrize("rule", ALL_RULES)
def test_every_rule_routes_to_exactly_one_side(rule: str) -> None:
    """All seven rules, so a new rule cannot be added without deciding where its files go."""
    scheme = _scheme()
    rendered = scheme.render(rule, RenderContext(category="Whatever", captured_at=WHEN))
    if rule == TIMELINE_RULE:
        assert rendered.as_posix() == "2014/2014-08/2014-08 - Everyday"
    else:
        assert rendered.as_posix() == "Whatever/2014/2014-08"


def test_the_rule_chain_produces_exactly_one_timeline_rule() -> None:
    """Routing rests on there being one camera rule; this fails loudly if that changes."""
    assert TIMELINE_RULE in ALL_RULES
    # `fallback` is emitted by `categorize` itself when no rule matches, so the chain holds
    # one fewer function than there are rule names.
    assert len(build_rules()) == len(ALL_RULES) - 1


def test_by_device_photos_stay_on_the_timeline() -> None:
    """The reason routing keys on the rule at all.

    Under ``--by-device`` the label is the hardware name, not ``Camera``. A router that tested
    the label would send an entire library into a side bin named after the phone.
    """
    scheme = _scheme()
    rendered = scheme.render(
        TIMELINE_RULE, RenderContext(category="Samsung SM-A546B", captured_at=WHEN)
    )
    assert rendered.as_posix() == "2014/2014-08/2014-08 - Everyday"  # no device folder anywhere


def test_a_side_bin_can_never_be_typed_into_a_timeline_path() -> None:
    """The junk quarantine is structural, not a default.

    The side-bin shape is fixed and is not read from user input, so no template anyone can set
    -- including one that tries to erase the category level -- reshapes a side bin.
    """
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}"),
        timeline_evented=LayoutTemplate.parse("{yyyy}"),
    )
    assert scheme.template_for(Placement.SIDE_BIN).template == SIDE_BIN_TEMPLATE_STRING
    landed = scheme.render(
        "screenshot_name", RenderContext(category="Screenshots", captured_at=WHEN)
    )
    assert landed.as_posix().startswith("Screenshots/")


# --- axis two: evented vs un-evented ------------------------------------------------------


def test_year_event_preset_splits_the_two_axes() -> None:
    """The preset that cannot be expressed as one template, which is why the axis exists."""
    scheme = PRESETS["year-event"].scheme()
    plain = scheme.render(TIMELINE_RULE, RenderContext(category="Camera", captured_at=WHEN))
    evented = scheme.render(
        TIMELINE_RULE,
        RenderContext(
            category="Camera", captured_at=WHEN, event=(WHEN, "goa"), event_name="Goa Trip"
        ),
    )
    assert plain.as_posix() == "2014/2014-08"  # month catch-all (this preset has no Everyday)
    assert evented.as_posix() == "2014/2014-08-20 - Goa Trip"  # event under the year


def test_default_preset_keeps_events_under_their_month() -> None:
    scheme = _scheme()
    evented = scheme.render(
        TIMELINE_RULE,
        RenderContext(
            category="Camera", captured_at=WHEN, event=(WHEN, "goa"), event_name="Goa Trip"
        ),
    )
    assert evented.as_posix() == "2014/2014-08/2014-08-20 - Goa Trip"


def test_no_shipped_preset_yields_a_category_leading_timeline_path() -> None:
    """The correction, pinned: source never sits above the years on the timeline."""
    for preset in PRESETS.values():
        scheme = preset.scheme()
        for context in (
            RenderContext(category="Camera", captured_at=WHEN),
            RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "e"), event_name="E"),
        ):
            first = scheme.render(TIMELINE_RULE, context).parts[0]
            assert first.startswith("2014"), f"{preset.key} led with {first!r}"


# --- the editable template is timeline-only -----------------------------------------------


def test_category_is_rejected_in_a_timeline_template_with_an_actionable_message() -> None:
    with pytest.raises(TemplateError) as excinfo:
        parse_timeline_template("{category}/{yyyy}/{mm}")
    message = str(excinfo.value)
    assert "{category}" in message
    assert "{yyyy}/{yyyy}-{mm}" in message  # tells the user what to do instead


def test_category_is_rejected_at_load_too_now_that_no_library_stores_one() -> None:
    """There is no second interpretation of a stored template any more.

    Load leniency existed solely so a pinned category-first library kept resolving. With that
    layout decommissioned, `scheme_from_string` parses through the same strict door as Settings.
    """
    with pytest.raises(TemplateError):
        scheme_from_string("{category}/{yyyy}/{mm}")


# --- event folder naming, and its sanitizer -----------------------------------------------


def test_event_names_are_readable_and_keep_their_case() -> None:
    scheme = _scheme()
    rendered = scheme.render(
        TIMELINE_RULE,
        RenderContext(
            category="Camera", captured_at=WHEN, event=(WHEN, "goa-trip"), event_name="Goa Trip"
        ),
    )
    assert rendered.name == "2014-08-20 - Goa Trip"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Trip: Goa/2014", "2014-08-20 - Trip_ Goa_2014"),
        ("Holiday   ", "2014-08-20 - Holiday"),
        ("Trip...", "2014-08-20 - Trip"),
        ('a<b>c"d|e?f*g', "2014-08-20 - a_b_c_d_e_f_g"),
    ],
)
def test_hostile_event_names_are_made_path_safe(name: str, expected: str) -> None:
    """A user-supplied name becomes a directory, so it gets a template literal's treatment."""
    template = LayoutTemplate.parse("{yyyy}")
    directory, _ = template._render(
        RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "s"), event_name=name)
    )
    assert directory.name == expected


def test_sanitizing_an_event_name_is_reported_at_preview_time() -> None:
    """Never-silent: what the sanitizer changed has to be visible before anything is written."""
    template = LayoutTemplate.parse("{yyyy}")
    _, notes = template._render(
        RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "s"), event_name="A/B")
    )
    assert any("path-safe" in note for note in notes)


def test_an_event_name_that_sanitizes_to_nothing_falls_back_to_the_slug() -> None:
    template = LayoutTemplate.parse("{yyyy}")
    directory, notes = template._render(
        RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "goa"), event_name="///")
    )
    assert directory.name == "20140820_goa"
    assert any("used the slug instead" in note for note in notes)


def test_an_event_without_a_recorded_name_falls_back_to_its_slug() -> None:
    """SLUG naming survives the decommission -- it is what an unnamed event renders as."""
    slugged = LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.SLUG)
    scheme = LayoutScheme.of(timeline=slugged, timeline_evented=slugged)
    rendered = scheme.render(
        TIMELINE_RULE,
        RenderContext(category="Camera", captured_at=WHEN, event=(WHEN, "goa"), event_name="Goa"),
    )
    assert rendered.as_posix() == "2014/2014-08/20140820_goa"


# --- undated, on both branches ------------------------------------------------------------


def test_undated_collapses_per_branch() -> None:
    scheme = _scheme()
    assert scheme.render(TIMELINE_RULE, RenderContext(category="Camera")).as_posix() == "Undated"
    assert (
        scheme.render("screenshot_name", RenderContext(category="Screenshots")).as_posix()
        == "Screenshots/Undated"
    )


# --- R2: the year is always the top-level parent ------------------------------------------


def test_no_shipped_preset_can_put_a_category_above_a_year() -> None:
    """R2, on the preset side: side bins sit beside the years, never above them."""
    for preset in PRESETS.values():
        for template in (preset.timeline, preset.timeline_evented):
            assert "{category}" not in template, f"{preset.key} names a category on the timeline"


@pytest.mark.parametrize(
    "attempt",
    [
        "{category}/{yyyy}/{mm}",  # category-first
        "{yyyy}/{yyyy}-{mm}/{category}",  # category-last
        "Photos/{category}/{yyyy}",  # category buried behind a literal
    ],
)
def test_no_template_a_user_can_type_places_a_category_on_the_timeline(attempt: str) -> None:
    """R2, on the template side: it is structurally impossible, not merely unavailable."""
    with pytest.raises(TemplateError):
        parse_timeline_template(attempt)


def test_no_category_first_rendering_survives_anywhere_in_the_tree() -> None:
    """The decommission is proved against the repo, not against the registry.

    A living test, in the same style as the removed preset names: what it catches is not a
    surviving code path -- the type system covers that -- but a surviving *reference* in help
    text, a doc or a fixture that would send someone toward a layout the product cannot produce.
    """
    forbidden = ("LEGACY_TEMPLATE_STRING", "is_legacy", "legacy_note", "Legacy layout")
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()

    offenders: list[str] = []
    for relative in tracked:
        path = root / relative
        # This test names the strings it forbids; the research docs record the history on purpose.
        if path.suffix in {".png", ".jpg", ".ico"} or relative in {
            "packages/truestill-core/tests/test_layout_scheme.py",
            "docs/default-layout-research.md",
            "docs/legacy-decommission-research.md",
            "CHANGELOG.md",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        offenders += [f"{relative}: {name}" for name in forbidden if name in text]

    assert not offenders, "category-first references still present: " + "; ".join(offenders)


#: Every shipped preset rendered through every sample row. **Written out as literals on
#: purpose** - a golden matrix compared against the implementation is only worth having if the
#: expected side was produced by a human reading it, not by the code under test. These are the
#: exact paths the boolean-router version produced before `Placement` existed, so the refactor
#: that introduced the enum is pinned as behaviour-preserving rather than merely asserted to be.
GOLDEN_PLACEMENTS: dict[str, tuple[str, ...]] = {
    "year-month-event": (
        "2014/2014-08/2014-08 - Everyday/sample.jpg",
        "2014/2014-08/2014-08-20 - Goa Trip/sample.jpg",
        "Undated/sample.jpg",
        "Screenshots/2024/2024-01/sample.jpg",
    ),
    "year-event": (
        "2014/2014-08/sample.jpg",
        "2014/2014-08-20 - Goa Trip/sample.jpg",
        "Undated/sample.jpg",
        "Screenshots/2024/2024-01/sample.jpg",
    ),
    "year-month-day": (
        "2014/2014-08/2014-08-20/sample.jpg",
        "2014/2014-08/2014-08-20/2014-08-20 - Goa Trip/sample.jpg",
        "Undated/sample.jpg",
        "Screenshots/2024/2024-01/sample.jpg",
    ),
}


@pytest.mark.parametrize("key", sorted(GOLDEN_PLACEMENTS))
def test_every_preset_renders_its_known_paths(key: str) -> None:
    """The routing matrix, pinned. Guards the router against silent re-wiring.

    Swapping two placements in `LayoutScheme.of`, or making `classify` answer differently, is
    invisible to a test that only checks one shape at a time - each individual assertion still
    passes against *some* template. Only the whole matrix catches a permutation.
    """
    rendered = tuple(row.path.as_posix() for _, row in preview_scheme(PRESETS[key].scheme()))
    assert rendered == GOLDEN_PLACEMENTS[key]


def test_classify_routes_on_the_rule_then_on_the_event() -> None:
    """The router's whole contract, stated once."""
    dated = RenderContext(category="Camera", captured_at=WHEN)
    evented = RenderContext(
        category="Camera", captured_at=WHEN, event=(WHEN, "goa-trip"), event_name="Goa Trip"
    )
    assert classify(TIMELINE_RULE, dated) is Placement.EVERYDAY
    assert classify(TIMELINE_RULE, evented) is Placement.EVENT_DAY
    # The rule wins outright: a side-bin file is a side-bin file even carrying an event.
    assert classify("screenshot_name", dated) is Placement.SIDE_BIN
    assert classify("screenshot_name", evented) is Placement.SIDE_BIN


def test_a_scheme_must_carry_a_template_for_every_placement() -> None:
    """Totality is checked where the scheme is built, not where a file is being placed."""
    with pytest.raises(TemplateError, match="missing a template"):
        LayoutScheme(templates={Placement.EVERYDAY: LayoutTemplate.parse("{yyyy}")})

    complete = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}"),
        timeline_evented=LayoutTemplate.parse("{yyyy}"),
    )
    assert set(complete.templates) == set(Placement)
