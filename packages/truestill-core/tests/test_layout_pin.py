"""The pin: a default change must never silently re-shape a library that already exists.

`layout_template` is persisted only when a user explicitly sets one, so every library organized
with the defaults renders through whatever the default constant happens to be. Changing that
constant would move the next run of every such library while leaving its existing tree behind --
a library split across two structures, with no prompt and no migration. The pin writes the
layout in force at the time, whatever it is; it has no knowledge of any particular shape.

The trigger is narrow on purpose, and both halves of it are pinned here: *files have already
been placed* and *no layout is stored*. A library that has only ever been scanned or previewed
has nothing on disk to protect and must receive the new default like any fresh one.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.layout import (
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPLATE_STRING,
    LAYOUT_TEMPLATE_KEY,
    Placement,
    effective_layout_string,
    pin_existing_layout,
    resolve_scheme,
)
from truestill_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import execute


def _resolution(source: Path, sha: str) -> Resolution:
    decision = Decision(
        source=source,
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path("Camera/Undated") / source.name,
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _place(catalog: Catalog, sha: str = "sha-1") -> None:
    """Organize one file for real -- the only path that marks a catalog as having placed."""
    catalog.record_uploaded(
        source_path=f"/src/{sha}.jpg",
        original_name=f"{sha}.jpg",
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=10,
        captured_at="2021-06-15T10:30:00",
        category="Camera",
        relative="Camera/2021/06/x.jpg",
        event_id=None,
        albums=[],
        drive_uuid=None,
    )


def test_an_organized_library_with_no_stored_layout_is_pinned(tmp_path: Path) -> None:
    """The case the pin exists for: files on disk, nothing recorded about their shape."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _place(catalog)
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None

        assert pin_existing_layout(catalog) is True

        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == DEFAULT_TEMPLATE_STRING
        assert (
            resolve_scheme(catalog).template_for(Placement.EVERYDAY).template
            == DEFAULT_TEMPLATE_STRING
        )


def test_a_scanned_but_never_organized_library_gets_the_new_default(tmp_path: Path) -> None:
    """The other half of the predicate, and the reason it is not "the catalog has rows".

    Scanning, previewing and an event-review session all write to the catalog -- events,
    skipped clusters, settings, drives -- without placing a single file. Such a library has no
    layout worth protecting and must not be held back from the new default.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.record_event(
            name="Goa", slug="goa", start_date="2021-06-15", file_count=3, signature="sig-1"
        )
        catalog.record_skip("sig-2")
        catalog.upsert_drive(uuid="A", label="Drive A")
        assert catalog.count() == 0  # rows exist, but nothing was ever placed

        assert pin_existing_layout(catalog) is False

        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None
        assert (
            resolve_scheme(catalog).template_for(Placement.EVERYDAY).template
            == DEFAULT_TEMPLATE.template
        )


def test_a_chosen_layout_is_never_overwritten(tmp_path: Path) -> None:
    """A user who picked a layout keeps it, placed files or not."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.set_setting(LAYOUT_TEMPLATE_KEY, "{yyyy}/{yyyy}-{mm}")
        _place(catalog)

        assert pin_existing_layout(catalog) is False
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) == "{yyyy}/{yyyy}-{mm}"  # theirs, kept


def test_pinning_is_idempotent(tmp_path: Path) -> None:
    """It announces once, because it only fires once."""
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _place(catalog)
        assert pin_existing_layout(catalog) is True
        assert pin_existing_layout(catalog) is False
        assert pin_existing_layout(catalog) is False


def test_preview_and_run_agree_before_the_pin_has_fired(tmp_path: Path) -> None:
    """The invariant that keeps previews honest.

    A preview must not write a setting (a read never writes), so it cannot pin -- but if it
    resolved differently from the run that follows, the plan a user approved would not be the
    plan that executed. `effective_layout_string` makes the two agree without writing.
    """
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _place(catalog)

        previewed = (
            resolve_scheme(catalog).template_for(Placement.EVERYDAY).template
        )  # what a preview would render through
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None  # and it wrote nothing

        pin_existing_layout(catalog)  # now the run fires the pin
        assert resolve_scheme(catalog).template_for(Placement.EVERYDAY).template == previewed


def test_a_fresh_catalog_reports_no_effective_layout(tmp_path: Path) -> None:
    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert effective_layout_string(catalog) is None
        assert catalog.has_placed_files() is False


def test_a_plain_folder_organize_with_no_drive_marker_counts_as_placed(tmp_path: Path) -> None:
    """The false negative the pin must not have, proved end to end rather than by reading.

    Organizing into an ordinary folder records no `file_copies` row, because there is no drive
    marker and therefore no drive to attribute the copy to. If "placed" were keyed on
    `file_copies`, such a library would look untouched and the pin would skip it -- silently
    re-shaping the very library it exists to protect. The signal is a `files` row.
    """
    source = tmp_path / "src"
    source.mkdir()
    photo = source / "a.jpg"
    photo.write_bytes(b"some-bytes")
    destination = tmp_path / "out"  # a plain folder: no marker is ever written here

    with Catalog(tmp_path / "c.sqlite") as catalog:
        assert catalog.has_placed_files() is False

        results = execute(
            [_resolution(photo, "sha-plain")],
            LocalDestination(destination),
            apply=True,
            catalog=catalog,
            drive_uuid=None,  # exactly the no-drive-marker case
        )

        assert [r.status for r in results] == [ActionStatus.UPLOADED]
        assert not (destination / ".truestill-drive.json").exists()  # really no marker
        assert catalog.copies_for_migration("any") == []  # and really no copy row
        assert catalog.has_placed_files() is True  # yet the pin sees it

        assert pin_existing_layout(catalog) is True
