"""Timeline membership is decided by a RULE, and the label set it leans on is exhaustive. `(ahw)`

Two guards, and the first is why the second is safe to build on.

⚠ **`deterministic_side_bin_labels()` was load-bearing for ONE subsystem and guarded by NOTHING.**
Checked before this file existed: `grep -rn "deterministic_side_bin_labels" packages/*/tests tests/`
returned nothing at all, against one production consumer (`migrate.label_routes`). `(ahw)` makes it
load-bearing for a second - every timeline query now asks *"is this label NOT a known side bin"* -
and inverting four predicates onto an unguarded constant is the trade this repo keeps filing
letters about.

The set is **derived**, not listed (`categorize.deterministic_side_bin_labels`), so a new
`NAME_PATTERNS` entry joins on its own. A new side-bin rule carrying its **own** label constant
would not, and the timeline would silently gain those files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.categorize import (
    CAMERA_LABEL,
    NAME_PATTERNS,
    SCREENSHOT_LABEL,
    deterministic_side_bin_labels,
)
from truestill_core.exif import REQUESTED_TAGS
from truestill_core.layout import Placement, RenderContext, classify
from truestill_core.models import SAVED_LABEL, RuleName

#: Every label a side-bin rule can emit, BY RULE, read off the rule bodies rather than inferred.
#: This is the DERIVED inventory; `deterministic_side_bin_labels()` is the DECLARATION.
_SIDE_BIN_LABELS: dict[RuleName, frozenset[str]] = {
    RuleName.SCREENSHOT_METADATA: frozenset({SCREENSHOT_LABEL}),
    RuleName.SCREENSHOT_NAME: frozenset({SCREENSHOT_LABEL}),
    RuleName.FILENAME_CONVENTION: frozenset(entry.label for entry in NAME_PATTERNS),
    RuleName.SAVED_HEURISTIC: frozenset({SAVED_LABEL}),
    RuleName.FALLBACK: frozenset({SAVED_LABEL}),
}

#: The rules whose label cannot be enumerated, with WHY. ⚠ A declared exception is a decision; an
#: unhandled rule is the shape that regrows. Both are open-ended by construction, which is exactly
#: what `categorize.deterministic_side_bin_labels`'s own docstring says.
_OPEN_ENDED: dict[RuleName, str] = {
    RuleName.SOFTWARE: (
        "names the folder after whatever an app stamped, so its label is unbounded. It also "
        "cannot fire today: `Software` is not in `exif.REQUESTED_TAGS` - see the `(aaq)` guard "
        "below, which is what keeps that true"
    ),
    RuleName.DEVICE: (
        "under `--by-device` the label is the hardware name, unbounded and unenumerable in SQL. "
        "It is a TIMELINE rule, so it is not a side bin at all - listed here only so no rule is "
        "silently unaccounted for"
    ),
}


def _side_bin_rules() -> set[RuleName]:
    """The DERIVED inventory: every rule `layout.classify` routes to the side bin."""
    context = RenderContext(category="x")
    return {rule for rule in RuleName if classify(rule, context) is Placement.SIDE_BIN}


def test_every_side_bin_rule_is_accounted_for() -> None:
    """Loop the router's own answer; assert into the two declarations. The 72nd member."""
    declared = set(_SIDE_BIN_LABELS) | set(_OPEN_ENDED)
    unaccounted = sorted(rule for rule in _side_bin_rules() if rule not in declared)
    assert not unaccounted, (
        f"{unaccounted} routes to the side bin and is in neither table. Add the labels it emits "
        "to _SIDE_BIN_LABELS, or declare it open-ended WITH the reason - and if its label is not "
        "in deterministic_side_bin_labels(), the timeline will silently gain those files."
    )


def test_every_enumerable_side_bin_label_is_declared_deterministic() -> None:
    """⚠ **The guard that makes the inversion safe.**

    A timeline query now asks *"is this label NOT a known side bin"*. If a side-bin rule can emit a
    label the constant does not carry, that label reads as timeline and the file appears on a
    screen it does not belong on.
    """
    deterministic = deterministic_side_bin_labels()
    for rule, labels in _SIDE_BIN_LABELS.items():
        missing = sorted(labels - deterministic)
        assert not missing, (
            f"{rule} can emit {missing}, which deterministic_side_bin_labels() does not carry. "
            "Every timeline query would read those files as timeline files."
        )


def test_the_constant_carries_nothing_a_side_bin_rule_cannot_emit() -> None:
    """The other direction: a label declared deterministic that no rule produces is dead weight,
    and would wrongly exclude a real label if one ever collided with it."""
    emitted = frozenset().union(*_SIDE_BIN_LABELS.values())
    stale = sorted(deterministic_side_bin_labels() - emitted)
    assert not stale, f"{stale} is declared a deterministic side bin and no rule emits it"


def test_the_timeline_label_is_not_a_deterministic_side_bin() -> None:
    """⚠ Anti-vacuity. If `Camera` were in the set, the inverted predicate would select nothing."""
    assert CAMERA_LABEL not in deterministic_side_bin_labels()
    assert _side_bin_rules(), "the router reported no side-bin rules, so nothing above asserts"


def test_every_open_ended_rule_states_why() -> None:
    """A skip-list with empty strings would satisfy the accounting test and mean nothing."""
    for rule, reason in _OPEN_ENDED.items():
        assert len(reason) > 60, f"{rule} is declared open-ended without a reason worth reading"


def test_the_timeline_equivalence_holds_only_while_software_stays_unrequested() -> None:
    """⚠ **THE LOAD-BEARING GUARD**, and it keeps a measured fact true rather than merely observed.

    `(ahw)` inverts every timeline predicate from *"the label is `Camera`"* to *"the label is not a
    known side bin"*. Those select the same files **only because `rule_software` cannot fire**:
    `Software` is not in `exif.REQUESTED_TAGS`, a documented exemption owned by `(aaq)`. Measured
    2026-08-26 - 781 files carrying `Software` across both sample corpora and the real library,
    **zero** equal to `Camera`; and a set diff over two real catalogs returned an identical set,
    2,632 of 2,695 and 3,770 of 4,105.

    🔑 **If `Software` is ever requested, `SOFTWARE` becomes a live rule that emits an unbounded
    label, and every inverted predicate silently starts putting software-labelled files on the
    timeline.** That is the reverse of the defect `(ahw)` fixed, arriving without a symptom. This
    test is the thing that makes closing `(aaq)` a conversation instead of a surprise.

    If you are reading this because it failed: requesting `Software` is not forbidden. It means the
    inverted predicates must move to a rule test in the same change, which needs the rule persisted
    - see `(ahw)`'s refusal of a `category_rule` column and why.
    """
    assert "Software" not in REQUESTED_TAGS, (
        "`Software` has joined REQUESTED_TAGS, so `rule_software` can now fire and emit an "
        "unbounded label. Every `category NOT IN (side bins)` timeline query in catalog.py will "
        "read those files as timeline files. Move those predicates to a rule test, or keep the "
        "`(aaq)` exemption - but the two cannot both change."
    )


def _seeded(db, labels: dict[str, str]) -> Catalog:
    """A catalog holding one dated, drive-attached file per label."""
    catalog = Catalog(db)
    catalog.upsert_drive(uuid="D1", label="Output")
    for sha, label in labels.items():
        catalog.record_uploaded(
            source_path=f"/src/{sha}.jpg",
            original_name=f"{sha}.jpg",
            sha256=sha * 64,
            copy_sha256=sha * 64,
            perceptual=None,
            size=10,
            captured_at="2015-07-05T11:55:16",
            category=label,
            relative=f"2015/{sha}.jpg",
            drive_uuid="D1",
        )
    return catalog


@pytest.mark.parametrize(
    ("label", "on_timeline"),
    [
        ("Camera", True),
        ("Samsung SM-A546B", True),  # `--by-device`: the whole point of `(ahw)`
        ("Adobe Photoshop", True),  # an open-ended software family, if it ever fires
        ("Saved", False),
        ("Screenshots", False),
        ("WhatsApp", False),
    ],
)
def test_the_predicate_selects_by_side_bin_and_not_by_the_word_camera(
    tmp_path, label: str, on_timeline: bool
) -> None:
    """⚠ **The BEHAVIOUR half, and a mutation is why it exists.** `(ahw)`

    The guards above prove the label SET is exhaustive. They do not prove any query USES it -
    dropping `Saved` from `deterministic_side_bin_labels()` inside `timeline_label_sql` changed
    what every timeline query returns and **killed no test**. The declaration and the behaviour are
    different properties, and this is the third entry in a row where that gap was found by mutation
    rather than by reading.

    `Samsung SM-A546B` is the case `(ahw)` was filed for: under `--by-device` the label is the
    hardware name, and the old `category = 'Camera'` predicate matched **nothing**.
    """
    with _seeded(tmp_path / "c.sqlite", {"a": label}) as catalog:
        events = catalog.camera_copies_for_events("D1")
        hints = catalog.source_hints_for_drive("D1")
        heavy = catalog.unevented_timeline_captured_ats()
        stats = dict(catalog.stats_summary())

    assert bool(events) is on_timeline, f"{label!r} clustering membership is wrong"
    assert bool(hints) is on_timeline, f"{label!r} source-hint population is wrong"
    assert bool(heavy) is on_timeline, f"{label!r} heavy-day density population is wrong"
    assert stats["timeline_files"] == (1 if on_timeline else 0), f"{label!r} counted wrong"
    assert stats["side_bin_files"] == (0 if on_timeline else 1), f"{label!r} counted wrong"


def test_the_two_twin_queries_select_the_same_population(tmp_path) -> None:
    """`catalog.py`'s own note: the hint query and the clustering query share a filter, and that
    is load-bearing rather than incidental. They must be one ruling, so they are tested as one."""
    with _seeded(tmp_path / "c.sqlite", {"a": "Camera", "b": "Saved", "c": "Nikon D40"}) as cat:
        events = {str(row["sha256"]) for row in cat.camera_copies_for_events("D1")}
        hints = {str(row["sha256"]) for row in cat.source_hints_for_drive("D1")}
    assert events == hints
    assert len(events) == 2, "the by-device label or the camera label was dropped"


_APP_JS = (
    Path(__file__).resolve().parents[3] / "packages/truestill-app/src/truestill_app/static/app.js"
)


def test_the_category_legend_does_not_drop_folders_it_cannot_name() -> None:
    """⚠ **The one `(ahw)` site that is NOT a population filter, pinned from pytest.**

    `legendFor` filtered its folder names on `CAT_INFO[n]`, a hardcoded vocabulary of six labels.
    Under `--by-device` the camera folder is the hardware name, no key matched, `names` was empty
    and **the entire legend vanished** - a screen going blank, and the only user-visible half of
    this entry that is not a number.

    It takes a **default**, not the inversion the four SQL predicates took: this is a lookup for
    explanatory text, and `catTip` already carries the fallback. Failing open here means a folder
    gets a generic description; failing closed meant the panel disappeared.

    Asserted from pytest rather than the browser lane, per `test_the_migrate_screen_says_it_stopped`
    - the browser lane is off and these screens are being replaced, so a test that drove one would
    guard a liability.
    """
    source = _APP_JS.read_text(encoding="utf-8")
    assert len(source) > 100_000, "app.js was not actually read"

    start = source.index("function legendFor(")
    # To the function's closing brace, not a fixed character count: the explanatory comment inside
    # it is longer than any window I would have guessed, and a short slice passed the first
    # assertion while silently missing the second.
    legend = source[start : source.index("\n}", start)]
    assert "filter((n) => CAT_INFO[n])" not in legend, (
        "the legend drops folder names CAT_INFO does not know, so a --by-device library shows none"
    )
    assert "catTip(n)" in legend, "the legend no longer uses the defaulting lookup"
