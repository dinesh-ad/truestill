"""Every contrast ratio the rail writes down is recomputed from the colour beside it.

⚠ **THIS EXISTS BECAUSE THE NUMBERS WENT STALE AND WERE REPORTED TWICE WITHOUT BEING FIXED.**
The rail's ground changed from `#17150f` to `#101012` on 2026-09-06 and again to rose-charcoal
`#161014` (**`D20`**, 2026-09-14). The block's own comment once claimed every value was
*"re-derived against the new ground, none carried over"*. Six of the nine were carried over
anyway after the first change - the 2026-08-13 figures, measured against a ground that no longer
exists. They were found by measuring a *new* token, mentioned, mentioned again, and left.

**`(ago)`'s bar is met on evidence rather than on principle.** A census guard is an artifact that
has to earn itself, and a guard written green over a class with no instances earns nothing. This
one is written over **six live instances**, in a block whose own prose claims the opposite, and it
is mechanical where the alternative is somebody remembering to re-run a calculation by hand every
time a hex changes. That is exactly the criterion `CLAUDE.md` states for a rule that may be read
on demand: *something mechanical, not the reading, enforces it.*

**What it cannot see**, said plainly: whether a colour is the *right* colour, whether the ratio
clears the threshold its own use needs, and whether the prose around it is true. It checks one
thing - that a number written next to a hex is the number that hex produces.
"""

from __future__ import annotations

import re
from pathlib import Path

_CSS = Path(__file__).resolve().parents[1] / "src/truestill_app/static/app.css"

#: `--name: #hex;` followed by a comment whose FIRST number-colon-one is the ratio against the
#: rail. The first is load-bearing: two of these comments carry a SECOND ratio that is
#: deliberately against something else - `--rail-muted` names `--fg-muted` at 3.91:1 here, and
#: `--rail-success` names `--success` tuned for white at 5.30:1. A parser that took the last, or
#: any, would compare a rail ratio against a white one and fail on a correct file.
_DECLARATION = re.compile(
    r"^\s*(--rail-[a-z-]+):\s*(#[0-9a-fA-F]{6});\s*/\*\s*([0-9]+\.[0-9]+):1", re.MULTILINE
)

#: The ground every one of these is measured against. Read from the file rather than written
#: here, so changing the rail's background cannot leave this test measuring the old one - which
#: is the exact failure it exists to catch, one level up.
_GROUND = re.compile(r"^\s*--rail-bg:\s*(#[0-9a-fA-F]{6});", re.MULTILINE)

#: WCAG 2.2 1.4.11. Applies to what the rail uses as **non-text UI** - a state dot, an active
#: edge - and NOT to the values that only separate surfaces, which the block's own comment
#: already says carry no floor.
NON_TEXT_FLOOR = 3.0


def _channel(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    """WCAG relative luminance. Written out rather than imported: a dependency taken for nine
    lines of arithmetic is the kind of thing `ENGINEERING_STANDARD.md` §1 asks to justify, and
    this cannot be justified."""
    raw = colour.lstrip("#")
    red, green, blue = (int(raw[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(one: str, other: str) -> float:
    first, second = luminance(one), luminance(other)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _declared() -> tuple[str, list[tuple[str, str, float]]]:
    css = _CSS.read_text(encoding="utf-8")
    ground = _GROUND.search(css)
    assert ground, "the rail has no --rail-bg; there is nothing to measure against"
    return ground.group(1), [
        (name, hexval, float(claimed)) for name, hexval, claimed in _DECLARATION.findall(css)
    ]


def test_the_instrument_reproduces_a_ratio_that_was_never_in_doubt() -> None:
    """**The instrument is checked before it is trusted**, which is what the block being tested
    says it did and is the only reason to believe the numbers below.

    `--rail-accent` was re-measured on 2026-09-06, the day the ground changed, and is the one
    value nobody has disputed. If this arithmetic cannot reproduce it, every other verdict in
    this file is noise.
    """
    assert round(contrast("#fda4af", "#161014"), 2) == 9.93
    assert round(contrast("#ffffff", "#000000"), 2) == 21.0
    assert round(contrast("#161014", "#161014"), 2) == 1.0


def test_every_recorded_ratio_is_the_one_its_colour_produces() -> None:
    """The claim each comment makes, checked against the hex it sits beside.

    Tolerance is 0.005 - the figures are written to two decimals, so anything larger would let a
    value drift by a full digit while this stayed green.
    """
    ground, declared = _declared()
    wrong = [
        f"{name}: {hexval} is {contrast(hexval, ground):.2f}:1 against {ground}, comment says {claimed:.2f}"
        for name, hexval, claimed in declared
        if abs(contrast(hexval, ground) - claimed) > 0.005
    ]

    assert not wrong, (
        "the rail's recorded contrast ratios are not what its colours produce:\n  "
        + "\n  ".join(wrong)
    )


def test_the_block_still_records_a_ratio_for_every_colour_that_carries_one() -> None:
    """**Anti-vacuity, and it is the assertion that keeps this file honest.**

    The test above iterates whatever the regex finds. Delete every comment and it passes by
    checking nothing - a green run over an empty list, which is the dead-assertion shape this
    repo has a census of. Nine tokens declare a ratio today; a change that drops one should be a
    decision, not a silent narrowing of what is measured.
    """
    _, declared = _declared()

    assert len(declared) == 9, [name for name, _, _ in declared]


def test_the_state_dot_clears_the_floor_for_non_text_ui_in_every_state() -> None:
    """`DECISIONS.md` D16 §5's account dot, against WCAG 2.2 1.4.11's 3:1.

    ⚠ **Contrast was never the dot's problem and this test says so rather than implying it.** All
    four colours clear the floor by more than a factor of two, and the defect that prompted this
    was that three of five states shared one of them - an indicator that carries no information
    in the majority case, which a person stops reading and then misses when it changes. That is
    fixed by shape and by hue, not by brightness, and it is asserted in the browser where shape
    is visible. This holds the floor so a future recolour cannot quietly fall through it.
    """
    ground, declared = _declared()
    colours = {name: hexval for name, hexval, _ in declared}

    for token in ("--rail-success", "--rail-accent", "--rail-warn", "--rail-muted"):
        assert token in colours, f"{token} lost its recorded ratio, so the dot's colour is unpinned"
        assert contrast(colours[token], ground) >= NON_TEXT_FLOOR, token
