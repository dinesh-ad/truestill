"""The text-size preference, persisted per catalog the way the sidebar's collapse is.

Three named steps, never a number: a free px field invites a value that breaks the layout, and
the answer to "how big" is already the browser's - this only nudges it.

Normalisation is server-side and total. A stored value is user data by the time it is read back:
a hand-edited catalog, a downgrade, a future step that no longer exists. Anything unrecognised
resolves to `medium`, which declares no root size at all and hands the question back to the
browser.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app import service
from truestill_core.catalog import Catalog


def test_an_untouched_catalog_answers_medium(tmp_path: Path) -> None:
    """Medium is not a size. It is the absence of one - see `test_text_size_setting.py` in e2e."""
    assert service.text_size_state(tmp_path / "c.sqlite") == {"size": "medium"}


def test_each_step_round_trips_through_the_catalog(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    for size in ("small", "medium", "large"):
        assert service.set_text_size(size, db) == {"ok": True, "size": size}
        assert service.text_size_state(db) == {"size": size}


def test_the_preference_lands_in_the_catalog_under_its_own_key(tmp_path: Path) -> None:
    """Same store as the sidebar's collapse, so it travels with the library rather than with
    the browser profile - moving machines keeps it (`docs/moving-machines.md`)."""
    db = tmp_path / "c.sqlite"
    service.set_text_size("large", db)

    with Catalog(db) as catalog:
        assert catalog.get_setting(service.TEXT_SIZE_KEY) == "large"


def test_an_unrecognised_stored_value_resolves_to_medium_rather_than_reaching_the_page(
    tmp_path: Path,
) -> None:
    """A stored value is user data. `huge` on the root would be an invalid `font-size` the
    browser drops - silently, and only for some of the page."""
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.set_setting(service.TEXT_SIZE_KEY, "huge")

    assert service.text_size_state(db) == {"size": "medium"}


def test_a_submitted_value_is_normalised_before_it_is_stored(tmp_path: Path) -> None:
    """Never store what was sent. The catalog must not accumulate values nothing can render."""
    db = tmp_path / "c.sqlite"

    assert service.set_text_size("LARGE", db) == {"ok": True, "size": "large"}
    assert service.set_text_size("  small  ", db) == {"ok": True, "size": "small"}
    assert service.set_text_size(None, db) == {"ok": True, "size": "medium"}
    assert service.set_text_size(17, db) == {"ok": True, "size": "medium"}

    with Catalog(db) as catalog:
        assert catalog.get_setting(service.TEXT_SIZE_KEY) == "medium"


def test_the_steps_are_a_closed_set_the_stylesheet_can_be_checked_against() -> None:
    """The CSS declares a rule per step. A step added here with no rule renders as medium and
    looks like the setting was ignored, so the set is stated once and asserted against."""
    assert service.TEXT_SIZES == ("small", "medium", "large")
