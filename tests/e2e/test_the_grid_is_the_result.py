"""After an organize, the photos ARE the result.

truestill has shipped as a photo organizer with **zero `<img>` elements**. Every complaint about
how it looks was downstream of that: a run finished and reported a column of numbers about
photographs the product never showed. This file asserts the fix as behaviour rather than as
markup - that a run draws its photos, that they come from the real route with real bytes, and
that the numbers now sit beneath them.

The lazy-loading decision is asserted here too, in the one place it can be: `loading="lazy"` on
every tile. A browser opens at most six connections per host over HTTP/1.1, so a grid that
requests forty-eight tiles at once serves six at a time. Native lazy loading spends that window
on tiles a person is actually looking at. Losing the attribute would not fail any other test and
would not look broken - it would just be slow, which is the failure nobody reports.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, expect

TESTID = "[data-testid='org-grid']"


def _completion(ui: Page, **overrides: Any) -> None:
    """Render a finished organize by handing `organizeCompletion` the server's own payload shape.

    Same seam `test_the_move_says_what_it_left.py` uses, and for the same reason: a real run is
    behind a typed-word confirm, and driving that would test the gate rather than the result.
    The end-to-end half - real bytes through the real route - is the last test in this file.
    """
    summary: dict = {
        "organized": 3,
        "photos": 3,
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 0,
        "bytes_saved": 0,
        "moved_by_copy": 3,
        "moved_in_place": 0,
        "failed": 0,
        "folders": {},
        "outcomes": {"organized": 3},
        "mode": "copy",
        "organized_sample": {
            "total": 3,
            # w/h per photo: Stage C makes the backend send these. Carried here first because
            # a row solver cannot lay out what it cannot measure, and measuring the loaded
            # image is too late - the grid would reflow as bytes land.
            "shown": [
                {"sha256": f"{i:064x}", "name": f"IMG_000{i}.jpg", **shape}
                for i, shape in enumerate(
                    [{"w": 4000, "h": 3000}, {"w": 3000, "h": 4000}, {"w": 4000, "h": 1824}]
                )
            ],
        },
    }
    summary.update(overrides)
    ui.evaluate(
        # THE PROPS ENTRY POINT. `#org-result` has one owner - the React island - so writing its
        # innerHTML from outside is either clobbered on the next render or, worse, survives
        # while the island believes it rendered nothing. That second case is not hypothetical:
        # it left this suite green while the row solver never ran, and only the panorama guard
        # noticed. The island is told what state to be in; it decides the DOM.
        "(s) => { window.organizeResult.set({ kind: 'complete', summary: s }); }",
        summary,
    )
    expect(ui.locator("#org-result .card")).to_be_visible()


def test_a_finished_run_draws_the_photos_it_organized(ui: Page) -> None:
    _completion(ui)
    assert ui.locator(f"{TESTID} img.tile").count() == 3, "a finished organize drew no photos"


def test_every_tile_asks_for_its_photo_by_content_and_carries_the_token(ui: Page) -> None:
    """An `<img>` cannot set `X-Truestill-Token`, so the tile URL must carry `?token=`. Without
    it every tile is a 403 and the grid renders as a wall of broken images."""
    _completion(ui)
    sources = ui.eval_on_selector_all(
        f"{TESTID} img.tile", "els => els.map(e => e.getAttribute('src'))"
    )
    assert sources, "no tiles rendered"
    for src in sources:
        assert src.startswith("/api/thumb/"), f"a tile did not address content: {src}"
        assert "token=" in src, f"a tile carried no token and will 403: {src}"


def test_the_tiles_load_lazily_rather_than_all_at_once(ui: Page) -> None:
    """THE CONNECTION-CAP DECISION, and the only assertion that can hold it.

    Six connections per host means forty-eight eager tiles queue eight deep. Nothing else in this
    suite would notice the attribute going missing: the grid would still be correct, still pass
    every other test here, and simply feel slow - the defect class that never gets reported.
    """
    _completion(ui)
    loading = ui.eval_on_selector_all(
        f"{TESTID} img.tile", "els => els.map(e => e.getAttribute('loading'))"
    )
    assert loading, "no tiles rendered"
    assert set(loading) == {"lazy"}, f"tiles are not lazy: {sorted(set(loading))}"


def test_the_tiles_decode_off_the_main_thread_and_reserve_their_box(ui: Page) -> None:
    """The other two attributes on a lazy tile, both added by a mutation that killed nothing.

    **Asserted as mechanism rather than as observed state, and that is deliberate rather than
    lazy.** §4's fiftieth member forbids asserting a state some *other* mechanism also produces;
    it does not require inventing a downstream observable that does not exist. Neither of these
    has one in a normal page:

    * `decoding="async"` moves the decode off the main thread. The visible result is a page that
      does not jank while forty-eight tiles arrive - not something a DOM assertion can see.
    * `width`/`height` let the browser reserve each box before any CSS or bytes arrive.

    ⚠ **`width`/`height` USED to be decorative and are now load-bearing, which is why this
    docstring changed in the commit that inverted the square guards.** While every tile was
    `--tile-size` square, the stylesheet fixed the box outright and these attributes mattered
    only in the window before CSS applied. Under an aspect-preserving layout they carry each
    photograph's TRUE SHAPE, which is the only thing a row can be laid out from before the bytes
    arrive. Losing them now does not cost a millisecond of reflow; it costs the layout.

    Both are real, both are invisible when lost, and the honest guard for them is their presence.
    """
    _completion(ui)
    attrs = ui.eval_on_selector_all(
        f"{TESTID} img.tile",
        "els => els.map(e => ({d: e.getAttribute('decoding'),"
        " w: e.getAttribute('width'), h: e.getAttribute('height')}))",
    )
    assert attrs, "no tiles rendered"
    assert {a["d"] for a in attrs} == {"async"}, "a tile decodes on the main thread"
    assert all(a["w"] and a["h"] for a in attrs), (
        "a tile declares no intrinsic size, so its box cannot be reserved before CSS applies"
    )


def test_every_tile_keeps_its_photograph_s_shape_before_the_photo_arrives(ui: Page) -> None:
    """A photograph is drawn in the shape it was taken in, and the box holds before the bytes do.

    **This replaces `test_every_tile_is_square_whether_or_not_its_photo_arrives`, and the
    replacement is the product's thesis rather than a style preference.** truestill's promise is
    that your originals are untouched; the only view of a photograph it had cropped every one of
    them to a square. See `docs/organize-grid-design.md`.

    Asserted with tiles that deliberately never load (the shas are fabricated), because an
    unloaded `<img>` is where a reserved box is easiest to lose: with no intrinsic size and no
    stylesheet height it collapses to nothing and the grid reflows as each photo arrives. That
    half is unchanged from the square guard - what changed is WHICH box is correct.

    The mechanism is now the `width`/`height` attributes carrying the photograph's true shape,
    which is why the docstring above them changed in this same commit.
    """
    _completion(ui)
    boxes = ui.eval_on_selector_all(
        f"{TESTID} img.tile",
        "els => els.map(e => { const r = e.getBoundingClientRect();"
        " return {w: Math.round(r.width), h: Math.round(r.height),"
        "         aw: Number(e.getAttribute('width')), ah: Number(e.getAttribute('height'))}; })",
    )
    assert boxes, "no tiles rendered"

    flattened = [b for b in boxes if not b["aw"] or not b["ah"]]
    assert not flattened, (
        f"a tile declares no intrinsic shape, so nothing can lay it out before it loads: "
        f"{flattened}"
    )
    # 2% tolerance: sub-pixel rounding at a fractional row height, not a squashed photograph.
    wrong = [
        b
        for b in boxes
        if abs((b["w"] / b["h"]) - (b["aw"] / b["ah"])) / (b["aw"] / b["ah"]) > 0.02
    ]
    assert not wrong, (
        f"tiles are drawn in a shape their photograph is not: {wrong}. Every tile keeping the "
        "same shape is the square grid this replaced; a photograph is drawn as it was taken."
    )

    shapes = {round(b["w"] / b["h"], 2) for b in boxes}
    assert len(shapes) > 1, (
        f"every tile rendered the same shape ({shapes}), so this guard would pass against the "
        "square grid it exists to forbid. The fixture must mix portrait and landscape."
    )


def test_a_photograph_is_never_cropped_to_fit_its_tile(ui: Page) -> None:
    """`object-fit` must not crop, because there is no longer anything to crop TO.

    **This replaces `test_a_photo_is_cropped_to_the_square_and_never_stretched`.** That guard
    existed to keep `cover` on a square tile: given a box the photo did not fit, `cover` cropped
    to the centre and the default `fill` squashed, and cropping was the lesser harm. Under an
    aspect-preserving layout the box IS the photo's shape, so `cover` has nothing to trim and its
    presence would mean the box and the photograph have disagreed somewhere.

    `fill` is the CSS default and is correct here for the same reason `cover` was correct before:
    when the box already matches the intrinsic ratio, `fill` scales and does not distort. What is
    forbidden is `cover`, which silently hides a disagreement instead of showing it.
    """
    _completion(ui)
    fits = ui.eval_on_selector_all(
        f"{TESTID} img.tile", "els => els.map(e => getComputedStyle(e).objectFit)"
    )
    assert fits, "no tiles rendered"
    assert "cover" not in set(fits), (
        f"tiles paint with object-fit {sorted(set(fits))}. `cover` CROPS - it is how the square "
        "grid hid the mismatch between a photograph and its tile, and an aspect-preserving "
        "layout has no mismatch to hide."
    )


def test_a_content_id_is_escaped_into_its_url_by_the_function_that_builds_it(ui: Page) -> None:
    """`resultGrid` is called with server-built payloads today, so no reachable input needs
    encoding - which is exactly why a mutation deleting `encodeURIComponent` killed nothing.

    §4's thirty-first member says an unfired mutation is either a missing guard or dead code, and
    which one it is decides between a test and a deletion. This is the first: the call is not
    dead, it is the correct way to put a value into a URL, and the fix is to hold the FUNCTION to
    that contract at its own boundary instead of relying on every future caller to be careful.
    Tested by calling it directly, since the payload type cannot express a hostile id.
    """
    src = ui.evaluate(
        """() => {
            const html = resultGrid({total: 1, shown: [{sha256: 'a/../b?x=1&y', name: 'n.jpg'}]});
            const el = document.createElement('div');
            el.innerHTML = html;
            return el.querySelector('img.tile').getAttribute('src');
        }"""
    )
    assert "a/../b" not in src, f"a separator went into the URL path unescaped: {src}"
    assert "a%2F..%2Fb%3Fx%3D1%26y" in src, f"the content id was not percent-encoded: {src}"


#: The wall, and it is arithmetic rather than taste: a thumbnail is `THUMB_PX` = 320 on its long
#: edge, so a 16:9 photograph runs out of pixels at exactly 320 / (16/9) = 180px of row height -
#: and **20.5% of the maintainer's 4,108-photo corpus is 16:9 or wider**. The brief targets 172,
#: which buys 35% more photograph area than the old 148px tile for 0.07 percentage points of
#: extra softness. `docs/organize-grid-design.md`.
ROW_HEIGHT_CEILING = 178


@pytest.mark.parametrize("width", [1440, 1280, 900, 760, 420])
def test_a_row_is_drawn_near_the_height_its_thumbnails_were_made_for(ui: Page, width: int) -> None:
    """`THUMB_PX` is 320 because a row is about 172 at 2x, and nothing enforces that pairing.

    **This replaces `test_a_tile_is_drawn_near_the_size_its_thumbnail_was_made_for`, which
    asserted a WIDTH window of 130-220px.** That was correct while every tile was square, so
    width and height were the same number. Under an aspect-preserving layout width is the free
    dimension - a 16:9 tile at 172px tall is 306px wide and a portrait is 129px - so the old
    window would fail on correct output in both directions. **Height is the invariant a row
    shares; width is what the photograph decides.**

    The upper bound is the one that matters and it is not a preference: past `ROW_HEIGHT_CEILING`
    a 16:9 photograph is being upscaled from a thumbnail that does not have the pixels.
    """
    ui.set_viewport_size({"width": width, "height": 900})
    _completion(ui)
    heights = ui.eval_on_selector_all(
        f"{TESTID} img.tile", "els => els.map(e => Math.round(e.getBoundingClientRect().height))"
    )
    assert heights, "no tiles rendered"

    too_tall = [h for h in heights if h > ROW_HEIGHT_CEILING]
    assert not too_tall, (
        f"at {width}px a tile is {too_tall}px tall against a {ROW_HEIGHT_CEILING}px ceiling. "
        "Past it a 16:9 photograph is upscaled from a 320px thumbnail that has no more pixels."
    )
    # ⚠ THE LOWER BOUND ONLY MEANS SOMETHING WHERE THERE IS ROOM, and asserting it everywhere
    # was wrong: at 760px three photographs summing 4.28 aspects fill their row at 95px, which is
    # the solver working, not failing. A row's height is `(available - gaps) / sum(aspects)`, so a
    # narrow panel holding wide photographs MUST solve short or the row would not fill. Guard 1 in
    # `test_the_row_solver.py` is what actually forbids postage stamps - a row that leaves slack.
    if width >= 1280:
        too_short = [h for h in heights if h < 120]
        assert not too_short, (
            f"at {width}px a tile is {too_short}px tall with room to spare, so most of the served "
            "thumbnail is thrown away on a screen with space for photographs"
        )


def test_no_tile_is_drawn_outside_the_card_that_holds_it(ui: Page) -> None:
    """A grid of fixed-size images is the classic way to lose content off the right edge, and the
    narrowest panel is where it happens.

    **THE FIRST VERSION OF THIS TEST WAS WORTHLESS AND A MUTATION FOUND IT.** It asked whether the
    DOCUMENT scrolled sideways. Replacing the responsive track with `repeat(6, 148px)` at a 420px
    viewport left all fourteen tests green - because the page does not scroll: something upstream
    clips it, so the overflow is silent. Measured, that mutant put the widest tile's right edge at
    **969px against a card ending at 404**. Five of the six columns were simply not on screen.

    So the assertion is the property a person experiences - a tile inside the card that contains
    it - rather than the symptom a different layout happens to produce.

    ⚠ **KEPT UNCHANGED THROUGH THE ASPECT INVERSION, and it matters MORE now, not less.** Under
    the square grid every tile was 148px and the only way to escape was a broken track. Under an
    aspect-preserving layout **a single wide photograph is wider than the card at a narrow
    viewport all by itself** - a 16:9 frame at a 172px row height is 306px, against a card that
    ends at 404px minus padding. This is the guard that catches a panorama hanging off the edge,
    and it needed no rewriting to do it, which is the argument for asserting what a person
    experiences rather than what a layout produces.
    """
    ui.set_viewport_size({"width": 420, "height": 900})
    _completion(
        ui,
        organized_sample={
            "total": 1,
            # The widest real photograph in the corpus is 4.348:1. At any sane row height it is wider
            # than a 420px panel, so if anything can escape the card, this can.
            "shown": [{"sha256": f"{0:064x}", "name": "PANO.jpg", "w": 4348, "h": 1000}],
        },
    )
    escaping = ui.evaluate(
        """() => {
            const grid = document.querySelector("[data-testid='org-grid']");
            const card = grid.closest('.card');
            const rect = card.getBoundingClientRect();
            const limit = rect.right - parseFloat(getComputedStyle(card).paddingRight);
            return [...grid.querySelectorAll('img.tile')]
                .map((t) => Math.round(t.getBoundingClientRect().right))
                .filter((right) => right > Math.round(limit) + 1);
        }"""
    )
    assert not escaping, f"{len(escaping)} tiles render past the card edge, at x={escaping}"


def test_nothing_but_the_headline_comes_before_the_photos(ui: Page) -> None:
    """ "The grid IS the result" is an ordering claim, so it is asserted as one.

    **The first version of this test asserted the grid preceded `.tally`, and it passed while the
    card still read as a report with photos in the middle of it.** It was true and insufficient:
    the grid also had a `sub` line above it, so the sequence was headline, prose, photos, numbers,
    chips, warnings - a paragraph inside a report, which is what the plan's constraint existed to
    prevent. Ordering against one later element cannot see what sits in between.

    So the claim is now the whole prefix: **between the headline and the grid there is nothing.**
    That is checkable, it is what "the grid is the result" means, and it fails for anything
    inserted above the photos rather than only for the one element that used to be below them.
    """
    _completion(ui)
    between = ui.evaluate(
        """() => {
            const grid = document.querySelector("[data-testid='org-grid']");
            const headline = document.querySelector('#org-result .headline');
            if (!grid || !headline) return null;
            const out = [];
            for (let el = headline.nextElementSibling; el && el !== grid; el = el.nextElementSibling) {
                out.push(el.className || el.tagName);
            }
            return out;
        }"""
    )
    assert between is not None, "the card is missing either its headline or its grid"
    assert between == [], f"these sit between the headline and the photos: {between}"


def test_the_numbers_are_one_line_beneath_the_photos(ui: Page) -> None:
    """The other half of the same constraint: the run's numbers are supporting detail here.

    Not `.tally` - a two-column block that reads as the main event - and not `.metrics`, whose
    3xl numbers are the Stats dashboard's whole point. On this card the photos are the result and
    the counts are a caption, so they are one muted line, positioned after the grid.
    """
    _completion(ui)
    line = ui.locator("#org-result .result-numbers")
    expect(line).to_have_count(1)
    assert ui.locator("#org-result .tally").count() == 0, (
        "the two-column number block is back above the photos"
    )

    after = ui.evaluate(
        """() => {
            const grid = document.querySelector("[data-testid='org-grid']");
            const line = document.querySelector('#org-result .result-numbers');
            return !!(grid.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING);
        }"""
    )
    assert after, "the numbers still come before the photos"


def test_a_big_grid_is_one_row_until_it_is_asked_to_open(ui: Page) -> None:
    """A SCALE DEFECT, NOT A PREFERENCE, and the thing it buries is the reason.

    `GRID_SAMPLE_LIMIT` is 48. Expanded, that is eight rows and roughly 1,250px of photographs
    sitting between the headline and everything the card has to say - the tally, the folder chips,
    and **every warning**. "N files now exist in only one place" is precisely what must not be the
    thing a person scrolls past to reach.

    So the grid opens at one row and says how many more there are. Asserted as a rendered height
    rather than a class name: a class is our word for the state, the height is the state.
    """
    shown = [{"sha256": f"{i:064x}", "name": f"IMG_{i}.jpg"} for i in range(48)]
    _completion(ui, organized_sample={"total": 48, "shown": shown}, organized=48, photos=48)

    grid = ui.locator(TESTID)
    box = grid.bounding_box()
    assert box is not None
    tile = ui.eval_on_selector(
        f"{TESTID} img.tile", "e => Math.round(e.getBoundingClientRect().height)"
    )
    assert round(box["height"]) <= tile + 2, (
        f"48 photos rendered {round(box['height'])}px tall, not the {tile}px of a single row - "
        "the tally, the chips and the warnings are below the fold"
    )
    expect(ui.locator("#org-result .grid-toggle")).to_be_visible()


def test_show_all_opens_the_grid_and_says_so_to_a_screen_reader(ui: Page) -> None:
    """The control has to actually work, and has to be a control - not a styled div."""
    shown = [{"sha256": f"{i:064x}", "name": f"IMG_{i}.jpg"} for i in range(48)]
    _completion(ui, organized_sample={"total": 48, "shown": shown}, organized=48, photos=48)

    toggle = ui.locator("#org-result .grid-toggle")
    assert ui.eval_on_selector("#org-result .grid-toggle", "e => e.tagName") == "BUTTON"
    expect(toggle).to_have_attribute("aria-expanded", "false")

    collapsed = ui.locator(TESTID).bounding_box()
    toggle.click()
    expanded = ui.locator(TESTID).bounding_box()

    assert collapsed is not None
    assert expanded is not None
    assert expanded["height"] > collapsed["height"] * 2, (
        f"the grid did not open: {round(collapsed['height'])}px -> {round(expanded['height'])}px"
    )
    expect(toggle).to_have_attribute("aria-expanded", "true")


def test_the_show_all_control_reads_as_interactive(ui: Page) -> None:
    """A control that looks like a caption is a control nobody presses.

    This first shipped as `.btn-ghost`: transparent on `--fg-secondary`, which measured
    `rgb(95, 87, 76)` beside a caption at `rgb(28, 26, 23)`. It rendered GREYER than the static
    text next to it - recessive where it needed to be inviting - and read as another line of
    prose under the photos.

    Compared against the `--accent` token rather than a literal colour, so this asserts
    membership of the design system: it stays true through a theme change, and it is the same
    treatment `details.more > summary` already uses for show-more elsewhere in this app.
    """
    shown = [{"sha256": f"{i:064x}", "name": f"IMG_{i}.jpg"} for i in range(48)]
    _completion(ui, organized_sample={"total": 48, "shown": shown}, organized=48, photos=48)

    colours = ui.evaluate(
        """() => {
            const probe = document.createElement('span');
            probe.style.color = 'var(--accent)';
            document.body.appendChild(probe);
            const accent = getComputedStyle(probe).color;
            probe.remove();
            return {
                accent,
                toggle: getComputedStyle(document.querySelector('.grid-toggle')).color,
                caption: getComputedStyle(document.querySelector('.result-numbers')).color,
            };
        }"""
    )
    assert colours["toggle"] == colours["accent"], (
        f"the control renders {colours['toggle']}, not the accent {colours['accent']}"
    )
    assert colours["toggle"] != colours["caption"], "the control is the same colour as the caption"


def test_a_grid_that_already_fits_offers_no_control(ui: Page) -> None:
    """Cry-wolf half. A handful of photos cannot bury anything, so a "show all 3" under three
    photos is noise - and noise is what teaches people to stop reading the controls."""
    _completion(ui)  # three photos
    assert ui.locator("#org-result .grid-toggle").count() == 0
    assert "is-collapsed" not in (ui.eval_on_selector(TESTID, "e => e.className") or "")


def test_tiles_share_a_row_height_and_are_free_in_width(ui: Page) -> None:
    """One height per row; width is whatever the photograph is.

    **This replaces `test_the_tiles_are_a_fixed_size_that_wraps_rather_than_stretching`**, which
    asserted `set(widths) == {148}` - a singleton set, which an aspect-preserving layout
    contradicts by definition.

    What survives from it is the real property that guard was protecting: the row must not
    STRETCH its tiles to fill the width. It was named for the mutation
    `minmax(var(--tile-size), 1fr)`, which made the grid read as a torn strip. Under the new
    layout a tile has no fixed width to stretch, so the equivalent failure is a tile whose drawn
    shape stops matching its photograph - which
    `test_every_tile_keeps_its_photograph_s_shape_before_the_photo_arrives` owns, and which is
    why `scripts/mutation_matrix.py`'s stretch mutant is RETIRED rather than ported.
    """
    for width in (1440, 1100, 760):
        ui.set_viewport_size({"width": width, "height": 900})
        _completion(ui)
        boxes = ui.eval_on_selector_all(
            f"{TESTID} img.tile",
            "els => els.map(e => { const r = e.getBoundingClientRect();"
            " return {w: Math.round(r.width), h: Math.round(r.height),"
            "         top: Math.round(r.top)}; })",
        )
        assert boxes, f"no tiles rendered at {width}px"

        by_row: dict[int, list[int]] = {}
        for box in boxes:
            by_row.setdefault(box["top"], []).append(box["h"])
        for top, row_heights in by_row.items():
            assert max(row_heights) - min(row_heights) <= 1, (
                f"at {width}px the row at y={top} mixes heights {sorted(set(row_heights))}; "
                "photographs in one row share a height or the row is not a row"
            )

        widths = {b["w"] for b in boxes}
        assert len(widths) > 1, (
            f"at {width}px every tile is {widths} wide, which is the fixed-size square grid this "
            "replaced. Width is the photograph's to decide."
        )


def test_the_gutters_are_even_across_a_row(ui: Page) -> None:
    """THE TRACK AND THE TILE ARE TWO DIFFERENT MECHANISMS, and only one was covered.

    A mutation restoring `minmax(var(--tile-size), 1fr)` killed nothing, which looked like a
    missing guard and was: the tiles stayed 148px because `.tile` sets its own width, so the
    fixed-size test could not see it. What changes is the TRACK - it stretches, the tile sits at
    its start, and the visible gaps between photos become uneven while every tile is still the
    right size. That is the ragged look the fixed track exists to prevent, and it is invisible to
    any assertion about tile width.

    Measured as the distance from one tile's right edge to the next tile's left edge, along one
    row, which is the gutter a person actually sees.

    ⚠ **THIS GUARD SURVIVED THE ASPECT INVERSION, and that was a decision rather than an
    oversight.** It was at risk: a layout that justified rows by redistributing slack INTO the
    gutters would make `gutters[0] == declared` exactly the thing the design intends to violate.
    The brief chose otherwise - photographs keep their true widths and the row does not stretch -
    so the declared gap stays the visible gap and this comparison keeps its full force. If a row
    solver is ever added that varies gutters, this is the guard it has to argue with first.

    Row grouping below assumes tiles in a row share a `top`, which the height guard in
    `test_tiles_share_a_row_height_and_are_free_in_width` now pins independently.

    ⚠ **AND COMPARED AGAINST THE DECLARED `gap`, because evenness alone does not catch it.** The
    first version of this test only asserted the gutters were equal to each other, and the
    stretch mutation walked straight through: stretched tracks are all the SAME width, so the
    gutters stay perfectly even and simply stop matching the gap that was declared. The visible
    gutter must equal the declared one, or the stylesheet's number is decorative.
    """
    ui.set_viewport_size({"width": 1440, "height": 900})
    shown = [{"sha256": f"{i:064x}", "name": f"IMG_{i}.jpg"} for i in range(12)]
    _completion(ui, organized_sample={"total": 12, "shown": shown}, organized=12, photos=12)

    measured = ui.eval_on_selector(
        TESTID,
        """el => {
            const r = [...el.querySelectorAll('img.tile')].map(e => e.getBoundingClientRect());
            const out = [];
            for (let i = 1; i < r.length; i++) {
                if (Math.abs(r[i].top - r[i - 1].top) < 1) out.push(Math.round(r[i].left - r[i - 1].right));
            }
            return {gutters: out, declared: Math.round(parseFloat(getComputedStyle(el).columnGap))};
        }""",
    )
    gutters, declared = measured["gutters"], measured["declared"]
    assert gutters, "no two tiles shared a row"
    assert len(set(gutters)) == 1, f"the gutters along a row are uneven: {gutters}"
    assert gutters[0] == declared, (
        f"tiles sit {gutters[0]}px apart but the stylesheet declares a {declared}px gap - "
        "the tracks are stretching and the declared gutter is decorative"
    )


def test_the_frames_touch_at_a_hairline_and_are_not_rounded(ui: Page) -> None:
    """Frames on a contact sheet butt together and have square corners.

    **This inverts `test_the_tiles_are_separated_and_rounded_enough_to_read_as_tiles`, which
    asserted `gap >= 12` and `border-radius >= 10`.** ⚠ **It was not on the plan's list of four
    inversions, and that was an oversight found by running the guards against the layout rather
    than by reading them** - the census that produced the list asked which guards were
    aspect-coupled, and this one is not. It is coupled to the *values* the brief changes.

    **The values it asserted were themselves measured**, at `app.css:794`: 8px and 6px "rendered
    correctly and too small to read as separate tiles at this size. One step up each." That
    finding held for UNIFORM SQUARES, where the gutter is the only thing separating one tile from
    the next. With true aspects a portrait beside a panorama is legible at 4px, because the shapes
    do the separating.

    ⚠ **The retreat is `--space-2` 8px and `--corner-sm` 6px** - the values that measurement
    actually produced, not today's 12px/10px and not a number someone likes the look of. See
    `docs/organize-grid-design.md`.
    """
    _completion(ui)
    style = ui.eval_on_selector(
        f"{TESTID}",
        """el => { const g = getComputedStyle(el);
            const t = el.querySelector('img.tile');
            return {gap: parseFloat(g.gap || g.rowGap),
                    radius: parseFloat(getComputedStyle(t).borderTopLeftRadius)}; }""",
    )
    assert style["gap"] <= 4, (
        f"the gutter is {style['gap']}px; frames on a contact sheet touch at a hairline, and "
        "12px of ground between rounded tiles is a photo gallery"
    )
    assert style["radius"] == 0, (
        f"a frame has a {style['radius']}px corner radius; a photograph is a rectangle"
    )


def test_a_truncated_grid_says_how_many_it_is_not_showing(ui: Page) -> None:
    """The rule every other capped list here obeys. A grid silently showing 48 of 200 reads as
    "this is what you organized"."""
    shown = [{"sha256": f"{i:064x}", "name": f"IMG_{i}.jpg"} for i in range(48)]
    _completion(ui, organized_sample={"total": 200, "shown": shown}, organized=200, photos=200)

    expect(ui.locator("#org-result")).to_contain_text("Showing 48 of 200 photos")


def test_a_run_of_videos_shows_no_grid_and_promises_nothing(ui: Page) -> None:
    """Real work with nothing to draw. An empty grid frame, or an "and 40 more" over a blank
    space, would both be claims about photos that were never organized."""
    _completion(
        ui,
        photos=0,
        videos=40,
        organized=40,
        organized_sample={"total": 0, "shown": []},
    )

    assert ui.locator(TESTID).count() == 0, "an empty grid frame rendered anyway"
    expect(ui.locator("#org-result")).not_to_contain_text("Showing")
    expect(ui.locator("#org-result")).to_contain_text("40 files organized")


def test_a_tile_name_cannot_inject_markup(ui: Page) -> None:
    """`name` is a user's file name and reaches an attribute. `esc` is what stands between the
    two, and a test that does not try is not evidence that it works."""
    _completion(
        ui,
        organized_sample={
            "total": 1,
            "shown": [{"sha256": "a" * 64, "name": '"><img src=x onerror=alert(1)>evil.jpg'}],
        },
    )

    assert ui.locator(f"{TESTID} img").count() == 1, "a file name created a second element"
    alt = ui.eval_on_selector(f"{TESTID} img.tile", "e => e.getAttribute('alt')")
    assert alt.startswith('"><img'), f"the name was not carried through verbatim: {alt!r}"


# ------------------------------------------------------------ the end-to-end half


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
def test_organizing_real_photos_puts_real_pixels_on_the_screen(
    ui: Page, tmp_path: Path, library
) -> None:
    """The whole point, with nothing mocked: organize a folder, and the photos appear.

    Asserted through `naturalWidth`, which is non-zero only when the browser actually **decoded**
    bytes it fetched. A broken `<img>` still renders an element, still has a `src`, and still
    satisfies every structural assertion above - so this is the one that proves the route, the
    token, the cache and the decode all work together on a real run.
    """
    source = library(4, name="Pictures")
    destination = tmp_path / "TruestillLibrary" / "Output"

    ui.fill("#org-source", str(source))
    ui.fill("#org-dest", str(destination))
    ui.click("#org-preview")
    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=30_000)
    ui.click("#org-dedup")
    expect(ui.locator("#org-confirm [data-typed-confirm]")).to_be_visible(timeout=30_000)
    ui.fill("#org-confirm [data-typed-confirm]", "copy")
    ui.click("#org-confirm [data-typed-go]")

    expect(ui.locator("#org-result")).to_contain_text("4 files organized", timeout=60_000)
    tiles = ui.locator(f"{TESTID} img.tile")
    expect(tiles).to_have_count(4)

    # `loading="lazy"` means a tile below the fold may not have been fetched yet, which is the
    # feature working. Scroll it into view first, then require pixels.
    tiles.first.scroll_into_view_if_needed()
    ui.wait_for_function(
        "() => { const i = document.querySelector(\"[data-testid='org-grid'] img.tile\");"
        " return i && i.complete && i.naturalWidth > 0; }",
        timeout=30_000,
    )
    width = ui.eval_on_selector(f"{TESTID} img.tile", "e => e.naturalWidth")
    assert width > 0, "the tile element exists but no image was decoded"
    assert width <= 320, f"a full-size original was served as a thumbnail: {width}px"
