"""`Catalog.set_local_setting`'s allow-list is the decisions document's exclusion list. `(afc)`

The two are the same rule seen from opposite ends: a setting is safe to write **without** firing a
decisions save exactly when the document would have excluded it anyway. They are separate
constants because `decisions` takes a catalog, so importing it from `catalog` would close a cycle.

⚠ **Two spellings of one rule is how they drift**, and the drift is silent in the dangerous
direction: widen `_LOCAL_SETTING_PREFIXES` alone and a real decision stops reaching the user's
drives, with nothing to notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core.catalog import _LOCAL_SETTING_PREFIXES, Catalog
from truestill_core.decisions import _EXCLUDED_SETTING_PREFIXES


def test_the_two_lists_are_identical() -> None:
    assert _LOCAL_SETTING_PREFIXES == _EXCLUDED_SETTING_PREFIXES, (
        "a setting can now be written without syncing that the document would still carry, or "
        "the reverse. They are one rule."
    )


def test_the_lists_are_not_empty() -> None:
    """Non-emptiness first: two empty tuples are equal and would pass the test above."""
    assert _EXCLUDED_SETTING_PREFIXES, "the exclusion list is empty; the guard is aimed at nothing"


def test_a_setting_the_document_would_carry_is_refused(tmp_path: Path) -> None:
    """⚠ The guard that keeps `set_local_setting` from being a footgun with a reassuring name.

    Skipping the decisions sync is safe **only** because the document excludes these prefixes. A
    caller that reached for this with an ordinary key would stop that decision reaching the user's
    drives, and nothing would say so - the silent direction. Found by a surviving mutation: with
    the check removed, no test failed.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        with pytest.raises(ValueError, match="machine-local"):
            catalog.set_local_setting("layout.template", "year-month-event")

        # ...and the ones the document really does exclude are accepted.
        for prefix in _EXCLUDED_SETTING_PREFIXES:
            catalog.set_local_setting(f"{prefix}probe", "x")


def test_a_local_write_leaves_the_catalog_clean_and_a_real_one_does_not(tmp_path: Path) -> None:
    """The behaviour the prefix guard exists to protect: `dirty` drives the drive sync."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.mark_clean()
        catalog.set_local_setting("path_hint.drive.abc", "/somewhere")
        assert catalog.dirty is False, (
            "recording where a drive was seen marked the catalog dirty, which fires a decisions "
            "save to every reachable drive - turning a read into a write to the user's disk"
        )

        catalog.set_setting("layout.template", "year-month-event")
        assert catalog.dirty is True, "a real decision must still reach the drives"
