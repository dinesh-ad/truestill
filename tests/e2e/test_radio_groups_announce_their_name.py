"""A radio set announces the question it answers, not just its options.

**The defect, and why it was worth fixing rather than noting.** Three radio groups carried their
heading in a bare `<label>` with no `for` and no wrapped control - `How to organize`, `Theme`,
`Text size`. A screen reader announced the options with no idea what they were options *for*:
"Copy into an organized folder, radio, 1 of 3" with the question missing. That sits beside code
that already sets `aria-current`, `aria-busy`, `role="alert"` and an `aria-label` on the wordmark,
so the surrounding surface pays attention to this and these three were the gap.

**Asserted by ROLE and ACCESSIBLE NAME, never by tag.** `get_by_role("group", name=...)` is what a
screen reader actually resolves; a test for `<fieldset>` would pass on markup that is nested wrong
or whose `<legend>` is not first, and would fail on a correct `role="radiogroup"` rewrite. The tag
is the current means; the announcement is the requirement.

**Provenance:** found by a one-off `biome lint` run (Biome 2.5.7, 2026-08-10) that was measured
and **not adopted** - see `BACKLOG.md`, *Consciously out of scope*. The findings were real; the
tool is not a dependency.
"""

from __future__ import annotations

import pytest
from e2e_support import open_screen
from playwright.sync_api import Page, expect

#: Each radio set, by the screen it lives on and the question it asks.
_GROUPS = [
    ("organize", "How to organize", "org-mode"),
    ("settings", "Theme", "theme"),
    ("settings", "Text size", "text-size"),
]


@pytest.mark.parametrize(("screen", "question", "radio_name"), _GROUPS)
def test_a_radio_set_is_a_named_group(
    ui: Page, screen: str, question: str, radio_name: str
) -> None:
    """The group exists, carries the question as its name, and holds the radios.

    The last part matters: a correctly named group that does not CONTAIN the inputs announces
    the question and then leaves the options outside it, which is the same silence in a different
    shape.
    """
    open_screen(ui, screen)

    group = ui.get_by_role("group", name=question)
    expect(group).to_have_count(1)
    expect(group.locator(f'input[type="radio"][name="{radio_name}"]')).to_have_count(3)


@pytest.mark.parametrize(("screen", "question", "radio_name"), _GROUPS)
def test_the_group_does_not_change_what_is_on_screen(
    ui: Page,
    screen: str,
    question: str,
    radio_name: str,  # noqa: ARG001 - from the shared table; this half checks chrome only
) -> None:
    """A semantics fix must not become a design change.

    `<fieldset>` arrives with browser chrome - a border, padding, and an intrinsic minimum width -
    and this app had no fieldset anywhere before, so nothing was resetting it. The question text
    must still read as the field label it always did, and the group must not draw a box.
    """
    open_screen(ui, screen)
    group = ui.get_by_role("group", name=question)

    box = group.evaluate(
        "el => { const s = getComputedStyle(el);"
        " return {border: s.borderTopWidth, pad: s.paddingTop, min: s.minInlineSize}; }"
    )
    assert box["border"] == "0px", f"{question}: the fieldset is drawing a border: {box}"
    assert box["pad"] == "0px", f"{question}: the fieldset kept its default padding: {box}"
