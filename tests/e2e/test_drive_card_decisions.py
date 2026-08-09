"""The decisions lines on the drive card, read the way a person reads them.

**§4's sixteenth member applies harder here than anywhere.** This card renders empty and then
fills, which is the "already true" trap in its purest form: every absence assertion on it - no
date, no staleness line, no card at all - is satisfied by the blank page before any request has
been answered. So every test below waits on a **positive** signal first: some text that only the
finished render can produce.

**The absence test is the one most likely to be vacuous**, and it is built so it cannot be. It
stubs two drives - one connected and carrying a document, one offline - and waits for the
CONNECTED drive's date line to arrive before asserting the offline card has no decisions line.
The positive signal proves the whole list rendered, so the absence is measured at a moment when
the thing being asserted absent would already be there if the code were wrong.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page, expect

_SAVED = "2026-08-09T12:00:00+00:00"


def _drive(label: str, uuid: str, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "uuid": uuid,
        "files": 2,
        "photos": 2,
        "videos": 0,
        "audio": 0,
        "size": 100,
        "last_seen": None,
        "last_verified": None,
        "path": "/tmp/here",
        "reach": "connected",
        "decisions": None,
    }
    row.update(over)
    return row


def _decisions(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "saved_at": _SAVED,
        "stale": [],
        "awaiting_restore": [],
        "refusal": None,
        "problem": None,
    }
    base.update(over)
    return base


def _show(ui: Page, drives: list[dict[str, Any]]) -> None:
    ui.route(
        "**/api/drives**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "library": {
                        "files": 2,
                        "photos": 2,
                        "videos": 0,
                        "audio": 0,
                        "bytes": 100,
                        "by_format": {},
                    },
                    "at_risk": [],
                    "drives": drives,
                }
            ),
        ),
    )
    ui.click('button[data-screen="backups"]')


def test_the_card_says_when_the_decisions_on_that_drive_were_saved(ui: Page) -> None:
    """ "Obvious that it exists, obvious how old it is" - the whole lesson from the threads where
    people had backups they could not find. The date is the line that does it."""
    _show(ui, [_drive("Desk HDD", "u1", decisions=_decisions())])

    saved = ui.locator("[data-testid='drive-decisions-saved']")
    expect(saved).to_contain_text("decisions saved here: 2026-08-09", timeout=30_000)


def test_a_drive_that_is_behind_says_so_in_words(ui: Page) -> None:
    """The staleness line, and it names WHAT is behind rather than saying "out of date" - a user
    who cannot tell what is missing cannot decide whether it matters."""
    _show(ui, [_drive("Desk HDD", "u1", decisions=_decisions(stale=["trips", "events"]))])

    stale = ui.locator("[data-testid='drive-decisions-stale']")
    expect(stale).to_contain_text("this copy is behind", timeout=30_000)
    expect(stale).to_contain_text("trips, events")


def test_a_drive_that_is_up_to_date_carries_no_staleness_line(ui: Page) -> None:
    """CRY-WOLF HALF. Every ordinary drive is up to date, so a line that appeared anyway would be
    on every card forever and learned as noise.

    Non-vacuous by construction: the date line is waited for FIRST, so the card is known to have
    rendered before the absence is asserted. Without that, this passes against a blank page.
    """
    _show(ui, [_drive("Desk HDD", "u1", decisions=_decisions())])

    expect(ui.locator("[data-testid='drive-decisions-saved']")).to_be_visible(timeout=30_000)
    expect(ui.locator("[data-testid='drive-decisions-stale']")).to_have_count(0)


def test_a_save_that_failed_finally_says_so_on_screen(ui: Page) -> None:
    """JOB 1B'S GAP, CLOSED. The save has recorded this since c5f36ff and no screen has ever
    shown it: a drive that refused every write looked identical to one that took them all."""
    _show(
        ui,
        [
            _drive(
                "Desk HDD",
                "u1",
                decisions=_decisions(
                    problem="the drive is read-only, or this account cannot write to it"
                ),
            )
        ],
    )

    problem = ui.locator("[data-testid='drive-decisions-problem']")
    expect(problem).to_contain_text("decisions were not saved here", timeout=30_000)
    expect(problem).to_contain_text("read-only")


def test_a_drive_carrying_names_this_computer_lacks_offers_them(ui: Page) -> None:
    """The lost-machine signal on the screen someone opens after plugging a drive in."""
    _show(ui, [_drive("Desk HDD", "u1", decisions=_decisions(awaiting_restore=["trips"]))])

    offer = ui.locator("[data-testid='drive-decisions-offer']")
    expect(offer).to_contain_text("this drive is carrying", timeout=30_000)
    expect(offer).to_contain_text("trips")


def test_the_refusal_reaches_the_screen_in_its_own_order(ui: Page) -> None:
    """One wording, three surfaces, and this is the one a mid-crisis user reads. The ORDER is the
    message: safe and readable, then why, then the remedy - asserted here as rendered text rather
    than as a string that exists in the payload."""
    refusal = (
        "Your names are safe and readable: /tmp/here/.truestill-decisions.json\n"
        "is plain text and opens in any editor, with no Truestill at all.\n"
        "This version cannot use them - they were written by a newer Truestill "
        "(format 2; this one reads 1).\n"
        "Upgrade Truestill, then run:  truestill restore /tmp/here"
    )
    _show(ui, [_drive("Desk HDD", "u1", decisions=_decisions(refusal=refusal))])

    shown = ui.locator("[data-testid='drive-decisions-refusal']")
    expect(shown).to_contain_text("safe and readable", timeout=30_000)
    text = shown.inner_text()
    assert text.index("safe and readable") < text.index("cannot use them") < text.index("Upgrade")
    for offer_of_help in ("overwrite", "convert", "discard", "delete"):
        assert offer_of_help not in text.lower(), f"the refusal offers to {offer_of_help}"


def test_an_unplugged_drive_shows_no_decisions_line_at_all(ui: Page) -> None:
    """THE ABSENCE TEST, AND THE ONE MOST LIKELY TO BE VACUOUS - an absent line is absent before
    the page loads, so asserting its absence proves nothing on its own.

    Made non-vacuous by rendering TWO drives and waiting for the CONNECTED one's date to arrive.
    That positive signal can only be produced by the finished render, so by the time the offline
    card is examined, a decisions line would already be there if the code put one there. A
    single-drive version of this test passes against a blank screen.

    The rule it guards: the saved date is a fact about what is ON THE DRIVE, and a drive that is
    not here cannot be asked - so the card says nothing rather than the last thing it saw.
    """
    _show(
        ui,
        [
            _drive("Desk HDD", "u1", decisions=_decisions()),
            _drive("Away HDD", "u2", path=None, reach="offline", decisions=None),
        ],
    )

    expect(ui.locator("[data-testid='drive-decisions-saved']")).to_contain_text(
        "2026-08-09", timeout=30_000
    )
    expect(ui.locator("[data-testid='drive-offline']")).to_be_visible()
    # One date line on the screen, and it belongs to the connected drive.
    expect(ui.locator("[data-testid='drive-decisions-saved']")).to_have_count(1)
    expect(ui.locator("#drives-list")).to_contain_text("Away HDD")
