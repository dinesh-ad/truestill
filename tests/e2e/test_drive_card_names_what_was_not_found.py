"""The drive card states what a check looked for and did not find. `(abg)` Stage 2.

**The rule being pinned is that this number is stated BESIDE the count, never subtracted from
it.** The custody sentence in the rail is a claim about now, so it excludes copies that were not
found. This card reports history - what was written here - and a count that quietly dropped to
zero would destroy the only clue a person has to what happened to their files. Two surfaces, two
opposite rules, on purpose; this file holds the second one to the screen.

**§4's sixteenth member.** Every absence assertion below waits on a positive signal first, because
this card renders empty and then fills - so "no not-found line" is satisfied by the blank page
before any request has been answered.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from playwright.sync_api import Page, expect

#: THE MIGRATION'S EARLY-WARNING SYSTEM. This file belongs to no screen, so no screen's commit
#: carries it - and an island landing on a DIFFERENT screen changes the DOM around it without
#: touching a line here. `make e2e-shell` runs the set after every island; see
#: `docs/react-migration-plan.md`.
pytestmark = pytest.mark.shell


def _drive(label: str, uuid: str, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "uuid": uuid,
        "files": 2269,
        "not_found": 0,
        "not_found_at": None,
        "photos": 2269,
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


def _show(ui: Page, drives: list[dict[str, Any]]) -> None:
    ui.route(
        "**/api/drives**",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "library": {
                        "files": 2269,
                        "photos": 2269,
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


def test_the_card_names_the_shortfall_and_dates_it(ui: Page) -> None:
    """The maintainer's own case, as a sentence: 2,269 recorded here, none of them found."""
    _show(ui, [_drive("Output", "u1", not_found=2269, not_found_at="2026-08-11T09:00:00+00:00")])

    note = ui.locator("[data-testid='drive-not-found']")
    expect(note).to_contain_text("2,269 not found", timeout=30_000)
    expect(note).to_contain_text("on 2026-08-11")


def test_the_recorded_count_survives_beside_it(ui: Page) -> None:
    """THE POINT OF THE WHOLE RULE. A drive whose copies were all missing must still say what was
    written there - otherwise the card reads as an empty drive nobody ever used, and the user has
    lost the only evidence that 2,269 files were once copied here."""
    _show(ui, [_drive("Output", "u1", not_found=2269, not_found_at="2026-08-11T09:00:00+00:00")])

    card = ui.locator(".card", has=ui.locator("[data-testid='drive-not-found']"))
    expect(card).to_contain_text("2,269 photos", timeout=30_000)


def test_an_ordinary_drive_carries_no_such_line(ui: Page) -> None:
    """CRY-WOLF HALF. Every healthy drive has nothing missing, so a line that rendered anyway
    would be on every card forever and learned as noise.

    Non-vacuous: the card's own file count is waited for first, so the list is known to have
    rendered before the absence is asserted.
    """
    _show(ui, [_drive("Desk HDD", "u1")])

    expect(ui.get_by_text("2,269 photos")).to_be_visible(timeout=30_000)
    expect(ui.locator("[data-testid='drive-not-found']")).to_have_count(0)
