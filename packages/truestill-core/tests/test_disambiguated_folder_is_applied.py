"""The disambiguated folder must reach the disk, not just the preview note.

**The defect.** `disambiguate_event_folders` computes `... (2)` / `... (3)` for two events that
render to one folder name on one date, and `migrate._disambiguated_folder_notes` throws the
computed folders away - it returns ``[f.note for f in folders if f.note]``, notes only. The
per-file render calls `layout.event_folder` directly and never sees them, so all three events
land in ONE directory while the preview states that one of them *became* `... (2)`.

**Severity, stated precisely.** `plan_migration` guards duplicate targets on the full relative
path *including the filename*, so co-locating three events does not overwrite anything: measured
on the real catalog, 2015-10-25 holds 146 files and 146 distinct filenames. No bytes are at risk.
What is wrong is that the folders merge contrary to the stated intent and **the preview says
something that will not happen** (`IMPLEMENTATION_STANDARDS.md` §9). `test_filename_safety.py`
already names this outcome "data loss by presentation", which is the accurate phrase.

**Why the existing guard did not catch it.** `test_filename_safety.py` covers
`disambiguate_event_folders` thoroughly - collisions, case-insensitivity, three-way, slug naming
- and **every one of those asserts what the function computes, never that the computed folder is
what gets used**. That is `ENGINEERING_STANDARD.md` §4's own failure: asserting a helper's output
rather than the provenance of the behaviour. These tests assert the placement instead, so they
cannot pass while the render ignores the decision.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.layout import DEFAULT_SCHEME, LayoutScheme, LayoutTemplate
from truestill_core.migrate import plan_migration

_DAY = "2015-10-25"
_NAME = "Gokul's Marriage"


def _seed_file(catalog: Catalog, root: Path, relative: str, captured: str, body: bytes) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    sha = sha256_file(path)
    catalog.record_uploaded(
        source_path=f"/src/{PurePosixPath(relative).name}",
        original_name=PurePosixPath(relative).name,
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=len(body),
        captured_at=captured,
        category="Camera",
        relative=relative,
        drive_uuid="D1",
    )
    return sha


def _three_same_day_events(catalog: Catalog, root: Path, name: str = _NAME) -> list[str]:
    """Three separately-identified events, one date, one name. Returns their file SHA-256s."""
    catalog.upsert_drive(uuid="D1", label="Drive A")
    shas = []
    for index in range(3):
        sha = _seed_file(
            catalog, root, f"in/{index}.jpg", f"{_DAY}T19:0{index}:00", f"body-{index}".encode()
        )
        event_id = catalog.record_event(
            name=name,
            slug=f"gokuls-marriage-{index}",
            start_date=_DAY,
            file_count=1,
            signature=f"signature-{index}",
        )
        catalog.set_event_id([sha], event_id)
        shas.append(sha)
    return shas


def _planned_directories(catalog: Catalog, shas: list[str]) -> list[str]:
    plan = plan_migration(catalog, "D1", DEFAULT_SCHEME)
    where = {move.sha256: move.new_relative for move in plan.moves}
    return [str(PurePosixPath(where[sha]).parent) for sha in shas]


def test_three_events_sharing_one_name_on_one_day_get_three_folders(tmp_path: Path) -> None:
    """THE DEFECT. Before the fix all three render to the same directory."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _three_same_day_events(catalog, root)
        directories = _planned_directories(catalog, shas)

    assert len(set(directories)) == 3, (
        "three separately-named events merged into one folder; the disambiguated name that "
        f"`disambiguate_event_folders` computed never reached the path: {directories}"
    )


def test_the_preview_note_describes_the_folder_that_is_actually_used(tmp_path: Path) -> None:
    """The §9 half: a note may not promise a folder the render does not produce.

    Asserting the two together is the point. Tested apart, the note and the path can each look
    correct while disagreeing with one another, which is exactly the state this file was written
    in.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _three_same_day_events(catalog, root)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME)
        directories = _planned_directories(catalog, shas)

    promised = [
        warning.split("becomes ")[1].strip("'\"")
        for warning in plan.warnings
        if "becomes " in warning
    ]
    assert promised, "no note claimed a disambiguated folder, so there is nothing to honour"
    leaves = {PurePosixPath(directory).name for directory in directories}
    for folder in promised:
        assert folder in leaves, (
            f"the preview promised the folder {folder!r} but nothing was placed there; "
            f"the run actually used {sorted(leaves)}"
        )


def test_one_event_on_a_date_keeps_its_plain_name(tmp_path: Path) -> None:
    """Cry-wolf half. A fix that suffixes unconditionally would still pass the two above."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        sha = _seed_file(catalog, root, "in/only.jpg", f"{_DAY}T19:00:00", b"only")
        event_id = catalog.record_event(
            name=_NAME, slug="gokuls-marriage", start_date=_DAY, file_count=1, signature="solo"
        )
        catalog.set_event_id([sha], event_id)
        directory = _planned_directories(catalog, [sha])[0]

    assert PurePosixPath(directory).name == f"{_DAY} - {_NAME}"


def test_the_same_name_on_different_dates_is_never_suffixed(tmp_path: Path) -> None:
    """The date prefix already separates them; suffixing would be noise (filename safety §)."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        shas = []
        for index, day in enumerate(("2015-10-25", "2016-02-11")):
            sha = _seed_file(
                catalog, root, f"in/{index}.jpg", f"{day}T19:00:00", f"b{index}".encode()
            )
            event_id = catalog.record_event(
                name=_NAME,
                slug=f"gokuls-marriage-{index}",
                start_date=day,
                file_count=1,
                signature=f"different-date-{index}",
            )
            catalog.set_event_id([sha], event_id)
            shas.append(sha)
        directories = _planned_directories(catalog, shas)

    assert all("(2)" not in directory for directory in directories), directories
    assert len(set(directories)) == 2


def test_a_template_that_places_the_event_itself_is_disambiguated_too(tmp_path: Path) -> None:
    """The `{event}` token is a SECOND place a render spells an event folder.

    Without the token the event level is appended by the render seam; with it, the substitution
    inside `_render_segment` does the spelling and the append is skipped
    (`LayoutTemplate.has_event_token`). A fix applied only to the append leaves every library on
    an `{event}` template holding the defect, which is why this is asserted separately rather
    than assumed to follow.
    """
    template = LayoutTemplate.parse("{yyyy}/{event}")
    scheme = LayoutScheme.of(timeline=template, timeline_evented=template, side_bin=template)
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _three_same_day_events(catalog, root)
        plan = plan_migration(catalog, "D1", scheme)
        where = {move.sha256: move.new_relative for move in plan.moves}
        directories = [str(PurePosixPath(where[sha]).parent) for sha in shas]

    assert len(set(directories)) == 3, (
        f"the {{event}} token spelled one folder for three events: {directories}"
    )
