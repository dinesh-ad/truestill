"""The undated report routes to the screen that can FIX a date, not only to one that finds it.

`(ahb)`. Stats names the undated pile in its **Completeness** card and its only action sent the
user to **Find** - which locates files by path and cannot set a date - while the rescue that can
sits **two cards above on the same screen**, in *How your dates were determined*: the tier
drill-down carries the `sha256` and the `Set date` inputs that `POST /api/dates/confirm` needs.

⚠ **AND THE SENTENCE BESIDE THE BUTTON CLAIMED FIND COULD FIX THEM** - *"Opens Find with
'Undated' so you can locate and fix dating gaps."* Find does no such thing. That is
`IMPLEMENTATION_STANDARDS.md` §9's user-facing-truth contract: a screen saying an action does
something it cannot.

**Why it matters more than a missing link.** `(ii)` ruled that a hand-fix *"is actively reverted,
which is worse than not supporting it"*, and `(aha)` traces what a user who reaches for an
external EXIF tool actually gets - a duplicate, or `verify` advising them to overwrite their own
edit. The route offered here is what keeps them out of that path, and the moment they need it is
the moment they read the undated count.

**Pinned from pytest, so the browser lane stays off.** `test_the_rearrange_card_name.py` is the
precedent, and its subject is this defect solved once already for a different feature: a built
feature nobody could find, while the manual procedure they were offered instead is exactly what it
replaces.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "src" / "truestill_app"


def _script() -> str:
    return (_APP / "static" / "app.js").read_text(encoding="utf-8")


def _completeness_actions() -> str:
    """Everything the Completeness card offers about undated files.

    ⚠ **Anchored on the GUARD, not on one button.** The first draft anchored on
    ``data-stats-action="undated"`` and, once a second action was added above it, silently
    captured only the lower block - so three assertions failed against a correct fix. A helper
    that can silently narrow is the same shape as a collector that silently finds nothing.
    """
    script = _script()
    # The guard on the ACTIONS, not the one on the metric's `at-risk` class a few lines above -
    # which is what the first anchor matched, and what this helper's own floor caught.
    start = script.index('${completeness.undated_files ? `<div class="actions">')
    end = script.index(': ""}', start)
    block = script[start:end]
    assert "data-stats-action" in block, "the helper captured no actions - the anchor moved"
    return block


def test_the_undated_report_offers_a_route_to_the_rescue() -> None:
    """⚠ **FAILS BEFORE THE FIX** - the only action was `undated`, which opens Find."""
    actions = _completeness_actions()

    assert 'data-stats-action="set-dates"' in actions, (
        "the undated report offers no route to the date rescue. A user reads the count here and "
        "the screen that can fix it is two cards above, unnamed and unlinked - which is the "
        "moment they reach for an external tool instead."
    )


def test_the_route_reuses_the_tier_drill_down_rather_than_a_second_path() -> None:
    """One way to open the undated list, not two.

    The drill-down already carries the `sha256` the rescue is keyed on. A second path to the same
    list is the drift `ALL_RULES` and `check_product_name.SUBCOMMANDS` each produced once.
    """
    script = _script()
    handler = script[script.index('statsAction === "set-dates"') :][:600]

    assert 'data-date-tier="none"' in handler, (
        "the route must open the existing tier drill-down, addressed by the raw DateSource value"
    )


def test_no_screen_claims_find_can_fix_a_date() -> None:
    """§9: an action may not say it does something it cannot.

    Anti-vacuity for the test above - adding a second button while leaving the false sentence
    beside the first would satisfy it and leave the screen still lying.
    """
    assert "locate and fix dating gaps" not in _script(), (
        "Find locates files by path; it cannot set a date. The sentence must not claim it can."
    )


def test_the_rescue_route_names_no_count() -> None:
    """⚠ **The label must survive the self-drain.**

    A confirmed file leaves the tier (`Catalog.files_in_date_tier` filters on `date_source`;
    `confirm_date` sets it), and a user sees one page at a time - so a total in the label is wrong
    twice over: it shrinks as they work, and it reads as a wall rather than a task. The label
    names the ACTION, never the size of the pile.
    """
    actions = _completeness_actions()
    label = re.search(r'data-stats-action="set-dates"[^>]*>([^<]+)<', actions)

    assert label is not None, "the rescue button is gone"
    assert not re.search(r"\d", label.group(1)), (
        f"the rescue label carries a number: {label.group(1)!r}. The count shrinks as the user "
        "works and they only ever see one page of it."
    )
    assert "${" not in label.group(1), "the label interpolates a value, which is a count in hiding"


# --- cry-wolf -----------------------------------------------------------------------------


def test_the_route_is_not_offered_when_there_is_nothing_to_fix() -> None:
    """A route to an empty screen is its own small lie. `(ahb)` Q303.

    ⚠ **This was already true of the OLD button and is the reason the guard is the fix rather
    than an addition**: the Completeness card renders whenever the library is non-empty, so with
    zero undated files the screen offered *"Review undated files"* and sent the user to a search
    that finds nothing.
    """
    actions = _completeness_actions()

    assert "completeness.undated_files" in actions, (
        "the undated actions render unconditionally, so a library with every date known is still "
        "offered a route to an empty result"
    )


def test_the_report_still_renders_its_route_when_files_are_undated() -> None:
    """The other half of the guard: it must gate on the count, not suppress the block outright."""
    actions = _completeness_actions()

    assert "data-stats-action" in actions, "the guard removed the actions entirely"
    assert re.search(r"completeness\.undated_files\s*\?", actions), (
        "the guard must render the route WHEN there are undated files, not instead of them"
    )


def test_find_is_still_reachable_for_locating_them() -> None:
    """Locating is a real need and this entry does not remove it - it stops it claiming to fix."""
    assert 'data-stats-action="undated"' in _script(), (
        "the Find route was removed; `(ahb)` corrects what it claims, it does not delete it"
    )
