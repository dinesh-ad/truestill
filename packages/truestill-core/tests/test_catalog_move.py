"""Moving a catalog to the OS-conventional location is an explicit, refusing, copy-only act.

**Why it copies and refuses rather than moving.** The mechanism this imitates - wxWidgets'
``MigrateLocalFile`` - has a documented failure: an automatic migration that finds a file in
*both* locations renames over the destination, and does not check for symlinks. For a custody
catalog that is data loss. So every one of those choices is inverted here:

* **copy, never move**, and the original stays where it is - the user deletes it when satisfied;
* **never overwrite** - if both exist, refuse and report both, with sizes and times, because
  "both exist" without a way to tell them apart is a dead end;
* **never follow or clobber a symlink** - someone may have linked the old path to the new one
  deliberately, and following it would copy a file onto itself.

**And it must say what it did NOT do.** After a copy the old catalog is still there and is still
the one that gets used, because `default_catalog_path` prefers it. Someone who copies, deletes
nothing, and then wonders why their edits go to the old file has been misled by a report that
only listed its successes - the same failure the three-state rescue card exists to prevent.

**The cache is not migrated, and that is said rather than silently skipped.** It is keyed by
absolute path and machine-specific; copying it would carry a hundred percent misses to the new
location while looking like it had done something useful.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from truestill_core.catalog_move import CatalogMoveOutcome, move_catalog_to_standard


def _legacy(tmp_path: Path, body: bytes = b"catalog-bytes") -> Path:
    legacy = tmp_path / "reports" / "catalog.sqlite"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(body)
    return legacy


def test_a_catalog_is_copied_to_the_standard_location(tmp_path: Path) -> None:
    legacy = _legacy(tmp_path)
    destination = tmp_path / "data" / "catalog.sqlite"

    result = move_catalog_to_standard(legacy, destination)

    assert result.outcome is CatalogMoveOutcome.COPIED
    assert destination.read_bytes() == b"catalog-bytes"


def test_the_original_is_left_exactly_where_it_was(tmp_path: Path) -> None:
    """Copy, never move. The user deletes the original when they are satisfied, not truestill."""
    legacy = _legacy(tmp_path)
    destination = tmp_path / "data" / "catalog.sqlite"

    move_catalog_to_standard(legacy, destination)

    assert legacy.exists()
    assert legacy.read_bytes() == b"catalog-bytes"


def test_the_report_says_the_old_catalog_is_still_the_one_in_use(tmp_path: Path) -> None:
    """The three-state-card rule applied to a terminal: leave with an accurate belief.

    `default_catalog_path` prefers the legacy file while it exists, so a copy alone changes
    nothing about which catalog gets written to next.
    """
    legacy = _legacy(tmp_path)

    result = move_catalog_to_standard(legacy, tmp_path / "data" / "catalog.sqlite")

    assert result.still_in_use == legacy
    detail = result.detail.lower()
    assert "still" in detail
    assert "remove" in detail or "delete" in detail


def test_the_report_says_the_cache_was_not_migrated(tmp_path: Path) -> None:
    """Said, not silently skipped - and with the reason, so it does not read as an omission."""
    legacy = _legacy(tmp_path)

    detail = move_catalog_to_standard(legacy, tmp_path / "data" / "catalog.sqlite").detail.lower()

    assert "cache" in detail
    assert "rebuil" in detail or "machine" in detail


# --- the refusals ------------------------------------------------------------------------------


def test_it_refuses_when_the_destination_already_exists(tmp_path: Path) -> None:
    """The documented failure of the mechanism this imitates: renaming over the destination."""
    legacy = _legacy(tmp_path, b"the-one-in-use")
    destination = tmp_path / "data" / "catalog.sqlite"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"a-different-catalog")

    result = move_catalog_to_standard(legacy, destination)

    assert result.outcome is CatalogMoveOutcome.DESTINATION_EXISTS
    assert destination.read_bytes() == b"a-different-catalog", "the destination was overwritten"


def test_the_refusal_lets_the_user_tell_the_two_apart(tmp_path: Path) -> None:
    """ "Both exist" without a way to distinguish them is a dead end."""
    legacy = _legacy(tmp_path, b"x" * 40)
    destination = tmp_path / "data" / "catalog.sqlite"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"y" * 900)

    detail = move_catalog_to_standard(legacy, destination).detail

    assert str(legacy) in detail
    assert str(destination) in detail
    assert "40" in detail, f"the in-use catalog's size is not shown: {detail}"
    assert "900" in detail, f"the destination catalog's size is not shown: {detail}"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_it_refuses_a_symlinked_source(tmp_path: Path) -> None:
    """Someone may have linked the old path at the new one deliberately - following it would
    copy a file onto itself."""
    real = tmp_path / "real.sqlite"
    real.write_bytes(b"catalog-bytes")
    legacy = tmp_path / "reports" / "catalog.sqlite"
    legacy.parent.mkdir(parents=True)
    legacy.symlink_to(real)

    result = move_catalog_to_standard(legacy, tmp_path / "data" / "catalog.sqlite")

    assert result.outcome is CatalogMoveOutcome.SYMLINK_REFUSED
    assert not (tmp_path / "data" / "catalog.sqlite").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_it_refuses_a_symlinked_destination(tmp_path: Path) -> None:
    """Writing through a destination symlink would clobber whatever it points at."""
    legacy = _legacy(tmp_path)
    elsewhere = tmp_path / "elsewhere.sqlite"
    elsewhere.write_bytes(b"do-not-touch")
    destination = tmp_path / "data" / "catalog.sqlite"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(elsewhere)

    result = move_catalog_to_standard(legacy, destination)

    assert result.outcome is CatalogMoveOutcome.SYMLINK_REFUSED
    assert elsewhere.read_bytes() == b"do-not-touch"


def test_nothing_to_move_is_its_own_outcome(tmp_path: Path) -> None:
    """Not an error, and not silence: the user asked a reasonable question."""
    result = move_catalog_to_standard(
        tmp_path / "reports" / "catalog.sqlite", tmp_path / "data" / "catalog.sqlite"
    )

    assert result.outcome is CatalogMoveOutcome.NOTHING_TO_MOVE


def test_a_catalog_already_at_the_standard_location_is_not_copied_onto_itself(
    tmp_path: Path,
) -> None:
    """Cry-wolf half: the ordinary post-migration state must be reported calmly, not refused."""
    same = tmp_path / "data" / "catalog.sqlite"
    same.parent.mkdir(parents=True)
    same.write_bytes(b"catalog-bytes")

    result = move_catalog_to_standard(same, same)

    assert result.outcome is CatalogMoveOutcome.ALREADY_STANDARD
    assert same.read_bytes() == b"catalog-bytes"
