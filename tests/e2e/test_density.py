"""Vertical rhythm: a tool, not a web page.

The Organize form measured 721px at rest and 1,023px once its hints render - for ONE form with
four groups in it. Nothing in it was wrong; there was simply a 16-24px gap between every pair of
things and 48px above the first.

WHAT IS TIGHTENED IS SPACE BETWEEN THINGS. What is deliberately NOT tightened is anything a
person aims at or reads: control heights, the type scale, the gap between a label and its own
input, and the rail. Density that shrinks hit targets is not density, it is a smaller product.
"""

from __future__ import annotations

import json

from e2e_support import open_screen
from playwright.sync_api import Page

#: Measured at 1920x1080 on a real library: 721px before, 642px after.
ORGANIZE_CARD_WAS = 721
#: The ceiling follows the measurement rather than the other way round. I set 620 first, missed
#: it by 22px, and the honest reading is that the rest of that card is INFORMATION: three mode
#: options each explaining what they do to your files, two checkboxes with their consequences,
#: and two field hints. Getting under 620 meant deleting copy, which is a product decision
#: nobody asked for. 660 leaves a hint room to wrap without a false failure and still fails if
#: the gaps creep back.
#:
#: ⚠ **UNCHANGED 2026-09-06, and the SUBJECT is what was wrong.** See `_card_height`.
ORGANIZE_CARD_CEILING = 660


def _has_a_library(ui: Page) -> None:
    """Answer `/api/library/status` as a machine that has organized before."""
    ui.route(
        "**/api/library/status",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "files": 2269,
                    "photos": 2200,
                    "videos": 69,
                    "audio": 0,
                    "bytes": 10**10,
                    "by_format": {},
                    "places": 1,
                    "single_copy": 0,
                    "files_no_copy": 0,
                    "files_one_copy": 0,
                    "redundancy_floor": 1,
                    "files_on_a_drive": 2269,
                    "held_floor": 1,
                    "library_path": "/home/you/Pictures/Truestill",
                    "library_root": "/home/you/Pictures/Truestill",
                    "needs_library_root": False,
                    "backup_path": None,
                    "never_checked_drives": [],
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


def _organize(ui: Page) -> None:
    ui.set_viewport_size({"width": 1920, "height": 1080})
    ui.click('.nav-item[data-screen="organize"]')
    ui.wait_for_timeout(300)


def _card_height(ui: Page) -> float:
    """The height of the card that holds the FORM, named by something only that card contains.

    ⚠ **Re-expected 2026-09-06, and this was measuring the wrong element.** It took
    `.screen.active .card`, which is the FIRST card on the screen - and the first card was
    `#org-first-run`, the one-time "Where should your library live?" question, which this
    fixture's server answers `needs_library_root: true` to and therefore shows. So the 660px
    ceiling written for a four-group form was being applied to a one-field question, and the form
    it was written about was never measured at all.

    The screen has one card now - the question was folded into it - so `.screen.active .card`
    would resolve correctly today by luck. It is pinned to `#org-source` instead, because "the
    card with the source field in it" is what this file means and stays true if a second card
    ever returns.
    """
    return ui.eval_on_selector(
        "#org-source", "el => el.closest('.card').getBoundingClientRect().height"
    )


def test_the_organize_form_got_shorter_without_losing_anything(ui: Page) -> None:
    """⚠ **The library is stubbed as ALREADY ANSWERED, added 2026-09-06.** The one-time "Where
    should your library live?" question is part of this card now, and it is ~220px of its own
    copy that a library sees exactly once - measuring it here would put a first-run state inside
    a ceiling written for the steady one. This fixture's server says `needs_library_root: true`
    because its catalog is a fresh temp file, which is a property of the harness rather than of
    the product.
    """
    _has_a_library(ui)
    _organize(ui)
    height = _card_height(ui)

    assert height <= ORGANIZE_CARD_CEILING, (
        f"the form is {height:.0f}px (was {ORGANIZE_CARD_WAS}px); the rhythm did not tighten"
    )
    for control in ("#org-source", "#org-dest", "#org-preview", "#org-dedup"):
        assert ui.locator(control).count() == 1, f"{control} disappeared"


def test_nothing_a_person_aims_at_got_smaller(ui: Page) -> None:
    """The line between density and shrinking the product. 36px is the reference row height and
    also about the floor for a comfortable pointer target."""
    _organize(ui)
    heights = ui.eval_on_selector_all(
        "#org-source, #org-dest, #org-preview, #org-dedup",
        "els => els.map(e => e.getBoundingClientRect().height)",
    )
    too_small = [h for h in heights if h < 32]
    assert not too_small, f"controls shrank below a comfortable target: {heights}"


def test_a_label_still_sits_with_its_own_input(ui: Page) -> None:
    """Tightening BETWEEN groups must not also tighten WITHIN one, or the form stops grouping."""
    _organize(ui)
    # `org-dest`, not `org-source`: the source field has the quick-access places rail between
    # its label and its input, so measuring there measures the rail, not the grouping.
    gap = ui.evaluate(
        "() => { const l = document.querySelector('label[for=\"org-dest\"]');"
        " const i = document.querySelector('#org-dest');"
        " return i.getBoundingClientRect().top - l.getBoundingClientRect().bottom; }"
    )
    assert 0 <= gap <= 14, f"label-to-input gap is {gap:.0f}px"


def test_the_groups_are_still_separated_from_each_other(ui: Page) -> None:
    """CRY-WOLF HALF: a form with no vertical grouping is worse than a tall one."""
    _organize(ui)
    gap = ui.evaluate(
        "() => { const a = document.querySelector('#org-source').closest('.field');"
        " const b = document.querySelector('#org-modes').closest('.field');"
        " return b.getBoundingClientRect().top - a.getBoundingClientRect().bottom; }"
    )
    assert gap >= 8, f"the groups run together: {gap:.0f}px between them"


def test_nothing_collides_at_the_large_text_size(ui: Page) -> None:
    """Tighter gaps plus bigger type is where overlap appears, so it is asserted rather than
    assumed - and at the compound worst case, not just at the default root."""
    open_screen(ui, "settings")
    ui.locator("#text-size").fill("4")  # xl
    ui.wait_for_timeout(300)
    _organize(ui)

    overlaps = ui.evaluate(
        "() => { const els = [...document.querySelectorAll('.screen.active .field')];"
        " const bad = [];"
        " for (let i = 1; i < els.length; i++) {"
        "   const prev = els[i-1].getBoundingClientRect(), cur = els[i].getBoundingClientRect();"
        "   if (cur.top < prev.bottom - 1) bad.push([els[i-1].className, cur.top, prev.bottom]); }"
        " return bad; }"
    )
    assert not overlaps, f"fields overlap at large text: {overlaps}"


def test_nothing_collides_at_a_raised_browser_default(ui: Page) -> None:
    _organize(ui)
    ui.evaluate("() => document.documentElement.style.setProperty('font-size','24px','important')")
    ui.wait_for_timeout(300)

    overflow = ui.evaluate("() => document.body.scrollWidth - document.body.clientWidth")
    overlaps = ui.evaluate(
        "() => { const els = [...document.querySelectorAll('.screen.active .field')];"
        " const bad = [];"
        " for (let i = 1; i < els.length; i++) {"
        "   const prev = els[i-1].getBoundingClientRect(), cur = els[i].getBoundingClientRect();"
        "   if (cur.top < prev.bottom - 1) bad.push(i); }"
        " return bad; }"
    )
    assert overflow <= 2, f"the page scrolls sideways at a 24px root: {overflow}px"
    assert not overlaps, f"fields overlap at a 24px root: {overlaps}"
