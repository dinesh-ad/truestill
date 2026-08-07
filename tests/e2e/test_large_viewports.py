"""Large viewports and multiple monitors - what the layout does past 1920px.

MEASURED ON THE REAL HARDWARE (mutter `GetCurrentState`, 2026-08-06), because the panel's
native resolution is not what CSS sees and reasoning from "it's a 4K" gets it wrong:

    eDP-1   AUO laptop         1920x1080 @ scale 1.00  ->  1920 CSS px, dPR 1.00
    HDMI-1  BenQ PD2720U (4K)  3840x2160 @ scale 1.25  ->  3072 CSS px, dPR 1.25
    DP-3    DELL S2721DS (QHD) 2560x1440 @ scale 1.00  ->  2560 CSS px, dPR 1.00

So the widest CSS viewport in play is 3072, not 3840 - and the 4K panel and the QHD panel are
BOTH wider in CSS px than the laptop, which is where the dead space showed. Before this commit,
with the content column capped at 1080:

    1920 CSS ->  144px dead each side   (fine)
    2560 CSS ->  464px dead each side
    3072 CSS ->  720px dead each side

A residual gutter at 3072 is deliberate and is NOT a bug: the alternative to a margin beside a
1600px column is a 2400px-wide text input. What is capped is the column, not the page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / "packages/truestill-app/src/truestill_app/static/tokens.css"

LAPTOP = {"width": 1920, "height": 1080}
QHD = {"width": 2560, "height": 1440}
UHD = {"width": 3072, "height": 1728}  # the BenQ at its actual 1.25 scale
#: The Dell rotated. Not a phone: 1440 CSS px wide is wider than most laptops.
PORTRAIT_QHD = {"width": 1440, "height": 2560}
PORTRAIT_FHD = {"width": 1080, "height": 1920}


def _layout(ui: Page) -> dict[str, float]:
    return ui.evaluate(
        "() => { const s = document.querySelector('.screen.active');"
        " const main = document.querySelector('.main');"
        " const panel = document.querySelector('#panel');"
        " const sr = s.getBoundingClientRect(), mr = main.getBoundingClientRect();"
        " const shown = panel && getComputedStyle(panel).display !== 'none';"
        " return { content: sr.width, main: mr.width,"
        "   panel: shown ? panel.getBoundingClientRect().width : 0,"
        "   gutter: (mr.width - sr.width) / 2,"
        "   overflow: document.body.scrollWidth - document.body.clientWidth }; }"
    )


def _at(ui: Page, size: dict[str, int]) -> dict[str, float]:
    ui.set_viewport_size(size)
    ui.wait_for_timeout(200)
    return _layout(ui)


def _with_library(ui: Page) -> None:
    """Give the resting panel something to say. It is `display: none` while empty."""
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "files": 2269,
                    "photos": 2100,
                    "videos": 169,
                    "audio": 0,
                    "bytes": 6_650_000_000,
                    "by_format": {},
                    "places": 2,
                    "single_copy": 400,
                    "files_no_copy": 69,
                    "files_one_copy": 400,
                    "redundancy_floor": 0,
                    "files_on_a_drive": 2200,
                    "held_floor": 1,
                    "library_path": "/media/BackupA",
                    "backup_path": "/media/BackupB",
                    "drives": [],
                    "custody": {},
                    "catalog_path": "/tmp/c.sqlite",
                    "catalog_presence": "ready",
                    "catalog_detail": "",
                    "catalog_tone": "info",
                }
            ),
        ),
    )
    ui.reload()
    ui.wait_for_selector(".nav-item")


# ------------------------------------------------------------------- the dead space itself


def test_the_content_column_uses_a_qhd_screen(ui: Page) -> None:
    """464px of empty page each side is the complaint this commit answers.

    THE CRITERION IS A SHARE OF THE TRACK, NOT A PIXEL COUNT, and I replaced my own first
    threshold to get here: a flat "<= 260px dead" is arbitrary, and it fails at 2560 for a
    reason that is not a defect - with no panel showing there are only two columns, so the same
    1600px column leaves more beside it. What is wrong is a column dwarfed by its own page; 60%
    of the track is the line, and beyond it the answer is the PANEL, not a wider column.
    """
    got = _at(ui, QHD)

    assert got["content"] >= 1500, f"content is only {got['content']:.0f}px on a 2560px screen"
    assert got["content"] / got["main"] >= 0.6, (
        f"the column is {got['content'] / got['main']:.0%} of the track at 2560"
    )


def test_the_content_column_uses_the_4k_panel_at_its_real_scale(ui: Page) -> None:
    """3072 CSS px, not 3840 - the panel runs at scale 1.25.

    Only the absolute floor here. At 3072 with no panel the column is ~56% of the track, and
    that is the honest worst case: an EMPTY library, which is also the case with least on
    screen. Once the panel has anything to say it takes a third column and the share rises.
    """
    got = _at(ui, UHD)

    assert got["content"] >= 1500, f"content is only {got['content']:.0f}px on a 3072px screen"


def test_a_gutter_still_exists_and_that_is_the_point(ui: Page) -> None:
    """CRY-WOLF HALF, and the defence of the ceiling. Filling 3072px with one column would put
    a 2400px input on screen, which is worse than the margin. The column is capped; the page
    is not."""
    got = _at(ui, UHD)

    assert got["content"] <= 1700, f"the column grew to {got['content']:.0f}px - forms get absurd"
    assert got["gutter"] > 0


def test_the_laptop_is_unchanged_in_kind(ui: Page) -> None:
    """1920 was never the problem: 144px each side already read as breathing room."""
    got = _at(ui, LAPTOP)

    assert got["overflow"] <= 2
    assert got["content"] >= 1200, got


# ------------------------------------------------------------- prose keeps its measure


def test_prose_stays_at_its_measure_however_wide_the_column_gets(ui: Page) -> None:
    """The 760px column existed to protect prose; that constraint moved onto the TEXT when the
    column first grew, and widening it again must not undo that.

    **Measured in `ch`, never in pixels, and that is the whole point.** A readable measure is a
    number of CHARACTERS per line - which is what `ch` means and what `max-width: 56ch` says -
    so a pixel threshold is a proxy for it that holds only while the font does. This assertion
    used `<= 600` and had been red on CI since 2026-08-06 at **641.3125px**, because `1ch` is
    the width of the font's `0` glyph and nothing in the sans stack
    (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", ...`) is bundled:

        this machine  1ch = 10.2812px -> 56ch = 575.75px  (passed)
        CI runner     1ch = 11.4520px -> 56ch = 641.31px  (failed)
        uncapped at UHD                              ~140ch

    Both renders were CORRECT - 641px really is a 56-character line in that face. The test was
    asserting the environment's fonts, not the product, which is `ENGINEERING_STANDARD.md` §4's
    tenth member on the face §7 never bundled. Dividing by the element's own `ch` asks the same
    question the stylesheet asks, so it is font-independent by construction.
    """
    _at(ui, UHD)

    measured = ui.eval_on_selector(
        ".screen.active .lede",
        """el => {
            const probe = document.createElement('span');
            probe.style.cssText = 'position:absolute;visibility:hidden;width:1ch';
            el.appendChild(probe);
            const ch = probe.getBoundingClientRect().width;
            probe.remove();
            return {px: el.getBoundingClientRect().width, ch};
        }""",
    )
    characters = measured["px"] / measured["ch"]
    assert characters <= 57, (
        f"the lede runs to {characters:.0f} characters ({measured['px']:.0f}px at "
        f"{measured['ch']:.2f}px/ch) - that is not a readable measure"
    )
    assert characters >= 40, (
        f"the lede is only {characters:.0f} characters wide - it is not filling to its cap, "
        "so this test is measuring a collapsed element rather than the constraint"
    )


def test_a_table_may_take_the_whole_column(ui: Page) -> None:
    """Measured: a Find row with a realistic event-folder path wants ~1030px, which the old
    1080 cap only just cleared and a longer event name would not. Controls and tables take the
    width; prose does not."""
    _at(ui, UHD)
    ui.click('.nav-item[data-screen="settings"]')
    ui.wait_for_timeout(200)

    table = ui.eval_on_selector("#layout-preview", "el => el.getBoundingClientRect().width")
    card = ui.eval_on_selector(
        "#layout-preview", "el => el.closest('.card').getBoundingClientRect().width"
    )
    assert table > 900, f"the table is only {table:.0f}px wide inside a {card:.0f}px card"


# --------------------------------------------------------------------- the panel scales


def test_the_panel_grows_on_a_wide_screen_but_stays_bounded(ui: Page) -> None:
    """The panel has to be MADE to render. It is `display: none` while empty, so without a
    library-status payload every assertion here reads 0 and passes whatever the CSS says - which
    is how the first version of this test survived its own mutation."""
    _with_library(ui)
    ui.set_viewport_size(UHD)
    ui.wait_for_timeout(250)
    wide = _layout(ui)
    narrow = _at(ui, {"width": 1400, "height": 900})

    assert wide["panel"] >= 380, f"the panel stayed at {wide['panel']:.0f}px on a 3072 screen"
    assert wide["panel"] <= 460, f"the panel grew to {wide['panel']:.0f}px"
    assert narrow["panel"] >= 320, f"the panel fell to {narrow['panel']:.0f}px below its floor"


def test_the_column_and_the_panel_share_a_wide_screen_sensibly(ui: Page) -> None:
    """With three columns the share rises: the panel is the answer to width, not a wider column."""
    _with_library(ui)
    got = _at(ui, UHD)

    assert got["panel"] > 0, "the panel did not render, so this asserts nothing"
    assert got["content"] / got["main"] >= 0.6, (
        f"the column is {got['content'] / got['main']:.0%} of the track beside a panel"
    )


def test_the_panel_threshold_did_not_move(ui: Page) -> None:
    """1336 = rail 232 + a comfortable 760 column + a 320 panel. The panel's MINIMUM is still
    320, so the number that threshold was derived from is unchanged."""
    ui.set_viewport_size({"width": 1335, "height": 900})
    ui.wait_for_timeout(200)
    expect(ui.locator("#panel")).to_be_hidden()


# ------------------------------------------------------- fluid type that still obeys the root


def _text_tokens() -> dict[str, str]:
    body = TOKENS.read_text("utf-8")
    return dict(re.findall(r"(--text-(?:xs|sm|base|lg|xl|2xl|3xl)):\s*([^;]+);", body))


def test_every_type_step_is_fluid() -> None:
    steps = _text_tokens()
    assert steps, "no --text-* tokens found"
    not_fluid = [name for name, value in steps.items() if "clamp(" not in value]
    assert not not_fluid, f"type steps that do not scale with the viewport: {not_fluid}"


def test_the_fluid_bounds_are_rem_so_the_root_still_governs() -> None:
    """THE TEST THIS PART EXISTS FOR. `clamp(14px, 1vw, 18px)` is fluid and DEAD to the root -
    it would silently undo both a raised browser default and the text-size setting, which is
    the same failure the `body.zoom = 1/devicePixelRatio` trick commits."""
    for name, value in _text_tokens().items():
        inner = value[value.index("clamp(") + 6 : value.rindex(")")]
        low, _mid, high = (part.strip() for part in inner.split(","))
        assert low.endswith("rem"), f"{name} has a px floor ({low}) - the root cannot raise it"
        assert high.endswith("rem"), f"{name} has a px ceiling ({high}) - the root cannot raise it"


def test_the_text_size_setting_still_moves_type_on_a_wide_screen(ui: Page) -> None:
    """The two mechanisms compose: the setting scales the root, the clamp bounds are rem."""
    ui.set_viewport_size(UHD)
    ui.click('.nav-item[data-screen="settings"]')

    sizes = {}
    for size in ("small", "medium", "large"):
        ui.click(f'input[name="text-size"][value="{size}"]')
        ui.wait_for_timeout(200)
        sizes[size] = ui.eval_on_selector("body", "el => parseFloat(getComputedStyle(el).fontSize)")

    assert sizes["small"] < sizes["medium"] < sizes["large"], sizes


def test_type_grows_with_the_viewport_between_the_bounds(ui: Page) -> None:
    _at(ui, {"width": 1366, "height": 900})
    narrow = ui.eval_on_selector("body", "el => parseFloat(getComputedStyle(el).fontSize)")
    _at(ui, UHD)
    wide = ui.eval_on_selector("body", "el => parseFloat(getComputedStyle(el).fontSize)")

    assert wide > narrow, f"body is {narrow}px at 1366 and {wide}px at 3072 - the clamp is flat"


# ------------------------------------------------------ dragging a window between monitors


def test_the_layout_is_identical_at_a_different_device_pixel_ratio(ui: Page) -> None:
    """A window dragged from the laptop (dPR 1.00) to the BenQ (dPR 1.25).

    CSS px are dPR-independent by definition, so nothing in the layout may depend on it. This
    is asserted rather than assumed because the widely-copied remedy - setting
    `body.zoom = 1 / devicePixelRatio` - would make it false, and would undo the user's own
    scaling at the same time.
    """
    at_one = _at(ui, QHD)

    context = (
        ui.context.browser.new_context(device_scale_factor=1.25) if ui.context.browser else None
    )
    assert context is not None
    page = context.new_page()
    page.goto(ui.url)
    page.wait_for_selector(".nav-item")
    page.set_viewport_size(QHD)
    page.wait_for_timeout(300)
    at_ratio = _layout(page)
    ratio = page.evaluate("() => window.devicePixelRatio")
    context.close()

    assert abs(ratio - 1.25) < 0.01, f"the second context reports dPR {ratio}"
    assert abs(at_ratio["content"] - at_one["content"]) <= 2, (at_one, at_ratio)
    assert abs(at_ratio["panel"] - at_one["panel"]) <= 2, (at_one, at_ratio)


def test_a_viewport_change_refits_the_one_thing_that_measures_itself(ui: Page) -> None:
    """Moving between monitors changes the CSS viewport, which fires `resize`. The catalog path
    is the only element that measures itself in JS, and it already listens - so no new listener
    is needed for the monitor case, and none was added."""
    _at(ui, {"width": 1400, "height": 900})
    narrow = ui.eval_on_selector("#custody-catalog", "el => el.textContent.trim()")
    _at(ui, UHD)
    ui.wait_for_timeout(400)
    wide = ui.eval_on_selector("#custody-catalog", "el => el.textContent.trim()")

    full = ui.eval_on_selector("#custody-catalog", "el => el.dataset.full || ''")
    assert narrow, "no catalog path rendered"
    if full:
        assert wide == full or len(wide) >= len(narrow), (narrow, wide)


# ---------------------------------------------------------------------- portrait monitors


def test_a_rotated_qhd_is_not_treated_as_a_phone(ui: Page) -> None:
    """1440 CSS px wide is wider than most laptops. The rail stays a rail; only the panel goes,
    because 1440 is below the 1336 + panel threshold... it is not, so the panel stays too."""
    got = _at(ui, PORTRAIT_QHD)

    assert got["overflow"] <= 2, f"a rotated QHD scrolls horizontally by {got['overflow']:.0f}px"
    flex = ui.eval_on_selector("#sidebar", "el => getComputedStyle(el).flexDirection")
    assert flex == "column", "the rail became a top bar on a 1440px-wide screen"


def test_a_rotated_laptop_panel_drops_the_side_panel_and_keeps_the_rail(ui: Page) -> None:
    got = _at(ui, PORTRAIT_FHD)

    assert got["overflow"] <= 2, got
    expect(ui.locator("#panel")).to_be_hidden()
    flex = ui.eval_on_selector("#sidebar", "el => getComputedStyle(el).flexDirection")
    assert flex == "column", "a 1080px-wide portrait screen fell to the phone layout"


def test_nothing_overflows_at_any_of_the_five_real_viewports(ui: Page) -> None:
    for size in (LAPTOP, QHD, UHD, PORTRAIT_QHD, PORTRAIT_FHD):
        got = _at(ui, size)
        assert got["overflow"] <= 2, f"{size['width']}x{size['height']} scrolls sideways: {got}"
