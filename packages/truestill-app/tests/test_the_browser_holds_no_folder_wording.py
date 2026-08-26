"""(aer) The browser prints the folder wording it is given, and holds none of its own.

**The constraint this enforces, in the maintainer's words:** *"The reason must drive the remedy
from one place. The whole defect is that hidden folders have a different remedy from unreadable
ones, so if `app.js` and the CLI each hold their own mapping of reason to sentence, the structure
has moved the duplication rather than removed it."*

That is not hypothetical. Before `(aer)` the unreadable remedy existed **three times**: twice in
`cli.py` verbatim (`_print_skipped` and `_print_inventory_skipped`), and a third time in `app.js`
**worded differently again** - *"then preview again"* against the CLI's *"then run again"*. One
sentence, three copies, two spellings.

So the payload carries `label` and `remedy` already worded by `models`, and this pins that the
browser did not quietly grow its own copy back. It is a **wiring** assertion, which §3 says is
what a source check may honestly claim - the browser lane proves the flow, this proves there is
only one home for the words.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.models import (
    FolderSkip,
    UncomparedReason,
    folder_skip_label,
    folder_skip_remedy,
    uncompared_label,
    uncompared_remedy,
)

_APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"


def test_the_source_is_actually_read() -> None:
    """Non-emptiness first: a scan over a file that moved reports the same green as a clean one."""
    source = _APP_JS.read_text(encoding="utf-8")

    assert len(source) > 10_000, f"app.js looks wrong or moved: {len(source)} bytes"
    assert "skipped_folders" in source, "the folder groups are not rendered at all"


def test_the_browser_prints_the_wording_it_is_given() -> None:
    """The label and the remedy come from the payload, not from a branch on `reason`."""
    source = _APP_JS.read_text(encoding="utf-8")

    assert "g.label" in source, "the heading is not taken from the payload"
    assert "g.remedy" in source, "the remedy is not taken from the payload"


def test_the_browser_holds_no_copy_of_the_sentences() -> None:
    """⚠ The one that matters. A literal here means the duplication came back.

    Asserted against `models`' real strings rather than a remembered phrase, so rewording the
    remedy cannot make this guard stop looking at the right thing.
    """
    source = _APP_JS.read_text(encoding="utf-8")

    for reason in FolderSkip:
        remedy = folder_skip_remedy(reason)
        label = folder_skip_label(reason)
        assert remedy not in source, (
            f"app.js contains the {reason.value} remedy verbatim - the browser has its own copy "
            "again, which is what the payload's shape exists to prevent"
        )
        assert label not in source, f"app.js contains the {reason.value} heading verbatim"


def test_the_browser_does_not_branch_on_the_reason() -> None:
    """A `reason === "hidden"` branch is the map arriving one keystroke at a time."""
    source = _APP_JS.read_text(encoding="utf-8")

    for reason in FolderSkip:
        for form in (f'"{reason.value}"', f"'{reason.value}'"):
            assert f"reason === {form}" not in source, (
                f"app.js branches on reason {form}; the payload already carries what to say"
            )


def test_the_browser_holds_no_uncompared_wording() -> None:
    """`(aev)`'s half of the same rule: the near-duplicate sentences live in `models` only.

    ⚠ **Checked against `models`' REAL strings**, not a phrase copied into this file. A guard
    written against a remembered sentence stops guarding the moment the real one is reworded, and
    goes green while doing it - which is how `(aer)`'s browser copy survived a mutation.

    ⚠ **AND IT LOOPS THE ENUM, so a THIRD reason is covered the day it is declared.** This
    asserted two module constants until `(ahq)` made the wording a table; a guard naming its
    subjects one by one covers exactly the members somebody remembered to add it for.
    §4's seventy-second member - loop the derived inventory, assert into the declaration.
    """
    source = _APP_JS.read_text(encoding="utf-8")

    for reason in UncomparedReason:
        label = uncompared_label(reason)
        remedy = uncompared_remedy(reason)
        assert label not in source, (
            f"app.js holds its own copy of the {reason.value} label ({label!r}). It must print "
            f"the payload's `label`, which core worded once."
        )
        assert remedy not in source, (
            f"app.js holds its own copy of the {reason.value} remedy ({remedy!r}). Two surfaces "
            f"wording one sentence is exactly what (aer) removed."
        )


def test_the_browser_reads_both_new_fields() -> None:
    """Non-emptiness, and the failure this file exists for. §4's fifty-second member.

    A payload can be perfectly correct while nothing on the page reads it - which is precisely
    how `unreadable_folders` reached the browser and stopped there for weeks. The two assertions
    above only prove the browser does not hold the *words*; deleting the renderer entirely would
    satisfy them both.
    """
    source = _APP_JS.read_text(encoding="utf-8")

    assert "uncompared" in source, "the payload's `uncompared` is read by nothing in the browser"
    assert "suppressed_diagnostics" in source, (
        "the suppressed-noise tally reaches the browser and stops there, so a run that removed "
        "787 lines looks identical to one that removed none"
    )


def test_the_browser_renders_every_uncompared_group_not_only_the_first() -> None:
    """`(ahq)` made `uncompared` a LIST, and a renderer that kept indexing it as one object
    would show the first reason and drop the rest - silently, which is the failure the whole
    group exists to end.

    ⚠ **A SOURCE CHECK, AND ITS LIMIT IS THE FILE'S LIMIT** (see the module docstring): it proves
    the payload is treated as a collection, not that a person sees two headings. The browser lane
    proves the flow. What it does catch is the exact regression - reverting to `uncompared.label`.
    """
    source = _APP_JS.read_text(encoding="utf-8")

    for indexed in (
        "uncompared.label",
        "uncompared.remedy",
        "uncompared.total",
        "uncompared.files",
    ):
        assert indexed not in source, (
            f"app.js reads `{indexed}` off the payload as a single object. `uncompared` is a list "
            f"of groups; the second reason would render as nothing at all."
        )
    maps = "uncompared\n    .map(" in source or "uncompared.map(" in source
    assert maps, (
        "app.js does not map over the uncompared groups, so at most one of them can reach a screen"
    )
