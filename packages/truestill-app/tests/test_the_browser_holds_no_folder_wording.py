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

from truestill_core.models import FolderSkip, folder_skip_label, folder_skip_remedy

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
