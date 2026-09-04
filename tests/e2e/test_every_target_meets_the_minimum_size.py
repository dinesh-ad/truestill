"""Every clickable thing is at least 24x24 CSS pixels, or is spaced far enough to be excused.

**WCAG 2.2 SC 2.5.8 (Target Size, Minimum), Level AA.** Measured in the browser against real
bounding boxes, never read off the stylesheet: a rule's declared `width` is not the rendered box
once padding, borders and flex have had their say, and a CSS read cannot see the exception below
at all.

⚠ **THE SPACING EXCEPTION IS THE HALF THAT MAKES THIS FAIR**, and a guard that skipped it would
fail on things that genuinely conform. An undersized target passes when a **24 px diameter circle
centred on it touches no other target**. So a small isolated control is fine and a small control
in a crowded row is not, which is the distinction the success criterion is actually about.

**Why this exists, and why now.** This is the floor the restyle arc is about to lean on: three
named density modes (Compact / Comfortable / Spacious) are a later arc, and **a Compact mode built
without this guard ships an accessibility regression by definition** - it is the one change that
makes every target smaller at once. Written before that arc rather than after, so it is a control
rather than an apology. Measured 2026-09-04: nothing in `static/` and nothing in `tests/e2e/`
carried a hit-target rule - `git grep -nIiE "min-height: *(24|44)|hit target|tap target"` returned
only coincidental token values.

**Exceptions NOT implemented, and named rather than left silent.** SC 2.5.8 also excuses inline
targets in a sentence, targets whose size is fixed by the user agent and not modified by the
author, and cases where a particular presentation is essential. None applies to this shell today -
every control here is authored - so the guard asserts the general rule. If one ever does apply,
the honest move is to widen this docstring with the instance, not to soften the threshold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest
from e2e_support import open_screen
from playwright.sync_api import Page

#: Shell-scoped: it belongs to no screen, so no screen's commit carries it. Same reasoning as
#: `test_rail_shell.py`, which states it for the migration's early-warning set.
pytestmark = pytest.mark.shell

#: SC 2.5.8's floor, in CSS pixels.
MINIMUM = 24.0

#: What counts as a target. Deliberately broad - `[tabindex]` and the two ARIA roles are included
#: because a div someone made clickable is exactly the kind that gets built undersized.
_TARGETS = (
    "a[href], button, input:not([type=hidden]), select, textarea, "
    "[role=button], [role=link], [role=checkbox], [role=radio], [role=tab], "
    '[tabindex]:not([tabindex="-1"])'
)

_COLLECT = """
(selector) => [...document.querySelectorAll(selector)]
  .filter((el) => {
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  })
  .map((el) => {
    const r = el.getBoundingClientRect();
    return {
      name: el.tagName.toLowerCase()
        + (el.id ? '#' + el.id : '')
        + (el.getAttribute('class') ? '.' + el.getAttribute('class').split(/\\s+/)[0] : ''),
      x: r.x, y: r.y, w: r.width, h: r.height,
    };
  })
  .filter((t) => t.w > 0 && t.h > 0)
"""


@dataclass(frozen=True)
class Target:
    """One clickable box as the browser actually laid it out."""

    name: str
    x: float
    y: float
    w: float
    h: float

    @property
    def undersized(self) -> bool:
        return self.w < MINIMUM or self.h < MINIMUM

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)


def _distance_to(box: Target, point: tuple[float, float]) -> float:
    """Distance from `point` to the nearest edge of `box`; 0 when the point is inside it."""
    px, py = point
    dx = max(box.x - px, 0.0, px - (box.x + box.w))
    dy = max(box.y - py, 0.0, py - (box.y + box.h))
    return math.hypot(dx, dy)


def offenders(targets: list[Target]) -> list[str]:
    """Undersized targets that the spacing exception does not excuse.

    The exception is applied as SC 2.5.8 words it: the 24 px **diameter** circle centred on the
    undersized target must not reach another target - so the test is a 12 px radius against every
    other box, itself excluded.
    """
    found: list[str] = []
    for target in targets:
        if not target.undersized:
            continue
        crowded = [
            other
            for other in targets
            if other is not target and _distance_to(other, target.centre) < MINIMUM / 2
        ]
        if crowded:
            found.append(
                f"{target.name} is {target.w:.0f}x{target.h:.0f} and "
                f"{crowded[0].name} is within 12px of its centre"
            )
    return found


def _targets(ui: Page) -> list[Target]:
    raw = ui.evaluate(_COLLECT, _TARGETS)
    return [Target(name=t["name"], x=t["x"], y=t["y"], w=t["w"], h=t["h"]) for t in raw]


#: Every screen the rail can reach. **The shell as it loads is one screen out of seven**, and it
#: is not the dense one: Settings carries four save buttons, a select, six text inputs and a
#: pattern table, and Organize carries the radio cards. A floor asserted on the default screen
#: alone is a floor asserted where the controls are fewest.
SCREENS = ("organize", "events", "import", "backups", "find", "stats", "settings")


def test_every_target_is_large_enough_or_far_enough(ui: Page) -> None:
    """The floor, on the shell as it loads."""
    failures = offenders(_targets(ui))

    assert not failures, (
        "these controls are under 24x24 CSS pixels and are not spaced far enough to be "
        "excused by SC 2.5.8:\n    " + "\n    ".join(failures)
    )


@pytest.mark.parametrize("screen", SCREENS)
def test_every_screens_targets_are_large_enough_or_far_enough(ui: Page, screen: str) -> None:
    """The same floor, on every screen rather than on whichever one loads first.

    ⚠ **The first version of this guard measured the default screen and nothing else** - it
    passed, and that pass said nothing about the six screens a person actually spends time on.
    A guard that is complete for what happens to be in front of it is `ENGINEERING_STANDARD.md`
    §4's *"complete for everything that exists and silently partial for what does not"*, one
    screen wide.
    """
    open_screen(ui, screen)
    failures = offenders(_targets(ui))

    assert not failures, (
        f"on the {screen} screen, these controls are under 24x24 CSS pixels and are not spaced "
        "far enough to be excused by SC 2.5.8:\n    " + "\n    ".join(failures)
    )


def test_the_guard_found_targets_to_measure(ui: Page) -> None:
    """The cry-wolf half. An empty list passes the test above while asserting nothing, and a
    selector that stopped matching is exactly how that would happen silently."""
    targets = _targets(ui)

    assert len(targets) > 10, f"only {len(targets)} targets found; the selector is not matching"
    assert any(t.w >= MINIMUM and t.h >= MINIMUM for t in targets), (
        "no target reaches the floor at all, which means the boxes are not being measured"
    )


def test_the_spacing_exception_excuses_an_isolated_control() -> None:
    """A small control alone on the page conforms, and must not be reported. Without this the
    guard could be made unconditional and the test above would still pass."""
    lone = Target(name="button.lone", x=0, y=0, w=22, h=22)
    far = Target(name="button.far", x=200, y=200, w=40, h=40)

    assert offenders([lone, far]) == []


def test_the_spacing_exception_does_not_excuse_a_crowded_one() -> None:
    """Proved by mutation of the input rather than of the code: the same undersized control with
    a neighbour beside it is the case SC 2.5.8 refuses."""
    small = Target(name="button.small", x=0, y=0, w=22, h=22)
    neighbour = Target(name="button.neighbour", x=14, y=0, w=22, h=22)

    assert offenders([small, neighbour]), "a crowded undersized target was excused"
