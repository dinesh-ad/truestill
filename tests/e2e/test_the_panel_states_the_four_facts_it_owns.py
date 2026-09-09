"""The right-hand panel's four facts, which existed nowhere else and were asserted nowhere.

⚠ **`renderPanel` is the only place in the product that says any of these**, and before this file
`grep -rn 'panel-fact\\|Photos span\\|Look-alikes kept\\|Biggest files' tests/` returned nothing.
Four statements about a person's library, in a 248px column the layout now reserves on purpose,
and every one of them could have stopped rendering with the whole lane green - which is the gap
that let a lying stepper live three days, one column to the right.

**Each fact is conditional on its own payload field**, so the risk is not that the panel breaks
loudly but that one row quietly stops appearing when a field is renamed or dropped. The tests
below therefore assert per-row, and the fixture carries all four at once so a renderer that lost
one is not hidden by a fixture that never had it.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, Route, expect

SOURCE = "/tmp/source"
PANEL = "#panel"
FACT = "#panel .panel-fact"

#: Deliberately distinct values, so a row rendering the WRONG field is a failure rather than a
#: coincidence: 4 GB reclaimable against 1 GB of look-alikes, and a biggest file at neither.
RECLAIMABLE = 4_000_000_000
NEAR_KEPT = 1_000_000_000
BIGGEST = 700_000_000


def _json_route(route: Route, body: dict[str, Any]) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _preview(ui: Page, **overrides: Any) -> None:
    """Drive Organize to a rendered dedup preview carrying all four panel facts.

    The panel is a THIRD COLUMN and is not rendered below 1336px, so the viewport is set wide
    first - at a narrower one every assertion here would pass or fail for the wrong reason.
    """
    summary: dict[str, Any] = {
        "tier": "dedup",
        "files": 460,
        "photos": 450,
        "videos": 10,
        "audio": 0,
        "by_format": {},
        "new_unique": 400,
        "near_dup": 20,
        "exact_dup": 40,
        "exact_dup_matches": {
            "total": 40,
            "shown": [],
            "already_in_library": 40,
            "within_this_batch": 0,
            "unclassified": 0,
        },
        "near_dup_matches": {"total": 20, "shown": []},
        "will_organize": 420,
        "undated": 0,
        "sentinel_rejected": 0,
        "future_rejected": 0,
        "suspect_default": 0,
        "inferred_local_shifts": [],
        "folders": {"Camera": 420},
        "destination_tree": {"2014/2014-08": 420},
        "skipped": {},
        "skipped_folders": [],
        "unreadable_files": {"total": 0, "shown": []},
        "mode": "copy",
        # --- the four the panel owns -----------------------------------------------------
        "capture_span": {"oldest": "2009-03-14", "newest": "2021-11-02"},
        "duplicate_bytes": {"reclaimable": RECLAIMABLE, "near": NEAR_KEPT},
        "largest_files": {"total": 1, "shown": [{"name": "DSC_0001.NEF", "bytes": BIGGEST}]},
    }
    summary.update(overrides)
    ui.set_viewport_size({"width": 1600, "height": 900})
    ui.route(
        "**/api/organize/inventory",
        lambda r: _json_route(
            r,
            {
                "tier": "inventory",
                "files": 460,
                "photos": 450,
                "videos": 10,
                "audio": 0,
                "by_format": {},
                "total_bytes": 460_000,
                "skipped": {},
                "skipped_folders": [],
            },
        ),
    )
    ui.route("**/api/organize/preview", lambda r: _json_route(r, {"job_id": "prev-job"}))
    ui.route(
        "**/api/jobs/prev-job/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body=f"data: {json.dumps({'type': 'done', 'summary': summary})}\n\n",
        ),
    )
    ui.fill("#org-source", SOURCE)
    ui.fill("#org-dest", "/tmp/library")
    ui.click("#org-preview")
    expect(ui.locator("#org-dedup")).to_be_enabled(timeout=30_000)
    ui.click("#org-dedup")
    # The TALLY, not `#org-result .card`: the inventory tier already drew a card, so waiting on
    # that returns before the dedup summary has landed and every assertion below would read an
    # empty panel and pass for the wrong reason.
    expect(ui.locator("[data-testid='org-tally']")).to_be_visible(timeout=30_000)


def _fact(ui: Page, label: str):
    """The one `.panel-fact` whose key is `label`."""
    return ui.locator(f"{FACT}", has=ui.locator(".panel-k", has_text=label))


def test_the_panel_draws_one_row_per_fact_the_payload_carries(ui: Page) -> None:
    """Anti-vacuity for everything below, and the census in one line: four fields, four rows.

    Without this, a panel that rendered nothing at all would satisfy every `not_to_contain_text`
    in this file and a panel that rendered one row four times would satisfy the per-row tests.
    """
    _preview(ui)

    expect(ui.locator(PANEL)).to_be_visible()
    expect(ui.locator(FACT)).to_have_count(4)
    expect(ui.locator("#panel .panel-title")).to_have_text("This folder")


def test_the_span_names_the_oldest_and_the_newest(ui: Page) -> None:
    """`capture_span`. The only statement anywhere about how far back the folder reaches."""
    _preview(ui)

    span = _fact(ui, "Photos span")
    expect(span).to_have_count(1)
    expect(span).to_contain_text("2009-03-14")
    expect(span).to_contain_text("2021-11-02")


def test_the_duplicate_cost_is_stated_and_is_not_the_look_alike_figure(ui: Page) -> None:
    """`duplicate_bytes.reclaimable` - what the copies WOULD have cost, so it is a saving.

    The two byte figures are the pair most likely to be crossed, which is why the fixture makes
    them 4 GB and 1 GB rather than anything alike: a row reading the wrong field fails here
    instead of looking plausible.
    """
    _preview(ui)

    cost = _fact(ui, "Space duplicates would have cost")
    expect(cost).to_have_count(1)
    expect(cost).to_contain_text("4")
    expect(cost).to_contain_text("GB")
    expect(cost).not_to_contain_text("1 GB")


def test_look_alikes_kept_is_named_separately_and_never_added_to_the_saving(ui: Page) -> None:
    """`duplicate_bytes.near`. Truestill KEEPS these files, so their bytes are not a saving -
    the panel's own comment says they are named separately and never summed into the line above.
    A renderer that added them would print 5 GB in one row and nothing in the other."""
    _preview(ui)

    kept = _fact(ui, "Look-alikes kept")
    expect(kept).to_have_count(1)
    expect(kept).to_contain_text("1")
    expect(kept).to_contain_text("GB")
    expect(kept).not_to_contain_text("5")


def test_the_biggest_files_are_named_with_their_size(ui: Page) -> None:
    """`largest_files.shown`. A name and a size per row - the name alone answers nothing."""
    _preview(ui)

    biggest = _fact(ui, "Biggest files")
    expect(biggest).to_have_count(1)
    expect(biggest).to_contain_text("DSC_0001.NEF")
    expect(biggest).to_contain_text("700")


def test_a_fact_the_payload_does_not_carry_draws_no_row(ui: Page) -> None:
    """**The cry-wolf half, and it is what keeps the four above honest.** Every row is
    conditional, so a renderer that drew all four unconditionally would print "Photos span
    undefined → undefined" on a folder whose dates are unknown - and would pass all five tests
    above. Dropping one field must drop exactly one row."""
    _preview(ui, capture_span=None)

    expect(ui.locator(FACT)).to_have_count(3)
    expect(ui.locator(PANEL)).not_to_contain_text("Photos span")
    expect(ui.locator(PANEL)).not_to_contain_text("undefined")


def test_a_payload_with_none_of_the_four_draws_no_panel_at_all(ui: Page) -> None:
    """No column rather than an empty card. `renderPanel` writes "" when nothing survives, and
    `.panel:empty` is what removes the track - so this is also what keeps the reserved column
    from becoming a permanent empty box on a folder that has nothing to say."""
    _preview(
        ui,
        capture_span=None,
        duplicate_bytes={"reclaimable": 0, "near": 0},
        largest_files={"total": 0, "shown": []},
    )

    expect(ui.locator(FACT)).to_have_count(0)
    expect(ui.locator(PANEL)).to_be_hidden()
