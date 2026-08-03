"""Timeline membership is a set, so adding a rule to it is one edit and not seven.

**Why this exists, before the rule that needs it.** "Does this file belong on the timeline?" was
asked by `rule == TIMELINE_RULE` in seven places - event clustering, migration routing, trip
placement, heavy-day counting, placement. `layout.classify` has an `assert_never`, so mypy
*forces* a new `RuleName` member to be handled there; it cannot force these seven. Missing one
would land a file on the timeline while silently excluding it from event naming or trip
placement, which is the "a fix reached one copy and not its twin" failure
`ENGINEERING_STANDARD.md` §4 records as this repo's recurring one.

**The set and the router must agree, and that is now the load-bearing check.** Until
`CAMERA_FILENAME` arrived, `TIMELINE_RULES` held one member and the whole file could rest on
"membership equals equality". It holds two, so that equivalence is simply false and asserting
it would be asserting a lie. What replaced it is stronger and total over the enum: for **every**
`RuleName`, membership in `TIMELINE_RULES` agrees with what `classify` does with it. Those are
the two edits a new timeline rule needs, in two files, and each is exactly what would be
forgotten without the other - a rule in the router's timeline arm but not the set gets timeline
placement with no event or trip; in the set but not the router, the reverse.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from truestill_core.layout import TIMELINE_RULE, TIMELINE_RULES, Placement, RenderContext, classify
from truestill_core.models import RuleName

REPO = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = (
    REPO / "packages/truestill-core/src",
    REPO / "packages/truestill-cli/src",
    REPO / "packages/truestill-app/src",
)

#: The shape this commit exists to remove: a direct comparison against the representative rule.
_COMPARISON = re.compile(r"[!=]=\s*TIMELINE_RULE\b|TIMELINE_RULE\s*[!=]=")


def test_the_set_holds_exactly_the_rules_that_reach_the_timeline_today() -> None:
    """Stated as a literal, so growing the set is a decision somebody made on purpose.

    A rule reaching the timeline is a product change - the file lands in a dated month folder
    among the owner's own photos rather than in a labelled bin - and it should never be
    something a refactor can do quietly.
    """
    assert frozenset({RuleName.DEVICE, RuleName.CAMERA_FILENAME}) == TIMELINE_RULES
    assert TIMELINE_RULE is RuleName.DEVICE


@pytest.mark.parametrize("rule", list(RuleName))
def test_the_set_and_the_router_agree_about_every_rule(rule: RuleName) -> None:
    """Total over the enum: `TIMELINE_RULES` and `classify` cannot drift apart.

    These are the two edits a new timeline rule needs, and each is what would be forgotten
    without the other. `assert_never` forces the router arm; nothing forces the set. An empty
    `RenderContext` is used deliberately - with no trip, event or heavy day, a timeline rule
    can only produce `EVERYDAY`, so any non-side-bin answer is the timeline answer.
    """
    placement = classify(rule, RenderContext(category="X"))
    assert (rule in TIMELINE_RULES) == (placement is not Placement.SIDE_BIN)


@pytest.mark.parametrize("rule", list(RuleName))
def test_the_bare_string_a_caller_passes_answers_the_same_as_the_member(rule: RuleName) -> None:
    """`RuleName` is a `StrEnum`, so it hashes as its own string.

    Not decoration: `migrate._rule_for` is typed `RuleName | str` and callers do pass the plain
    token. A set keyed on members that silently said "no" to every string would send every
    migrated camera file to a side bin.
    """
    assert (str(rule) in TIMELINE_RULES) == (rule in TIMELINE_RULES)


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
