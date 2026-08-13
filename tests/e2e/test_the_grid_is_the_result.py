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
            "shown": [{"sha256": f"{i:064x}", "name": f"IMG_000{i}.jpg"} for i in range(3)],
        },
    }
    summary.update(overrides)
    ui.evaluate(
        "(s) => { document.getElementById('org-result').innerHTML = organizeCompletion(s); }",
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


def test_the_grid_sits_above_the_numbers(ui: Page) -> None:
    """ "The grid IS the result" is an ordering claim, so it is asserted as one. Measured in
    document position rather than pixels, which is the claim and cannot be flaky."""
    _completion(ui)
    grid_first = ui.evaluate(
        """() => {
            const grid = document.querySelector("[data-testid='org-grid']");
            const tally = document.querySelector('#org-result .tally');
            if (!grid || !tally) return null;
            return !!(grid.compareDocumentPosition(tally) & Node.DOCUMENT_POSITION_FOLLOWING);
        }"""
    )
    assert grid_first is not None, "the card is missing either its grid or its tally"
    assert grid_first, "the numbers still come before the photos"


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
