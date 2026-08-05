"""The rail: dark in both themes, an outlined wordmark, a monogram when collapsed.

Shell only. Nothing here asserts screen content.

The rail is **theme-independent**: it is dark in light mode too, so its tokens sit outside the
light/dark ladder and the two colours that used to be borrowed from it were re-derived against
it rather than reused - `--text-muted` measured 3.91:1 there, below AA, while its own source
annotation claims 4.6:1 *on white*.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

_LIGHT = {"colorScheme": "light"}


def _rail_bg(ui: Page) -> str:
    return ui.eval_on_selector(".sidebar", "el => getComputedStyle(el).backgroundColor")


def test_the_rail_is_dark_in_light_mode_too(ui: Page) -> None:
    """Theme-independent, which is the whole point of giving it its own token group."""
    ui.emulate_media(color_scheme="light")
    light = _rail_bg(ui)
    ui.emulate_media(color_scheme="dark")
    dark = _rail_bg(ui)

    assert light == dark, f"the rail changed with the theme: light {light} vs dark {dark}"
    # Dark means dark: every channel low. Parsed rather than string-matched so a token
    # rename that keeps the colour still passes, and a colour change fails.
    channels = [int(v) for v in light[light.index("(") + 1 : light.index(")")].split(",")[:3]]
    assert max(channels) < 60, f"the rail is not dark: {light}"


def test_the_wordmark_is_monospace_text_not_artwork(ui: Page) -> None:
    """REWRITTEN 2026-08-05. It asserted the wordmark was outlined SVG; that ruling was reversed.

    `ui-v2-research` §2 argues monospace as the product's TYPE SIGNATURE - every path, count and
    hash is monospace, and the wordmark heads that system. A serif mark took the wordmark out of
    the one thing it was chosen to lead. The earlier reasoning about Georgia still holds and is
    why no serif *font* is used; what changed is that the answer is not a serif at all.

    Being real text has a second benefit the SVG had to work for: the product's own name is
    selectable, searchable and available to a screen reader without an `aria-label` standing in
    for it.
    """
    mark = ui.locator(".wordmark")
    expect(mark).to_be_visible()
    expect(mark).to_contain_text("Truestill")

    # `locator().count()`, not `eval_on_selector`, which RAISES on a missing element rather
    # than returning None - an absence has to be asserted with something that can express one.
    assert ui.locator(".wordmark svg[data-brand='wordmark']").count() == 0, (
        "the wordmark is still an SVG"
    )

    family = ui.eval_on_selector(".wordmark-text", "el => getComputedStyle(el).fontFamily")
    assert "mono" in family.lower(), f"the wordmark is not monospace: {family!r}"

    # The trailing dot is part of the mark and carries its own colour.
    expect(ui.locator(".wordmark .dot")).to_have_text(".")


def test_the_wordmark_gradient_is_authored_for_the_rail_not_the_brand_sheet(ui: Page) -> None:
    """The supplied gradient cannot be used here, and this pins why.

    `#2A3B8C`, the brand sheet's low stop, measures **1.81:1** against the rail - it fails every
    threshold. The sheet's gradient is for a light page. The rail's is authored separately, and
    this asserts the unusable stop is not what shipped.
    """
    stops = ui.eval_on_selector_all(
        ".wordmark svg[data-brand='monogram'] linearGradient stop",
        "els => els.map(e => (e.getAttribute('stop-color') || '').toLowerCase())",
    )
    assert stops, "no gradient stops found"
    assert "#2a3b8c" not in stops, (
        "the brand sheet's light-page gradient stop is on the dark rail, where it measures "
        "1.81:1 and is effectively invisible"
    )


def test_each_mark_carries_its_own_gradient_so_it_paints_when_its_sibling_is_hidden(
    ui: Page,
) -> None:
    """The defect this caught: a shared gradient that stops resolving when collapsed.

    Both marks first referenced one `<linearGradient>` declared inside the wordmark SVG. When
    the rail collapses, the wordmark is `display: none` - and **a hidden SVG's `defs` do not
    resolve**, so the monogram rendered at its full 39x26 box and painted nothing at all. It was
    present, measurable, correctly sized and invisible, which is why the geometry assertions
    above did not notice. Each mark now declares its own gradient.
    """
    for mark in ("monogram",):  # the wordmark is text again; only this one is artwork
        own = ui.eval_on_selector(
            f".wordmark svg[data-brand='{mark}']",
            "el => { const g = el.querySelector('linearGradient');"
            " if (!g) return null;"
            " const fill = el.querySelector('path').getAttribute('fill') || '';"
            " return fill.includes(g.id); }",
        )
        assert own is True, f"the {mark} does not reference a gradient it declares itself"


def test_collapsing_swaps_the_wordmark_for_the_monogram(ui: Page) -> None:
    """The 64px rail gets the monogram; the full wordmark does not fit and is not shrunk into it."""
    expect(ui.locator(".wordmark .wordmark-text")).to_be_visible()
    expect(ui.locator(".wordmark svg[data-brand='monogram']")).to_be_hidden()

    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")

    expect(ui.locator(".wordmark svg[data-brand='monogram']")).to_be_visible()
    expect(ui.locator(".wordmark .wordmark-text")).to_be_hidden()


def test_the_nav_is_grouped_but_still_seven_flat_items(ui: Page) -> None:
    """Section labels are grouping, not hierarchy. `(aam)` closed as no nested submenus."""
    labels = ui.eval_on_selector_all(
        ".nav-section-label", "els => els.map(e => e.textContent.trim().toUpperCase())"
    )
    assert labels == ["MAIN", "SETTINGS"], f"expected MAIN and SETTINGS, got {labels}"

    assert ui.eval_on_selector_all(".nav-item", "els => els.length") == 7
    assert (
        ui.eval_on_selector_all(
            ".nav-item [class*='submenu'], .nav-item ul, .nav-item .nav-children",
            "els => els.length",
        )
        == 0
    ), "a submenu appeared; (aam) closed as no nested submenus"


def test_the_section_labels_are_hidden_when_collapsed(ui: Page) -> None:
    """A 64px rail has no room for a word, and a clipped 'SETTINGS' is worse than none."""
    labels = ui.locator(".nav-section-label")
    # Anti-vacuity: with no labels at all this test is an empty loop that always passes.
    assert labels.count() == 2, f"expected 2 section labels before collapsing, got {labels.count()}"

    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    for label in labels.all():
        expect(label).to_be_hidden()


def test_the_rail_artwork_matches_the_authored_source(ui: Page) -> None:
    """The inline SVG and `brand/` must not drift apart.

    The artwork is inlined rather than linked, which buys the accessible name, the collapsed
    swap and zero extra requests - and costs a second copy. This is what makes the copy a
    duplicate rather than a fork: the path data in the page has to be the path data in
    `brand/*-dark.svg`. Dark, because this rail is dark in both themes.
    """
    root = Path(__file__).resolve().parents[2]
    for mark in ("monogram",):  # the wordmark is text; only this one comes from brand/
        source = (root / "brand" / f"{mark}-dark.svg").read_text(encoding="utf-8")
        expected = re.search(r'<path d="([^"]+)"', source)
        assert expected is not None, f"no path data in brand/{mark}-dark.svg"
        rendered = ui.eval_on_selector(
            f".wordmark svg[data-brand='{mark}'] path", "el => el.getAttribute('d')"
        )
        assert rendered == expected.group(1), (
            f"the {mark} in index.html has drifted from brand/{mark}-dark.svg"
        )


def test_the_tab_icon_is_served(ui: Page) -> None:
    """brand.md §6's stated whole win: the tab stops showing a blank page icon."""
    link = ui.eval_on_selector("link[rel='icon']", "el => el.getAttribute('href')")
    assert link == "/static/favicon.ico"

    response = ui.request.get(f"{ui.url.split('?')[0].rstrip('/')}/static/favicon.ico")
    assert response.ok, f"the favicon 404s: {response.status}"
    body = response.body()
    # An ICO is a container; assert it really carries several sizes rather than one.
    assert body[:4] == b"\x00\x00\x01\x00", "not an ICO"
    assert int.from_bytes(body[4:6], "little") >= 5, "the ICO carries too few sizes"


def test_the_collapse_control_is_a_chevron_not_a_nav_row(ui: Page) -> None:
    """Collapsing is something you do to the rail, not a place you go.

    Asserts the shape changed AND that (fff) survived it: the control is still a real button
    with an accessible name that flips. The visible word is gone by ruling, so `aria-label` is
    now the only thing carrying that name - which is why it is asserted here rather than assumed.
    """
    toggle = ui.locator("#sidebar-toggle")
    expect(toggle).to_be_visible()

    assert ui.eval_on_selector("#sidebar-toggle", "el => el.tagName") == "BUTTON"
    assert ui.eval_on_selector("#sidebar-toggle", "el => el.getAttribute('aria-label')") == (
        "Collapse sidebar"
    )
    # Not one of the seven destinations, and not shaped like one.
    assert (
        ui.eval_on_selector("#sidebar-toggle", "el => el.classList.contains('nav-item')") is False
    )
    box = toggle.bounding_box()
    rail = ui.locator("#sidebar").bounding_box()
    assert box is not None
    assert rail is not None
    assert box["width"] < rail["width"] / 2, "the chevron still spans the rail like a nav row"

    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    assert ui.eval_on_selector("#sidebar-toggle", "el => el.getAttribute('aria-label')") == (
        "Expand sidebar"
    ), "the accessible name did not flip; (fff) requires it and there is no visible word now"


def test_the_account_slot_is_reserved_and_empty(ui: Page) -> None:
    """D5 is unbuilt, so the position is held and nothing is guessed into it.

    `(aam)` already ruled what goes here - account/licence details, sign-out inside, never a
    one-click Logout. Until that exists the slot renders nothing and takes no space.
    """
    slot = ui.locator("#account-slot")
    assert slot.count() == 1, "the reserved account position is gone"
    assert ui.eval_on_selector("#account-slot", "el => el.children.length") == 0
    assert ui.eval_on_selector("#account-slot", "el => el.textContent.trim()") == ""
    expect(slot).to_be_hidden()


def test_the_chevron_rides_the_boundary_between_rail_and_content(ui: Page) -> None:
    """The control sits ON the edge, straddling it - not inside the rail beside the wordmark.

    **It had to leave `.sidebar` to do this, and that was forced rather than chosen.** The rail
    carries `overflow-x: hidden` to keep the catalog path inside the 64px form (`(fff)`, pinned
    by `test_collapsed_custody_stays_inside_the_rail`), which would clip an overhanging child.
    Relaxing it is not available: the rail also needs `overflow-y: auto` so a short window can
    reach every nav item, and a box with one axis `auto` computes the other from `visible` to
    `auto` - verified in a browser, not assumed. So the button is a child of the shell instead.

    **The size is asserted, not eyeballed.** This exact control already rendered 207px wide once,
    because its rule sat before the shared `.sidebar-toggle, .nav-item { width: 100% }` block and
    lost on source order at equal specificity. Moving the element moves its cascade position
    again, so the assertion travels with it.
    """
    toggle = ui.locator("#sidebar-toggle")
    rail = ui.locator("#sidebar")
    expect(toggle).to_be_visible()

    box = toggle.bounding_box()
    rail_box = rail.bounding_box()
    assert box is not None
    assert rail_box is not None

    # Small and round, not a row.
    assert box["width"] <= 32, f"the chevron is {box['width']}px wide - that is a row, not a knob"
    assert abs(box["width"] - box["height"]) <= 1, "not a circle"

    # Straddling: its centre is on the rail's right edge, so roughly half overhangs.
    edge = rail_box["x"] + rail_box["width"]
    centre = box["x"] + box["width"] / 2
    assert abs(centre - edge) <= 3, (
        f"the chevron's centre is {centre}px but the boundary is {edge}px - it is not on the edge"
    )

    # And it is NOT clipped: its full width is painted, which is what leaving the rail bought.
    assert box["width"] > 0
    assert box["x"] < edge < box["x"] + box["width"], "the chevron does not cross the boundary"


def test_the_chevron_follows_the_boundary_when_the_rail_collapses(ui: Page) -> None:
    """It rides the edge, so it moves with the edge rather than staying where it was."""
    rail = ui.locator("#sidebar")
    before = ui.locator("#sidebar-toggle").bounding_box()
    assert before is not None

    ui.click("#sidebar-toggle")
    expect(rail).to_have_attribute("data-collapsed", "true")
    ui.wait_for_timeout(400)  # the shell animates its columns over 160ms

    after = ui.locator("#sidebar-toggle").bounding_box()
    rail_box = rail.bounding_box()
    assert after is not None
    assert rail_box is not None
    assert after["x"] < before["x"], "the chevron did not follow the rail inwards"
    edge = rail_box["x"] + rail_box["width"]
    assert abs((after["x"] + after["width"] / 2) - edge) <= 3, "it left the boundary"


def test_the_chevron_keeps_its_accessible_name_and_keyboard_operation(ui: Page) -> None:
    """(fff) must not regress for a visual change. It carries the name alone now."""
    toggle = ui.locator("#sidebar-toggle")
    assert ui.eval_on_selector("#sidebar-toggle", "el => el.tagName") == "BUTTON"
    assert ui.eval_on_selector("#sidebar-toggle", "el => el.getAttribute('aria-label')") == (
        "Collapse sidebar"
    )

    toggle.focus()
    expect(toggle).to_be_focused()
    ui.keyboard.press("Enter")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    expect(toggle).to_be_focused()
    assert ui.eval_on_selector("#sidebar-toggle", "el => el.getAttribute('aria-label')") == (
        "Expand sidebar"
    )


def test_below_the_breakpoint_the_chevron_is_gone(ui: Page) -> None:
    """There is no edge to ride when the rail is a top bar, so the control is not shown.

    Collapsing a horizontal bar means nothing, and `(fff)`'s own rule already hid the toggle at
    this width. Asserted here because the element moved to the shell, where a media query that
    used to reach it might not.
    """
    ui.set_viewport_size({"width": 700, "height": 800})
    expect(ui.locator("#sidebar-toggle")).to_be_hidden()


def test_the_wordmark_is_flat_with_an_accent_dot_not_a_gradient(ui: Page) -> None:
    """The gradient was tried on the rail and rejected on evidence, not on taste.

    Not a contrast failure - both stops measure clear of AA there (9.17:1 and 6.04:1). Rendered
    at 3x and compared: across nine characters at 18px the shift is imperceptible, and it
    swallows the accent dot, whose colour IS the gradient's high stop. The dot is the mark's one
    deliberate chromatic note. This pins the outcome so the gradient is not reapplied here later;
    it still belongs on the monogram, the icons and the website header, where there is room.
    """
    word = ui.eval_on_selector(
        ".wordmark-text",
        "el => { const s = getComputedStyle(el);"
        " return {img: s.backgroundImage, colour: s.color}; }",
    )
    assert word["img"] == "none", f"a gradient is back on the wordmark: {word['img']!r}"

    dot = ui.eval_on_selector(".wordmark-text .dot", "el => getComputedStyle(el).color")
    assert dot != word["colour"], (
        f"the accent dot is the same colour as the word ({dot}) - it has stopped being an accent"
    )


def test_the_nav_icons_are_sized_as_icons_not_as_body_text(ui: Page) -> None:
    """The glyphs are 16px, and that is a deliberate size rather than an inherited one.

    They were 13px, and nothing said so: `.nav-item .ico` sets `width: 18px` and no font-size,
    so the glyph took `--text-sm` from the row's `font` shorthand. The 18px is a reserved
    COLUMN for label alignment; it never sized anything. Asserting the computed size pins the
    distinction, because a reader who sees `width: 18px` will assume the icon is 18px.
    """
    size = ui.eval_on_selector(".nav-item .ico", "el => getComputedStyle(el).fontSize")
    assert size == "16px", f"the nav icon is {size}, not the intended 16px"

    row = ui.eval_on_selector(".nav-item", "el => getComputedStyle(el).fontSize")
    assert row != size, (
        "the icon is the same size as the row's text again, which is how it became 13px - "
        "it must carry its own size, not inherit one"
    )


def test_the_icon_size_does_not_inflate_the_row(ui: Page) -> None:
    """`line-height: 1` on the glyph, or every row grows and the nav block grows with it.

    Measured before writing: at 16px with the inherited line-height the icon box becomes 19.2px
    tall, each row grows 31.6 -> 35.2px, and the nav block grows by 25px. With `line-height: 1`
    the row moves 31.6 -> 32.0 and the block by under 3px. The chevron already uses exactly this
    pattern (`.sidebar-toggle .chevron`), so this is the house answer, not a new trick.
    """
    line_height = ui.eval_on_selector(".nav-item .ico", "el => getComputedStyle(el).lineHeight")
    assert line_height == "16px", (
        f"the icon's line-height is {line_height}; it must be 1 (= its own font-size) so the "
        "glyph does not drive the row's height"
    )

    box = ui.eval_on_selector_all(
        ".nav-item", "els => els.map(e => +e.getBoundingClientRect().height.toFixed(1))"
    )
    assert max(box) <= 33, f"a nav row is {max(box)}px tall - the icon is inflating it"


def test_the_icon_box_and_the_label_position_are_unchanged(ui: Page) -> None:
    """The size change must buy nothing at the label's expense.

    The 18px column and the label's left edge are what a bigger glyph would disturb first, so
    both are pinned. The widest glyph measures 15px at 16px type, which is why 16 was taken and
    18 was not - 18px type measures 17px in an 18px box, which is the edge.
    """
    ico = ui.eval_on_selector(
        ".nav-item .ico",
        "el => { const r = el.getBoundingClientRect();"
        " return {w: +r.width.toFixed(1), x: +r.x.toFixed(1)}; }",
    )
    label = ui.eval_on_selector(
        ".nav-item .nav-label", "el => +el.getBoundingClientRect().x.toFixed(1)"
    )
    assert ico["w"] == 18, f"the reserved icon column is {ico['w']}px, not 18px"
    assert ico["x"] == 24, f"the icon column moved to x={ico['x']}"
    assert label == 54, f"the label moved to x={label}; the icon column pushed it"

    # THE GLYPH'S OWN INK, not the box. `flex: 0 0 18px` pins the box, so an oversized glyph
    # overflows it while width, x and the label all stay exactly where they were - every
    # assertion above passes at 24px and at 32px. Proven, not supposed: this is what the
    # mutation caught. A Range over the text node measures what is actually painted.
    widest = ui.evaluate(
        "() => Math.max(...[...document.querySelectorAll('.nav-item .ico')].map(el => {"
        " const r = document.createRange(); r.selectNodeContents(el);"
        " return r.getBoundingClientRect().width; }))"
    )
    assert widest <= 18, (
        f"the widest glyph paints {widest:.1f}px inside an 18px column - it is overflowing, "
        "which no box measurement can see"
    )


def test_the_collapsed_rail_is_unaffected_by_the_icon_size(ui: Page) -> None:
    """64px is the tightest case: 23px of inner room for an 18px column.

    Measured with a FRESH catalog, because the collapse state is persisted - a run that reuses
    a catalog loads already-collapsed and the toggle expands it instead. That mistake produced
    a 232px "collapsed" reading during this work, which is why the state is asserted here rather
    than assumed from the click.
    """
    ui.click("#sidebar-toggle")
    expect(ui.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    ui.wait_for_timeout(400)  # the shell animates its columns over 160ms

    rail = ui.eval_on_selector("#sidebar", "el => +el.getBoundingClientRect().width.toFixed(1)")
    assert rail == 64, f"the collapsed rail is {rail}px, not 64px"

    # Painted ink against the row's real inner width. The 64px rail leaves 23px inside a
    # nav-item's padding, so this is the tightest place the glyph has to fit - and, as above,
    # the box alone cannot report a glyph that has outgrown it.
    fit = ui.evaluate(
        "() => { const rows = [...document.querySelectorAll('.nav-item')];"
        " const ink = rows.map(row => { const el = row.querySelector('.ico');"
        "   const r = document.createRange(); r.selectNodeContents(el);"
        "   return r.getBoundingClientRect().width; });"
        " const row = rows[0].getBoundingClientRect().width;"
        " const pad = parseFloat(getComputedStyle(rows[0]).paddingLeft) * 2;"
        " return {widest: Math.max(...ink), room: row - pad}; }"
    )
    assert fit["widest"] <= fit["room"], (
        f"the widest glyph paints {fit['widest']:.1f}px with only {fit['room']:.1f}px of room "
        "inside the collapsed rail"
    )


def test_the_collapse_chevron_is_on_the_type_scale(ui: Page) -> None:
    """Regression guard for the button this commit also touches.

    `.sidebar-toggle` itself carried no font-size and fell to the UA default 13.333px. Nothing
    visible depended on it - `.chevron` sets its own 18px and `.nav-label` is clipped to 1px -
    so this is hygiene, not a repaired defect, and it is recorded that way. What it prevents is
    a later visible child inheriting a size no token chose.
    """
    button = ui.eval_on_selector("#sidebar-toggle", "el => getComputedStyle(el).fontSize")
    assert button.endswith("px")
    assert not button.startswith("13.3"), (
        f"the toggle is back on the UA default ({button}); it must take a token"
    )

    chevron = ui.eval_on_selector(".sidebar-toggle .chevron", "el => getComputedStyle(el).fontSize")
    assert chevron == "18px", f"the chevron glyph is {chevron}, not the 18px it has always been"
