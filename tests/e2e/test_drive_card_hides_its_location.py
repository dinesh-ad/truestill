"""The drive card's path is reveal-on-demand - `(acs)`.

**The concern is exactly one thing:** nobody glancing at the app should learn which cloud service
the user pays for. The drive card was the one place a full absolute path - a provider's name, a
username, a folder layout - appeared on screen every time Backups opened, asked for by nobody.

**The rule, and it answers both directions:** *a path is shown unasked only when it is doing
identity work.* So the path collapses by default and renders **expanded** where two drives share a
label - because two cards both titled `Morrowkeep` are told apart by nothing else, and collapsing
there would collapse two drives into one indistinguishable card. That is precisely what `(acs)`'s
invariant forbids: hiding may reduce detail, never the count, a drive's identity as a distinct
thing, or the fact that something is unverified.

⚠ **This defends against a glance and a screenshot, not against inspection.** `data-open` and
`data-path` still carry the path, because the Open and *Check now* buttons take it. Making it
inspection-proof means those buttons take a uuid the server resolves - a real change, not needed
for this concern and not made. **These tests therefore assert on rendered TEXT, never on the
absence of the attribute**, so they describe the protection that actually exists.
"""

from __future__ import annotations

import json
from typing import Any

from e2e_support import open_backups
from playwright.sync_api import Page, expect

_CLOUD = "/home/someone/BigCloudProvider/Photos"


def _drive(label: str, uuid: str, path: str, **over: Any) -> dict[str, Any]:
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
        "path": path,
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
    open_backups(ui)


def _card_text(ui: Page) -> str:
    return ui.eval_on_selector("#drives-list", "el => el.innerText")


# --------------------------------------------------------------- collapsed by default


def test_the_location_is_not_on_screen_until_it_is_asked_for(ui: Page) -> None:
    """The whole point. Waits on a POSITIVE signal - the drive's label - before asserting the
    absence, per §4's sixteenth member: an empty `#drives-list` would satisfy this assertion
    before any request was answered."""
    _show(ui, [_drive("Morrowkeep", "u1", _CLOUD)])

    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)
    assert "BigCloudProvider" not in _card_text(ui), _card_text(ui)
    expect(ui.locator("#drives-list summary")).to_contain_text("Show location")


def test_asking_for_it_shows_it(ui: Page) -> None:
    """The other half - hiding a fact the user cannot retrieve would be a different defect."""
    _show(ui, [_drive("Morrowkeep", "u1", _CLOUD)])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    ui.locator("#drives-list summary").click()

    assert _CLOUD in _card_text(ui), _card_text(ui)


# --------------------------------------------------------------- identity work overrides


def test_two_drives_sharing_a_label_show_their_paths_without_being_asked(ui: Page) -> None:
    """`(acs)`'s invariant at the point it binds hardest. Both cards read `Morrowkeep`; with the
    location collapsed they would be **two indistinguishable cards** - the count preserved and the
    identity destroyed, which is the failure the invariant names."""
    _show(
        ui,
        [
            _drive("Morrowkeep", "u1", "/mnt/photos"),
            _drive("Morrowkeep", "u2", _CLOUD),
        ],
    )
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    text = _card_text(ui)
    assert "/mnt/photos" in text, text
    assert _CLOUD in text, text


def test_the_expanded_state_comes_from_the_collision_not_from_a_default(ui: Page) -> None:
    """**The case most likely to be quietly right for the wrong reason.**

    A card that rendered expanded because everything renders expanded would satisfy the test above
    while the feature did nothing. This asserts both states in ONE render: the colliding pair open,
    the distinctly-named drive beside them closed. No default can produce that.
    """
    _show(
        ui,
        [
            _drive("Morrowkeep", "u1", "/mnt/photos"),
            _drive("Morrowkeep", "u2", _CLOUD),
            _drive("The Memory Cabinet", "u3", "/mnt/cabinet"),
        ],
    )
    expect(ui.locator("#drives-list")).to_contain_text("Cabinet", timeout=30_000)

    open_states = ui.eval_on_selector_all("#drives-list details", "els => els.map(e => e.open)")
    assert open_states == [True, True, False], open_states
    assert "/mnt/cabinet" not in _card_text(ui), _card_text(ui)


# --------------------------------------------------------------- guards


def test_the_rest_of_the_card_is_unchanged(ui: Page) -> None:
    """A GUARD, passing before and after by design. Hiding the path must reduce DETAIL only - the
    count, the drive's distinctness and its verification state all stay on screen, which is the
    invariant's own wording."""
    _show(ui, [_drive("Morrowkeep", "u1", _CLOUD)])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    text = _card_text(ui)
    assert "2 photos" in text, text
    assert "last checked" in text, text
    expect(ui.locator("#drives-list .drive-check")).to_have_count(1)


def test_check_now_still_works_with_the_location_collapsed(ui: Page) -> None:
    """A GUARD. `Check now` reads `data-path`, which was never displayed, so verification is
    unaffected by hiding the text. Asserted because a privacy change that quietly disabled
    verification would be the worst possible trade."""
    _show(ui, [_drive("Morrowkeep", "u1", _CLOUD)])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    ui.locator("#drives-list .drive-check").click()

    expect(ui.locator("#verify-path")).to_have_value(_CLOUD)


def test_the_reveal_draws_no_separator_through_the_card(ui: Page) -> None:
    """A GUARD, and the reason `details.more` gained an `inline` modifier rather than being reused
    as-is. `details.more` is a section break by design - a border-top and margin meant for a card's
    FOOT - and dropped among the card's facts it draws a rule through the middle of it.

    Same precedent as the `<fieldset>` work: a semantics or privacy fix must not become a design
    change, and the way to keep it honest is to measure the chrome rather than trust it.
    """
    _show(ui, [_drive("Morrowkeep", "u1", _CLOUD)])
    expect(ui.locator("#drives-list")).to_contain_text("Morrowkeep", timeout=30_000)

    box = ui.eval_on_selector(
        "#drives-list details",
        "el => { const s = getComputedStyle(el);"
        " return {border: s.borderTopWidth, margin: s.marginTop, pad: s.paddingTop}; }",
    )
    assert box["border"] == "0px", box
    assert box["margin"] == "0px", box
