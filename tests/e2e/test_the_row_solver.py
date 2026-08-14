"""The row solver's own failure modes, none of which Stage B's guards can see.

**Why this file exists separately.** Stage B wrote its inversions to invariants that hold for a
square grid AND for a solved layout - shape preserved, nothing cropped, height under the ceiling -
which is what lets them survive the solver landing. The cost of that choice is that **they say
nothing about whether the solver is correct**. A solver that put every photograph on its own row,
or stretched the last row to fill, or clipped a panorama, would satisfy every one of them.

So these four are about the solver and only the solver. They were written **before** it, which is
the same rule the guards themselves are held to.

**The layout being guarded.** Rows of photographs at a common height; a row's height is
``(container - gaps) / sum(aspects)``, so a row fills the container exactly by construction. The
last row takes ``min(natural, target)`` rather than being blown up to fill a width it does not
have. Every height is clamped to `ROW_HEIGHT_CEILING`. `docs/organize-grid-design.md`.

⚠ **Read the mutation claims carefully; they are not uniform.** Guards 1 and 3 fail against
today's square grid, so they carry the both-ways proof. Guards 2 and 4 **pass against today's
code and that is correct** - they are bounds, and a square grid violates neither. Claiming they
"fail against today's CSS" would be false, so they are proven the way Stage B's ceiling guard was:
against a deliberately broken solver. Said here rather than implied, because a both-ways claim
that does not apply is worse than no claim.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

TESTID = "[data-testid='org-grid']"

#: From `test_the_grid_is_the_result.py`. The wall is 320 / (16/9) = 180 exactly.
ROW_HEIGHT_CEILING = 178

#: The height the brief targets. A FULL row solves to whatever fills the width, which is at or
#: below this; the LAST row is capped here rather than blown up past it.
ROW_HEIGHT_TARGET = 172

#: Real shapes from the maintainer's corpus, mixed so a row has something to solve: 4:3 landscape,
#: 3:4 portrait, 16:9, and the widest real photograph at 4.348:1.
_CORPUS_SHAPES = [
    (4000, 3000),
    (3000, 4000),
    (4000, 2250),
    (3000, 4000),
    (4000, 3000),
    (2448, 3264),
    (4000, 1824),
    (3264, 2448),
]

#: The widest photograph in 4,108 real ones. At a 172px row height it is 748px wide, against a
#: 420px panel - the case that proved a pure-CSS layout could not carry this.
_PANORAMA = (4348, 1000)


def _grid(ui: Page, shapes: list[tuple[int, int]]) -> None:
    """Render a finished organize whose sample carries these shapes."""
    summary: dict[str, Any] = {
        "organized": len(shapes),
        "photos": len(shapes),
        "videos": 0,
        "audio": 0,
        "bytes_organized": 5000,
        "duplicates": 0,
        "bytes_saved": 0,
        "moved_by_copy": len(shapes),
        "moved_in_place": 0,
        "failed": 0,
        "folders": {},
        "outcomes": {"organized": len(shapes)},
        "mode": "copy",
        "organized_sample": {
            "total": len(shapes),
            "shown": [
                {"sha256": f"{i:064x}", "name": f"IMG_{i:04}.jpg", "w": w, "h": h}
                for i, (w, h) in enumerate(shapes)
            ],
        },
    }
    ui.evaluate(
        "(s) => { document.getElementById('org-result').innerHTML = organizeCompletion(s); }",
        summary,
    )
    expect(ui.locator("#org-result .card")).to_be_visible()
    # Opened, because the collapsed state shows one row and three of these four guards are about
    # what happens across rows.
    toggle = ui.locator(".grid-toggle")
    if toggle.count():
        toggle.click()


def _rows(ui: Page) -> list[dict[str, Any]]:
    """Tiles grouped into rows by their `top`, with the container's content width."""
    return ui.evaluate(
        """() => {
            const grid = document.querySelector("[data-testid='org-grid']");
            const style = getComputedStyle(grid);
            const inner = grid.clientWidth
                - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            const gap = parseFloat(style.columnGap || style.gap) || 0;
            const byTop = new Map();
            for (const el of grid.querySelectorAll('img.tile')) {
                const r = el.getBoundingClientRect();
                const key = Math.round(r.top);
                if (!byTop.has(key)) byTop.set(key, []);
                byTop.get(key).push({
                    w: r.width, h: r.height,
                    aw: Number(el.getAttribute('width')), ah: Number(el.getAttribute('height')),
                    right: r.right,
                });
            }
            return [...byTop.entries()]
                .sort((a, b) => a[0] - b[0])
                .map(([top, tiles]) => ({top, tiles, inner, gap}));
        }"""
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Written before the solver. Today's auto-fill grid leaves the leftover width at the end "
        "of each row, which is exactly what a justified row must not do. The marker comes off in "
        "the commit that lands the solver."
    ),
)
def test_every_full_row_fills_the_width_it_was_given(ui: Page) -> None:
    """GUARD 1. A row that leaves slack is not justified, it is a wrapped list.

    Checked at more than one viewport because a solver that hardcodes a width passes at the one
    it was written against and nowhere else.
    """
    for viewport in (1440, 900):
        ui.set_viewport_size({"width": viewport, "height": 1200})
        _grid(ui, _CORPUS_SHAPES)
        rows = _rows(ui)
        assert len(rows) > 1, f"at {viewport}px the sample did not wrap, so nothing is being solved"

        for row in rows[:-1]:  # the last row is guard 2's subject and must NOT fill
            tiles = row["tiles"]
            spanned = sum(t["w"] for t in tiles) + row["gap"] * (len(tiles) - 1)
            assert abs(spanned - row["inner"]) <= 2, (
                f"at {viewport}px the row at y={row['top']} spans {spanned:.1f}px of "
                f"{row['inner']:.1f}px available, leaving {row['inner'] - spanned:.1f}px of slack. "
                "A justified row fills its container; the leftover is what made the old grid read "
                "as a torn strip."
            )


def test_the_last_row_is_not_blown_up_to_fill(ui: Page) -> None:
    """GUARD 2. The classic justified-layout defect: three photos in the final row scaled to a
    width they do not have, so they tower over every row above them.

    ⚠ **This passes against today's square grid and that is correct** - every square row is the
    same height, so nothing is stretched. It is a bound, not an inversion, and it is proven
    against a deliberately broken solver rather than against today's CSS.
    """
    ui.set_viewport_size({"width": 1440, "height": 1200})
    _grid(ui, _CORPUS_SHAPES)
    rows = _rows(ui)
    assert len(rows) > 1, "the sample did not wrap, so there is no last row to check"

    last_row = rows[-1]
    last = max(t["h"] for t in last_row["tiles"])

    # ⚠ NOT compared against the rows above it, which was this guard's first and wrong premise.
    # A FULL row solves to whatever height fills the width - 160.4px in the reference run - while
    # the last row is capped at the target. So the last row being TALLER than the rows above is
    # correct, and asserting otherwise failed against a solver that was behaving properly. The
    # defect is being scaled PAST the target to fill a width it does not have.
    assert last <= ROW_HEIGHT_TARGET + 1, (
        f"the last row is {last:.1f}px against a {ROW_HEIGHT_TARGET}px target. A final row with "
        "fewer photographs keeps its natural height capped at the target; scaling it up to fill "
        "the container is the classic justified-layout defect."
    )

    # The direct observable, and the exact inverse of guard 1: a stretched last row spans the
    # container, an unstretched one leaves the slack showing.
    spanned = sum(t["w"] for t in last_row["tiles"]) + last_row["gap"] * (
        len(last_row["tiles"]) - 1
    )
    assert spanned < last_row["inner"] - 2, (
        f"the last row spans {spanned:.1f}px of {last_row['inner']:.1f}px - it fills the "
        "container exactly, which means it was stretched to. A short final row ends where its "
        "photographs end."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Written before the solver. Today's grid crops this photograph to a square with "
        "object-fit: cover, so its shape is not preserved. The marker comes off with the solver."
    ),
)
def test_a_photograph_wider_than_the_panel_is_scaled_not_clipped_or_squashed(ui: Page) -> None:
    """GUARD 3. The real case from the corpus, and the pair that `max-width: 100%` broke.

    A 4.348:1 photograph at a 172px row height is 748px wide, against a 420px panel. Three things
    can happen and only one is right: it can be clipped (the card overflows), squashed (the shape
    is lost, which is what a width constraint against a fixed height produces), or **scaled** -
    given a shorter row of its own, which is what a solver does by construction because a row's
    height is `(container - gaps) / sum(aspects)`.

    **Both halves are asserted together on purpose.** Each alone is satisfiable by the failure the
    other catches: clipping preserves the shape, and squashing keeps it inside the card.
    """
    ui.set_viewport_size({"width": 420, "height": 900})
    _grid(ui, [_PANORAMA])
    rows = _rows(ui)
    tile = rows[0]["tiles"][0]

    # ⚠ Compared against the PAYLOAD's shape, not the element's `width`/`height` attributes.
    # The first version of this guard used the attributes and XPASSed against today's grid,
    # because `resultGrid` hardcodes them to 320x320: the declared shape and the drawn square
    # agree perfectly while the photograph inside is cropped. A guard must measure against the
    # truth, never against a number the thing under test supplies.
    intrinsic = _PANORAMA[0] / _PANORAMA[1]
    drawn = tile["w"] / tile["h"]
    assert abs(drawn - intrinsic) / intrinsic <= 0.02, (
        f"the photograph is {intrinsic:.3f}:1 and is drawn {drawn:.3f}:1. A width constraint "
        "against a fixed height squashes rather than scales - this is what max-width: 100% did."
    )

    limit = ui.eval_on_selector(
        TESTID,
        """el => { const card = el.closest('.card'); const r = card.getBoundingClientRect();
            return r.right - parseFloat(getComputedStyle(card).paddingRight); }""",
    )
    assert tile["right"] <= limit + 1, (
        f"the photograph's right edge is at {tile['right']:.0f}px against a card ending at "
        f"{limit:.0f}px. Preserving the shape by hanging off the panel is not preserving it."
    )


def test_no_row_exceeds_the_ceiling_under_the_solver(ui: Page) -> None:
    """GUARD 4. The wall, held across every row rather than only the first.

    ⚠ **Also passes against today's square grid**, where every tile is 148px - a bound, not an
    inversion, proven against a broken solver. Stage B's
    `test_a_row_is_drawn_near_the_height_its_thumbnails_were_made_for` checks the same ceiling on
    a single sample; this checks it on a wrapped, mixed-shape grid, where a solver dividing by a
    small sum of aspects can produce one very tall row while every other row is fine.
    """
    for viewport in (1440, 900, 420):
        ui.set_viewport_size({"width": viewport, "height": 1200})
        _grid(ui, _CORPUS_SHAPES)
        for row in _rows(ui):
            tallest = max(t["h"] for t in row["tiles"])
            assert tallest <= ROW_HEIGHT_CEILING, (
                f"at {viewport}px the row at y={row['top']} is {tallest:.1f}px tall, past the "
                f"{ROW_HEIGHT_CEILING}px ceiling. Past it a 16:9 photograph is upscaled from a "
                "320px thumbnail that has no more pixels."
            )
