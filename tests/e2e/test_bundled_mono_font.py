"""The bundled DejaVu Sans Mono is the face that actually rasterises, from our own server.

**The trap this suite is built around.** `getComputedStyle(el).fontFamily` only echoes the
declaration: it returns the full stack whether or not a single glyph came from it, so it would
pass with no font present at all. CDP `CSS.getPlatformFontsForNode` fixes that - it reports what
the rasteriser used.

**But CDP alone is still not enough here, and that is the subtle part.** The maintainer's machine
has DejaVu Sans Mono installed system-wide, and the bundled face carries the same family name. So
CDP would report `DejaVu Sans Mono` for a system fallback and for our file identically, and every
assertion below would pass on a machine where the bundle shipped nothing.

So provenance is asserted where three defences overlap:

  1. the browser actually fetched `/static/fonts/*.ttf` from us (network),
  2. a `@font-face`-declared face reached `loaded` (`document.fonts` holds only declared faces,
     never system ones),
  3. the rasteriser used that family (CDP).

Any one alone is passable without the bundle. Together they are not. `test_..._would_pass_with_a
_system_font` below pins that reasoning in place so a later reader does not "simplify" 1 and 2
away as redundant.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell

# Every element here is declared `var(--family-mono)` in app.css.
#   .wordmark-text  - the mark itself
#   .custody .line  - a real sentence, and where WARN_MARK (U+26A0) lands
#   .custody .pips  - U+25AA / U+25AB, the glyphs that eliminated IBM Plex Mono
MONO_SURFACES = (".wordmark-text", ".custody .line", ".custody .pips")

EXPECTED_FAMILY = "DejaVu Sans Mono"


def _platform_fonts(ui: Page, selector: str) -> list[dict[str, Any]]:
    """What the rasteriser actually used - not what CSS asked for."""
    cdp = ui.context.new_cdp_session(ui)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    root = cdp.send("DOM.getDocument")["root"]["nodeId"]
    node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})["nodeId"]
    assert node, f"{selector} is not in the DOM"
    return list(cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"])


def test_the_font_files_are_served_by_our_own_server(ui: Page) -> None:
    """Self-hosted, offline-first: the bytes come from us, not from a CDN."""
    base = ui.url.split("?")[0].rstrip("/")
    for face in ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"):
        response = ui.request.get(f"{base}/static/fonts/{face}")
        assert response.ok, f"{face} did not serve: {response.status}"
        body = response.body()
        assert body[:4] == b"\x00\x01\x00\x00", f"{face} is not a TrueType file"
        assert len(body) > 100_000, f"{face} served {len(body)} bytes - truncated?"


def test_the_licence_travels_with_the_font_over_http_too(ui: Page) -> None:
    """It sits in the served directory, so a user who has the app has the notice."""
    base = ui.url.split("?")[0].rstrip("/")
    response = ui.request.get(f"{base}/static/fonts/LICENSE-DejaVu.txt")
    assert response.ok, f"the Vera notice did not serve: {response.status}"
    assert "Copyright (c) 2003 by Bitstream, Inc." in response.text()


def test_the_page_actually_fetched_the_bundled_face(ui: Page) -> None:
    """Provenance defence 1 of 3: the bytes crossed the wire from our origin.

    A system fallback makes no request. This is the assertion a bundle that dropped the data file
    would fail, on a machine where CDP alone would still report the right family.
    """
    # RESPONSES, not requests. A request event fires for a 404 too, so recording requests alone
    # would keep passing if the font file vanished and the page silently fell back.
    #
    # A CONTEXT THAT HAS NEVER SEEN THIS ORIGIN, not `reload()`. The reload version passed in
    # Chromium and failed in WebKit the first time WebKit ran, and the product was fine both
    # times: WebKit serves the already-cached face and emits no network event, while Chromium
    # emits one anyway. "A reload re-fetches" is a Chromium behaviour, not a web guarantee - and
    # this test's claim is that the bytes crossed the wire from OUR origin, which is only
    # observable on a first load. Measured: fresh context fetches both faces in both engines.
    served: list[tuple[str, int]] = []
    context = ui.context.browser.new_context() if ui.context.browser else None
    assert context is not None, "no browser available to open a cold context"
    try:
        page = context.new_page()
        page.on("response", lambda r: served.append((r.url, r.status)))
        page.goto(ui.url)
        expect(page.locator(".wordmark-text")).to_be_visible()
        # The face loads lazily - only once something needs it - so wait for it to settle.
        page.wait_for_function("() => document.fonts.status === 'loaded'")
    finally:
        context.close()

    fetched = [(u, s) for u, s in served if "/static/fonts/" in u and u.endswith(".ttf")]
    assert fetched, f"no bundled font was requested; the page used a fallback. saw: {served}"
    assert all(status == 200 for _, status in fetched), (
        f"a bundled face did not serve, so the page fell back silently: {fetched}"
    )


def test_a_declared_face_reached_loaded(ui: Page) -> None:
    """Provenance defence 2 of 3: `document.fonts` holds only @font-face faces, never system ones.

    So a `loaded` DejaVu entry here cannot come from the operating system.
    """
    ui.wait_for_function("() => document.fonts.status === 'loaded'")
    loaded = ui.evaluate(
        "() => [...document.fonts]"
        ".filter(f => f.status === 'loaded')"
        ".map(f => ({family: f.family, weight: f.weight}))"
    )
    families = {f["family"] for f in loaded}
    assert EXPECTED_FAMILY in families, (
        f"no declared DejaVu face reached 'loaded' - only {families}. "
        "A system fallback would leave document.fonts empty."
    )
    weights = sorted(f["weight"] for f in loaded if f["family"] == EXPECTED_FAMILY)
    assert weights == ["400", "700"], f"expected the two shipped weights, got {weights}"


@pytest.mark.parametrize("selector", MONO_SURFACES)
def test_the_bundled_family_is_what_rasterises(ui: Page, selector: str, browser_name: str) -> None:
    """Provenance defence 3 of 3: CDP, on each surface that matters.

    `.custody .pips` is here because it is the assertion that eliminated IBM Plex Mono: it lacks
    U+25AA and U+25AB, so its pips silently rasterised in Times New Roman. A font that cannot draw
    the custody glyphs fails inside the one line the sidebar exists to make trustworthy.

    ⚠ **CHROMIUM ONLY, AND THAT IS A REAL GAP RATHER THAN A TIDY-UP.** This is the only assertion
    that reads which font the engine *actually rasterised with*, as opposed to which one it was
    asked for - and the only way to ask that through Playwright is CDP, which no other engine
    speaks (`CDP session is only available in Chromium`). So on WebKit - the engine that ships in
    the Tauri shell on Linux and macOS - the substitution this test exists to catch would go
    unseen. The two defences above it still run everywhere: the face is fetched from our origin,
    and both weights reach `loaded`. What is not covered on WebKit is the last step, whether a
    glyph silently fell back mid-string. Skipped loudly rather than quietly passing, on
    `test_selfcheck`'s rule: a surface that was not checked cannot be read as one that passed.
    """
    if browser_name != "chromium":
        pytest.skip(f"needs CDP to read the rasterised family; {browser_name} has no equivalent")
    fonts = _platform_fonts(ui, selector)
    assert fonts, f"nothing rasterised for {selector}"
    families = {f["familyName"] for f in fonts}
    assert families == {EXPECTED_FAMILY}, (
        f"{selector} did not rasterise wholly in the bundled face: {families}. "
        "More than one family means some glyph fell back to another font."
    )


def test_the_wordmark_uses_the_real_bold_not_a_synthesised_semibold(ui: Page) -> None:
    """The wordmark asks for 600; only 400 and 700 exist, so CSS matching lands on Bold.

    Measured rather than reasoned: rendered at 18px, weight 600 and weight 700 produce identical
    bitmaps while 400 differs. Pinned because shipping a real SemiBold later would silently
    lighten the mark without any CSS changing.
    """
    weight = ui.eval_on_selector(".wordmark-text", "el => getComputedStyle(el).fontWeight")
    assert weight == "600", f"the wordmark no longer asks for 600: {weight}"

    same_as_bold = ui.evaluate(
        "() => {"
        " const m = (w) => {"
        "  const c = document.createElement('canvas').getContext('2d');"
        "  c.font = w + \" 18px 'DejaVu Sans Mono'\";"
        "  return c.measureText('Truestill.').width; };"
        " return {four: m(400), six: m(600), seven: m(700)}; }"
    )
    assert same_as_bold["six"] == same_as_bold["seven"], (
        f"weight 600 no longer resolves to the Bold face: {same_as_bold}"
    )


def test_the_pips_and_warning_mark_have_real_glyphs_in_the_bundled_face(ui: Page) -> None:
    """The specific defect that eliminated Plex, asserted directly rather than by family name.

    A face can be present and still lack a glyph; the browser then falls back per character, which
    is invisible to a family-name check on text that happens to be all ASCII.
    """
    missing = ui.evaluate(
        "() => {"
        " const c = document.createElement('canvas').getContext('2d');"
        " const width = (ch, font) => { c.font = font; return c.measureText(ch).width; };"
        " const mono = \"13px 'DejaVu Sans Mono'\";"
        " const bogus = \"13px 'NoSuchFamilyAnywhere'\";"
        " return ['\\u26a0', '\\u25aa', '\\u25ab'].filter("
        "   ch => width(ch, mono) === width(ch, bogus)); }"
    )
    assert missing == [], (
        f"the bundled face has no glyph for {missing} - these would fall back per character, "
        "which is exactly how IBM Plex Mono broke the custody strip"
    )


def test_this_suite_would_not_pass_on_a_system_font_alone(ui: Page) -> None:
    """Anti-vacuity, and the reason defences 1 and 2 are not redundant with 3.

    The bundled family name is identical to the system one on Linux, so CDP cannot distinguish
    them. This asserts the distinguishing signal exists and is observable: the `@font-face` rule
    names a same-origin URL. If a future edit swaps to `local()`, CDP keeps passing and this
    fails - which is the whole point.
    """
    sources = ui.evaluate(
        "() => [...document.styleSheets]"
        ".flatMap(s => { try { return [...s.cssRules]; } catch { return []; } })"
        ".filter(r => r instanceof CSSFontFaceRule)"
        ".map(r => r.style.getPropertyValue('src'))"
    )
    assert sources, "no @font-face rule is reachable from the page"
    dejavu = [s for s in sources if "DejaVuSansMono" in s]
    assert dejavu, f"no DejaVu @font-face src found: {sources}"
    for src in dejavu:
        assert "local(" not in src, "local() makes the system copy indistinguishable from ours"
        assert "url(" in src, "the face is not loaded from a URL at all"
