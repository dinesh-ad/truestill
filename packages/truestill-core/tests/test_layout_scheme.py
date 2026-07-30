"""The layout scheme: routing on evidence, and a quarantine that cannot be typed around.

Two axes decide where a file lands. The **rule** that categorized it picks timeline vs side bin;
whether it belongs to a named **event** picks which timeline template. Neither is a conditional
inside the template grammar -- the grammar stays a description of structure.
"""

from __future__ import annotations

import inspect
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from truestill_core.categorize import build_rules
from truestill_core.layout import (
    DEFAULT_EVERYDAY_DAY_THRESHOLD,
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
    count_capture_days,
    heavy_capture_days,
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


def test_no_decommissioned_layout_reference_survives_current_facing_text() -> None:
    """The decommission is proved against current-facing repo text, not only the registry.

    A living test, in the same style as the removed preset names: what it catches is not a
    surviving code path -- the type system covers that -- but a surviving *reference* in help
    text, a doc or a fixture that would send someone toward a layout the product cannot produce.

    Research, the changelog and the dated walkthrough remain immutable evidence. Three negative
    fixtures also spell the rejected template literally so they can prove it is rejected.
    """
    forbidden = (
        "LEGACY_TEMPLATE_STRING",
        "is_legacy",
        "legacy_note",
        "Legacy layout",
        "<Label>/YYYY/MM",
        "Camera/YYYY/MM",
        "{category}/{yyyy}/{mm}",
        "label / %Y / %m",
    )
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()

    historical_files = {
        "CHANGELOG.md",
        "docs/default-layout-research.md",
        "docs/legacy-decommission-research.md",
        "docs/org-structure-research.md",
        "docs/trip-grouping-research.md",
        "docs/walkthrough-qa-report.md",
    }
    negative_fixture_files = {
        "packages/truestill-cli/tests/test_config_cli.py",
        "packages/truestill-core/tests/test_layout_scheme.py",
        "packages/truestill-core/tests/test_migrate.py",
    }
    offenders: list[str] = []
    for relative in tracked:
        path = root / relative
        if (
            path.suffix in {".png", ".jpg", ".ico"}
            or relative in historical_files
            or relative in negative_fixture_files
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        offenders += [f"{relative}: {name}" for name in forbidden if name in text]

    assert not offenders, "decommissioned layout references still present: " + "; ".join(offenders)


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


def test_classify_refuses_an_unknown_rule_name() -> None:
    """Intentional tightening: a typo must raise, not silently side-bin."""
    with pytest.raises(ValueError, match="devcie"):
        classify("devcie", RenderContext(category="Camera", captured_at=WHEN))


# --- axis three: trip days (Stage 2d, 13.2) -----------------------------------------------


def test_classify_puts_a_trip_ahead_of_an_event_unconditionally() -> None:
    """§2: a trip day claims every photo taken that day - never EVENT_DAY, even carrying one.

    The precedence recommendation trip-grouping-research.md §13.3(1) settled on: `classify`
    ignores `context.event` once `context.trip` is set, so a caller cannot get this wrong by
    omission (it need not remember to also clear `event` for a trip-claimed day).
    """
    trip_and_event = RenderContext(
        category="Camera",
        captured_at=WHEN,
        event=(WHEN, "goa-trip"),
        event_name="Goa Trip",
        trip=(WHEN, "wayanad"),
        trip_name="Wayanad",
    )
    trip_only = RenderContext(
        category="Camera", captured_at=WHEN, trip=(WHEN, "wayanad"), trip_name="Wayanad"
    )
    assert classify(TIMELINE_RULE, trip_and_event) is Placement.TRIP_DAY
    assert classify(TIMELINE_RULE, trip_only) is Placement.TRIP_DAY
    # The rule still wins outright, exactly as it does over an event.
    assert classify("screenshot_name", trip_only) is Placement.SIDE_BIN


def test_trip_day_renders_the_wayanad_shape() -> None:
    """§2's exact worked example: the trip's own header folder, then each individual day."""
    scheme = _scheme()  # year-month-event: TRIP_DAY derives from timeline_evented, unset here
    start = datetime(2014, 8, 15)
    for day in (15, 16, 17):
        context = RenderContext(
            category="Camera",
            captured_at=datetime(2014, 8, day, 12, 0),
            trip=(start, "wayanad"),
            trip_name="Wayanad",
        )
        path = scheme.render(TIMELINE_RULE, context)
        assert path.as_posix() == f"2014/2014-08/2014-08-15 - Wayanad/2014-08-{day}"


def test_trip_day_files_under_its_start_month_even_when_a_member_crosses_into_the_next() -> None:
    """§3(d): a trip is one object, filed entirely under the month it started in."""
    scheme = _scheme()
    start = datetime(2016, 11, 28)
    context = RenderContext(
        category="Camera",
        captured_at=datetime(2016, 12, 2, 9, 0),  # this member's OWN date is in December
        trip=(start, "goa"),
        trip_name="Goa",
    )
    path = scheme.render(TIMELINE_RULE, context)
    # Base segments (year/month) come from the trip's start; only the day level is the member's
    # own date.
    assert path.as_posix() == "2016/2016-11/2016-11-28 - Goa/2016-12-02"


def test_trip_day_defaults_to_the_event_day_templates_naming() -> None:
    """§13.3(2): "the trip shape is the day-event shape plus one dated level" - no new knob.

    `LayoutScheme.of` derives `TRIP_DAY`'s template from `timeline_evented` when `trip_day` is
    not given, so a scheme built the same way every shipped preset already is gets a valid trip
    template for free. Fails against the wrong-template class of bug this could regress to (a
    fourth shape silently inheriting `EVERYDAY`'s template instead of `EVENT_DAY`'s) - confirmed
    by temporarily changing `of`'s `TRIP_DAY` arm to `timeline` and re-running: the assertion
    below caught it (`AssertionError`), restored after.
    """
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}"),  # EVERYDAY: deliberately different from evented
        timeline_evented=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}"),
    )
    context = RenderContext(
        category="Camera", captured_at=WHEN, trip=(WHEN, "goa"), trip_name="Goa"
    )
    path = scheme.render(TIMELINE_RULE, context)
    # If TRIP_DAY had inherited EVERYDAY's template, this would render "2014/2014-08-20 - Goa/..."
    # under a bare {yyyy} base instead.
    assert path.as_posix() == "2014/2014-08/2014-08-20 - Goa/2014-08-20"


def test_trip_day_can_carry_a_different_naming_than_event_day() -> None:
    """The `(mm)` boundary, baselined: TRIP_DAY is the first placement whose naming can
    genuinely diverge from EVENT_DAY's (no shipped preset does this yet, exactly like no shipped
    preset made EVENT_DAY differ from EVERYDAY before this). Proves the render seam can express
    the divergence; migrate.py's collision-scoping across that divergence is 13.4's job, not
    exercised here.
    """
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}"),
        timeline_evented=LayoutTemplate.parse(
            "{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.READABLE
        ),
        trip_day=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.SLUG),
    )
    start = datetime(2026, 8, 15)
    event_path = scheme.render(
        TIMELINE_RULE,
        RenderContext(
            category="Camera", captured_at=start, event=(start, "goa-trip"), event_name="Goa Trip"
        ),
    )
    trip_path = scheme.render(
        TIMELINE_RULE,
        RenderContext(
            category="Camera", captured_at=start, trip=(start, "goa-trip"), trip_name="Goa Trip"
        ),
    )
    # Same date, same name, same slug -- yet genuinely different header folders, because each
    # placement's own naming was asked, never a fixed guess (the principle (mm) enforced for
    # migrate.py, now proven expressible at the render seam itself).
    assert event_path.as_posix() == "2026/2026-08/2026-08-15 - Goa Trip"
    assert trip_path.as_posix() == "2026/2026-08/20260815_goa-trip/2026-08-15"


def test_a_scheme_must_carry_a_template_for_every_placement() -> None:
    """Totality is checked where the scheme is built, not where a file is being placed."""
    with pytest.raises(TemplateError, match="missing a template"):
        LayoutScheme(templates={Placement.EVERYDAY: LayoutTemplate.parse("{yyyy}")})

    complete = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}"),
        timeline_evented=LayoutTemplate.parse("{yyyy}"),
    )
    assert set(complete.templates) == set(Placement)


# --- axis four: heavy un-evented days (backlog gg) ----------------------------------------


def test_classify_routes_heavy_day_after_trip_and_event() -> None:
    """Order: SIDE_BIN → TRIP_DAY → EVENT_DAY → DAY_BUCKET | EVERYDAY."""
    heavy = RenderContext(category="Camera", captured_at=WHEN, heavy_day=True)
    assert classify(TIMELINE_RULE, heavy) is Placement.DAY_BUCKET
    assert classify(TIMELINE_RULE, RenderContext(category="Camera", captured_at=WHEN)) is (
        Placement.EVERYDAY
    )
    # Trip and event still win even when the caller also marked the day heavy.
    assert (
        classify(
            TIMELINE_RULE,
            RenderContext(
                category="Camera",
                captured_at=WHEN,
                heavy_day=True,
                event=(WHEN, "goa"),
                event_name="Goa",
            ),
        )
        is Placement.EVENT_DAY
    )
    assert (
        classify(
            TIMELINE_RULE,
            RenderContext(
                category="Camera",
                captured_at=WHEN,
                heavy_day=True,
                trip=(WHEN, "wayanad"),
                trip_name="Wayanad",
            ),
        )
        is Placement.TRIP_DAY
    )
    assert classify("screenshot_name", heavy) is Placement.SIDE_BIN


def test_classify_is_pure_and_never_counts() -> None:
    """The heavy-day flag arrives on RenderContext; classify must not reach for a catalog.

    Pin by source: the router body names only rule/context fields and Placement members - no
    Catalog, no threshold helpers, no day-count helpers. Confirmed by temporarily inserting
    ``count_capture_days`` into ``classify`` and watching this assertion fail, then restoring.
    """
    source = inspect.getsource(classify)
    forbidden = (
        "Catalog",
        "get_setting",
        "count_capture_days",
        "heavy_capture_days",
        "normalize_everyday_day_threshold",
        "EVERYDAY_DAY_THRESHOLD",
        "DEFAULT_EVERYDAY_DAY_THRESHOLD",
    )
    for name in forbidden:
        assert name not in source, f"classify must stay pure; found {name!r}"


def test_day_bucket_renders_the_dated_everyday_shape() -> None:
    """Product shape from adaptive-day-folder-research.md - not derived from the timeline string."""
    scheme = _scheme()
    path = scheme.render(
        TIMELINE_RULE, RenderContext(category="Camera", captured_at=WHEN, heavy_day=True)
    )
    assert path.as_posix() == "2014/2014-08/2014-08-20 - Everyday"


def test_day_bucket_defaults_to_the_product_template_not_the_timeline() -> None:
    """DAY_BUCKET must not silently inherit EVERYDAY's monthly template.

    Confirmed by temporarily pointing of()'s DAY_BUCKET arm at ``timeline`` and re-running:
    this assertion failed (monthly Everyday path), then restored.
    """
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}/{yyyy}-{mm} - Everyday"),
        timeline_evented=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}"),
    )
    path = scheme.render(
        TIMELINE_RULE, RenderContext(category="Camera", captured_at=WHEN, heavy_day=True)
    )
    assert path.as_posix() == "2014/2014-08/2014-08-20 - Everyday"
    assert "2014-08 - Everyday" not in path.as_posix()


def test_count_capture_days_is_one_linear_pass() -> None:
    """O(n) over the sequence; heavy-day membership is O(1) against the result, not a recount."""
    days = [
        datetime(2014, 8, 17, 9, 0),
        datetime(2014, 8, 17, 10, 0),
        date(2014, 8, 17),
        datetime(2014, 8, 18, 11, 0),
        None,
    ]
    counts = count_capture_days(days)
    assert counts == {"2014-08-17": 3, "2014-08-18": 1}
    # Exactly at the threshold stays monthly; one over becomes heavy.
    at_limit = {**counts, "2014-08-17": DEFAULT_EVERYDAY_DAY_THRESHOLD}
    assert heavy_capture_days(at_limit) == frozenset()
    over = {**counts, "2014-08-17": DEFAULT_EVERYDAY_DAY_THRESHOLD + 1}
    assert heavy_capture_days(over) == frozenset({"2014-08-17"})
    assert heavy_capture_days(over, threshold=2) == frozenset({"2014-08-17"})
