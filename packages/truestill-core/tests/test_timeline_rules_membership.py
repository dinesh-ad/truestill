"""Timeline membership is a set, so adding a rule to it is one edit and not seven.

**Why this exists, before the rule that needs it.** "Does this file belong on the timeline?" was
asked by `rule == TIMELINE_RULE` in seven places - event clustering, migration routing, trip
placement, heavy-day counting, placement. `layout.classify` has an `assert_never`, so mypy
*forces* a new `RuleName` member to be handled there; it cannot force these seven. Missing one
would land a file on the timeline while silently excluding it from event naming or trip
placement, which is the "a fix reached one copy and not its twin" failure
`ENGINEERING_STANDARD.md` §4 records as this repo's recurring one.

**Provably behaviour-neutral.** `TIMELINE_RULES` holds exactly one member, and `RuleName` is a
`StrEnum`, so `x in TIMELINE_RULES` and `x == TIMELINE_RULE` agree for every input including
the plain strings some callers pass. That equivalence is asserted below rather than assumed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from truestill_core.layout import TIMELINE_RULE, TIMELINE_RULES
from truestill_core.models import RuleName

REPO = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = (
    REPO / "packages/truestill-core/src",
    REPO / "packages/truestill-cli/src",
    REPO / "packages/truestill-app/src",
)

#: The shape this commit exists to remove: a direct comparison against the representative rule.
_COMPARISON = re.compile(r"[!=]=\s*TIMELINE_RULE\b|TIMELINE_RULE\s*[!=]=")


def test_the_set_holds_exactly_the_representative_rule_today() -> None:
    """One member, which is what makes the conversion carry no behaviour change at all."""
    assert frozenset({TIMELINE_RULE}) == TIMELINE_RULES
    assert TIMELINE_RULE is RuleName.DEVICE


@pytest.mark.parametrize(
    "rule",
    [RuleName.DEVICE, RuleName.SOFTWARE, RuleName.FALLBACK, RuleName.SCREENSHOT_NAME, "device"],
)
def test_membership_and_equality_agree_for_every_input(rule: RuleName | str) -> None:
    """The equivalence the refactor rests on, asserted rather than assumed.

    `RuleName` is a `StrEnum`, so it hashes and compares as its own string - which is why a
    caller passing the bare `"device"` gets the same answer from a set as from `==`.
    """
    assert (rule in TIMELINE_RULES) == (rule == TIMELINE_RULE)


def test_no_source_file_compares_against_the_representative_rule() -> None:
    """The deliverable: seven places that must be found become one that must be updated.

    `TIMELINE_RULE` itself stays - it is still the right thing to *construct* with, and
    `migrate` and the layout samples do exactly that. What must not come back is asking
    membership by equality, because the next rule added to the timeline would then have to
    find all seven again.
    """
    offenders: list[str] = []
    for root in SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _COMPARISON.search(line):
                    offenders.append(
                        f"{path.relative_to(REPO).as_posix()}:{number}: {line.strip()}"
                    )

    assert not offenders, (
        f"{len(offenders)} place(s) still ask timeline membership by equality:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse `in TIMELINE_RULES` instead. Equality means a rule added to the timeline has "
        "to be found in every one of these again, and `assert_never` cannot catch a miss here."
    )


def test_the_guard_can_see_the_shape_it_bans() -> None:
    """Anti-vacuity: a regex that matched nothing would pass this file forever."""
    for sample in (
        "if rule == TIMELINE_RULE:",
        "if category.rule != TIMELINE_RULE:",
        "        if TIMELINE_RULE == rule:",
    ):
        assert _COMPARISON.search(sample), sample


def test_the_guard_spares_legitimate_construction() -> None:
    """Cry-wolf: building *with* the rule is correct and must not be flagged."""
    for spared in (
        "    rule: RuleName | str = TIMELINE_RULE,",
        "    return TIMELINE_RULE if decided == ROUTE_TIMELINE else RuleName.FALLBACK",
        'SampleRow("Camera undated", TIMELINE_RULE, RenderContext(category="Camera")),',
        "from truestill_core.layout import TIMELINE_RULE, TIMELINE_RULES",
    ):
        assert not _COMPARISON.search(spared), spared
