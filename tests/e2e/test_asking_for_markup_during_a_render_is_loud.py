"""Asking the island for a block of HTML while it is rendering must fail loudly, not silently.

**The failure this guards, which shipped and was found by diffing rather than by a red run.**
`toHtml` renders a component into a detached node with `flushSync` and reads `innerHTML`. React
does not flush when it is already rendering: it logs a warning nothing reads, and the caller gets
`""`. The completion card built its folder chips that way, from inside the island's own render, so
the whole "Into these folders" block vanished while the card's stats line went on printing
"N folders". Nothing failed.

**How the trap is reached here without a line of production code existing for the test.** The
island calls three `app.js` globals DURING its render - `outcomeWord`, `cleanupOfferNote` and
`showScreen` - which is the same shape as the original defect: a seam function invoked mid-render
that itself asks for markup. Replacing one of them with a function that asks for markup reproduces
the defect exactly, using only seams the product already has.

The cry-wolf half lives in the four screens that call `truestillMarkup` legitimately, from
ordinary event handlers rather than from a render. Their existing tests are the proof that this
guard does not fire on them, and they are named in the commit rather than duplicated here.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

SUMMARY: dict[str, Any] = {
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
    "folders": {"2021": 3},
    "outcomes": {"organized": 3},
    "mode": "copy",
    "organized_sample": {"total": 0, "shown": []},
    # The island calls `cleanupOfferNote` during its render only when this is present.
    "leftover_empty_folders": {"count": 2, "folders": ["x", "y"], "root": "/src"},
}


def test_a_seam_that_asks_for_markup_mid_render_throws_instead_of_returning_nothing(
    ui: Page,
) -> None:
    """The guard fires, and its message names the trap rather than the symptom."""
    errors: list[str] = []
    ui.on("pageerror", lambda e: errors.append(str(e)))

    # `cleanupOfferNote` is called from inside `CompletionCard`'s render. Pointed at the markup
    # seam, it is the original defect reproduced through the product's own wiring.
    ui.evaluate(
        "() => { window.cleanupOfferNote = () =>"
        " window.truestillMarkup.byFormat({ photos: { jpg: 1 } }); }"
    )
    ui.evaluate("(s) => { window.organizeResult.set({ kind: 'complete', summary: s }); }", SUMMARY)

    # The render is scheduled, not synchronous with `set`, so the throw arrives after `evaluate`
    # returns. Polled rather than slept: a fixed wait is either flaky or slow.
    for _ in range(100):
        if errors:
            break
        ui.wait_for_timeout(100)
    assert errors, "asking for markup mid-render raised nothing at all"
    joined = "\n".join(errors)
    assert "during a React render" in joined, f"the error does not name the trap: {joined}"
    assert "come back EMPTY" in joined, f"the error does not say what would have happened: {joined}"


def test_the_same_seam_off_the_render_path_still_answers(ui: Page) -> None:
    """The cry-wolf half, in miniature: the identical call from an ordinary handler must work.

    Without this the test above would pass against a `toHtml` that throws unconditionally, which
    would take Backups' and Import's cards down with it.
    """
    html = ui.evaluate("() => window.truestillMarkup.byFormat({ photos: { jpg: 2, png: 1 } })")
    assert html, "the markup seam returned nothing when called off the render path"
    assert "jpg 2" in html, f"the by-format block did not render its formats: {html}"


def test_a_component_that_renders_nothing_is_not_mistaken_for_the_trap(ui: Page) -> None:
    """The sharpest cry-wolf case, and the reason the detection is a sentinel rather than a test
    of `innerHTML`. `ByFormat` returns `null` for a payload with no format rows, so an empty
    string is its CORRECT answer - and must not be reported as a failed flush."""
    html = ui.evaluate("() => window.truestillMarkup.byFormat({ photos: {} })")
    assert html == "", f"expected the empty answer, got {html!r}"
