"""A list the UI shortens must say it shortened it (audit F46).

The trip/event move preview renders ``p.moves.slice(0, 200)`` under a summary that reads
"Show the moves". A user reviewing where 2,057 photos are about to go was shown 200 of them,
presented as the whole plan, with nothing on screen distinguishing that from a complete list.
This is the never-silent rule (`IMPLEMENTATION_STANDARDS.md` §9) applied to a list: a truncated
outcome is *counted and named*, never folded into something that looks total.

The app already had the correct pattern - the clean-empty offer renders eight folder names and
then "...and N more". This is that pattern applied to the one list that lacked it.

Asserted through the browser rather than by grepping `app.js`, because the defect is what a
user reads. Both halves are here: a plan over the limit must disclose, and a plan under it must
**not** grow a spurious "and 0 more" - a disclosure that fires on complete lists trains people
to ignore it.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect

#: Mirrors ``MOVE_PREVIEW_LIMIT`` in app.js. Duplicated on purpose: if someone changes the
#: constant without changing the disclosure, these tests must fail rather than follow it.
_LIMIT = 200


def _json_route(route, body: dict) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _moves(count: int) -> list[dict[str, str]]:
    return [
        {"old": f"Camera/IMG_{i:04d}.jpg", "new": f"Trip/IMG_{i:04d}.jpg"} for i in range(count)
    ]


def _drive_to_preview(ui: Page, move_count: int) -> None:
    """Stub the propose -> name -> preview chain and stop at the rendered move list."""
    ui.route(
        "**/api/events/propose",
        lambda r: _json_route(
            r,
            {
                "ok": True,
                "session": "sess",
                "label": "Drive",
                "declines": [],
                "collapsed": None,
                "cards": [
                    {
                        "kind": "event",
                        "start": "2021-01-01",
                        "end": "2021-01-01",
                        "count": move_count,
                        "active_days": 1,
                        "days": [],
                        "location": None,
                        "collapsed": False,
                    }
                ],
            },
        ),
    )
    ui.route("**/api/events/sess/apply", lambda r: _json_route(r, {"events": 1, "trips": 0}))
    ui.route("**/api/events/sess/preview", lambda r: _json_route(r, {"job_id": "preview-job"}))
    ui.route(
        "**/api/jobs/preview-job/events**",
        lambda r: r.fulfill(
            status=200,
            content_type="text/event-stream",
            body="data: "
            + json.dumps(
                {
                    "type": "done",
                    "status": "done",
                    "summary": {"ok": True, "moves": _moves(move_count)},
                }
            )
            + "\n\n",
        ),
    )
    ui.click('button[data-screen="events"]')
    ui.fill("#ev-source", "/tmp/src")
    ui.click("#ev-propose")
    ui.fill('.ev-name[data-i="0"]', "Trip")
    ui.click("#ev-apply")


def test_a_shortened_move_list_names_what_it_left_out(ui: Page) -> None:
    over = _LIMIT + 50
    _drive_to_preview(ui, over)

    moves = ui.locator("#ev-moves")
    expect(moves).to_contain_text(f"{over:,} photos will move", timeout=30_000)
    # Before expanding: the summary itself admits it is partial, so the truncation is not a
    # surprise discovered at the bottom of a long scroll.
    expect(moves).to_contain_text(f"first {_LIMIT:,} of {over:,}")
    # And after: the tail says how many were left out.
    expect(moves).to_contain_text(f"and {over - _LIMIT:,} more")


def test_a_complete_move_list_does_not_claim_to_be_shortened(ui: Page) -> None:
    """Cry-wolf half: a plan that fits must read as complete, with no "and 0 more"."""
    _drive_to_preview(ui, 3)

    moves = ui.locator("#ev-moves")
    expect(moves).to_contain_text("3 photos will move", timeout=30_000)
    expect(moves).to_contain_text("Show the moves")
    expect(moves).not_to_contain_text("first")
    expect(moves).not_to_contain_text("more")


def test_a_move_list_exactly_at_the_limit_is_not_called_shortened(ui: Page) -> None:
    """Boundary: at exactly the limit nothing is hidden, so nothing may claim it is."""
    _drive_to_preview(ui, _LIMIT)

    moves = ui.locator("#ev-moves")
    expect(moves).to_contain_text(f"{_LIMIT:,} photos will move", timeout=30_000)
    expect(moves).not_to_contain_text("more")
