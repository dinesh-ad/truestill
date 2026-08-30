"""Renaming a trip or an event: the plan, and every refusal. `(aix)` stage 1.

**This stage writes nothing**, which is the point of it. `trips.slug` renders the directory
through `layout.event_dirname`, so a name change **moves photographs** - and the cheapest moment
to discover a wrong assumption about that is before any code can move one.

🔑 **The `Move` list is asserted against a fixture catalog, never against intent.** A wrong
assumption about `event_dirname` shows up here as a concrete path mismatch - the expected
`Camera/2014/2014-08/2014-08-15 - Corsica/a.jpg` against whatever was actually rendered - rather
than as a green test over a plan nobody read. That is the whole reason this stage exists.

**The refusal set is the valuable half.** Every condition has a test proving it fires *and* that
its sentence comes from `RENAME_WORDING`, because a refusal nobody can read is a divergence with
extra steps - digiKam answers *"Failed to rename Album"* rather than letting the catalog drift.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file
from truestill_core.layout_settings import resolve_scheme
from truestill_core.migrate import (
    RENAME_WORDING,
    ROUTE_TIMELINE,
    RenameKind,
    RenamePlan,
    RenameRefusal,
    plan_rename,
)


def _seed(
    catalog: Catalog, root: Path, drive_uuid: str, files: list[tuple[str, str, str, bytes]]
) -> dict[str, str]:
    shas: dict[str, str] = {}
    for relative, category, captured, content in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        sha = sha256_file(path)
        shas[relative] = sha
        catalog.record_uploaded(
            source_path=f"/src/{PurePosixPath(relative).name}",
            original_name=PurePosixPath(relative).name,
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=len(content),
            captured_at=captured,
            category=category,
            relative=relative,
            drive_uuid=drive_uuid,
        )
    return shas


@pytest.fixture
def trip_drive(tmp_path: Path) -> tuple[Path, Path, int]:
    """A drive holding one confirmed two-day trip, already migrated under its own name."""
    root = tmp_path / "drive"
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                (
                    "Camera/2014/2014-08/2014-08-15 - Holiday/a.jpg",
                    "Camera",
                    "2014-08-15T10:00:00",
                    b"aaaa",
                ),
                (
                    "Camera/2014/2014-08/2014-08-16 - Holiday/b.jpg",
                    "Camera",
                    "2014-08-16T10:00:00",
                    b"bbbb",
                ),
            ],
        )
        trip_id = catalog.create_trip(
            name="Holiday",
            slug="holiday",
            start_date="2014-08-15",
            end_date="2014-08-16",
            days=["2014-08-15", "2014-08-16"],
        )
    return root, db, trip_id


def _plan(db: Path, kind: RenameKind, row_id: int, name: str) -> RenamePlan:
    with Catalog(db) as catalog:
        # ⚠ **`routes` is not optional decoration.** `plan_migration` treats an unmapped label
        # as a side bin, and a side bin renders no trip folder at all - so without this the plan
        # is empty and every assertion below passes for the wrong reason. Found by writing the
        # first version without it.
        return plan_rename(
            catalog,
            "D1",
            resolve_scheme(catalog),
            kind=kind,
            row_id=row_id,
            new_name=name,
            routes={"Camera": ROUTE_TIMELINE},
        )


def test_the_plan_names_the_real_destination_of_every_file(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """THE DETECTOR, and the assertion is the rendered path itself.

    ⚠ **If `event_dirname`'s shape were assumed wrongly this fails by SHOWING the difference** -
    the expected folder against the one the layout actually renders - which is exactly what a
    stage that writes nothing is for. A test asserting only `len(moves) == 2` would pass against
    a plan that moves both files somewhere absurd.
    """
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "Corsica")

    assert plan.refusal is None, plan.refusal_detail
    assert plan.new_slug == "corsica"
    moved = {(m.old_relative, m.new_relative) for m in plan.moves}
    # ⚠ **The rendered shape is a trip HEADER dated by the trip's START, then a day folder
    # beneath it** - `2014-08-15 - Corsica/2014-08-16/b.jpg`, not `2014-08-16 - Corsica/b.jpg`.
    # The first draft of this test asserted the second and was wrong, which is precisely the
    # assumption a stage that writes nothing exists to expose at zero cost.
    assert moved == {
        (
            "Camera/2014/2014-08/2014-08-15 - Holiday/a.jpg",
            "2014/2014-08/2014-08-15 - Corsica/2014-08-15/a.jpg",
        ),
        (
            "Camera/2014/2014-08/2014-08-16 - Holiday/b.jpg",
            "2014/2014-08/2014-08-15 - Corsica/2014-08-16/b.jpg",
        ),
    }, f"the plan renders somewhere unexpected:\n{moved}"


def test_the_plan_carries_the_size_from_the_catalog_row(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """`Move.size` says *"from the catalog row the plan was built from - never a `stat`"*.

    A rename plans while the drive may be busy or slow; re-`stat`ing every file to fill a field
    the row already holds would make a pure plan touch the disk.
    """
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "Corsica")

    assert [m.size for m in plan.moves] == [4, 4]
    assert all(m.copy_sha256 for m in plan.moves), "the plan must carry what verification needs"


def test_nothing_is_written_by_planning(trip_drive: tuple[Path, Path, int]) -> None:
    """The stage's own promise, asserted rather than described."""
    root, db, trip_id = trip_drive
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    _plan(db, RenameKind.TRIP, trip_id, "Corsica")

    with Catalog(db) as catalog:
        row = catalog.named_trip_days()
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == before
    assert set(row.values()) == {"Holiday"}, "the catalog name changed during a PLAN"


# --- the refusal set: every condition, each proving it fires and where its words come from ----


def test_an_unknown_row_refuses(trip_drive: tuple[Path, Path, int]) -> None:
    _root, db, _trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, 9999, "Corsica")

    assert plan.refusal is RenameRefusal.NO_SUCH_ROW
    assert plan.moves == ()
    assert plan.refusal_detail == RENAME_WORDING[RenameRefusal.NO_SUCH_ROW].format(kind="trip")


def test_an_empty_name_refuses(trip_drive: tuple[Path, Path, int]) -> None:
    """A rename to nothing would leave the trip unnamed, which is not what was asked."""
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "   ")

    assert plan.refusal is RenameRefusal.EMPTY_NAME
    assert "needs a name" in plan.refusal_detail


def test_the_same_name_refuses_rather_than_planning_nothing(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """`UNCHANGED` is its own answer, not an empty move list.

    An empty plan is ambiguous - it also means *"the new name renders the same folder"* - and the
    two need different words.
    """
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "Holiday")

    assert plan.refusal is RenameRefusal.UNCHANGED


def test_a_name_that_leaves_nothing_usable_refuses_instead_of_keeping_the_old_one(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """⚠ **`(abw)`'s DISCARDED ANSWER, ARRIVING IN A NEW PLACE.**

    `layout` falls back to the slug when a name sanitises to nothing - right for NAMING, where the
    alternative is no folder at all. **Wrong for renaming**: a user who typed `"///"` and silently
    got their old folder back was not refused and was not obeyed, which is precisely the defect
    `(abw)` cost us on the already-named trip.
    """
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "///")

    assert plan.refusal is RenameRefusal.NOT_PATH_SAFE
    assert "leaves nothing" in plan.refusal_detail


def test_a_non_latin_name_is_accepted_rather_than_called_unusable(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """⚠ **CRY-WOLF, and the reason the check is `isalnum` rather than `slugify(name) == ""`.**

    Measured: `events.slugify("日本")` is `""`, because the slug alphabet is ASCII. Refusing on an
    empty slug would reject a perfectly good name whose NAME-layout folder renders fine - so the
    test is Unicode-aware, exactly as `layout`'s own is.
    """
    _root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "日本")

    assert plan.refusal is None, f"a legitimate non-Latin name was refused: {plan.refusal_detail}"
    assert plan.moves, "the rename renders no move at all"


def test_every_refusal_has_wording_and_no_wording_is_orphaned() -> None:
    """One home, both directions - `STOP_WORDING`'s rule.

    A member with no sentence would surface as a `KeyError` at the moment a user is being
    refused; a sentence with no member is dead prose nobody can reach.
    """
    assert set(RENAME_WORDING) == set(RenameRefusal), (
        f"RenameRefusal and RENAME_WORDING disagree: {set(RenameRefusal) ^ set(RENAME_WORDING)}"
    )


def test_a_trip_whose_drive_is_absent_says_so_rather_than_denying_it_exists(
    trip_drive: tuple[Path, Path, int],
) -> None:
    """⚠ **The two refusals a drive-scoped query cannot tell apart.**

    A trip that exists but has no photographs on THIS drive is not an unknown trip - the remedy is
    connecting the right drive, and answering *"there is no trip with that id"* would send the
    user looking for a mistake they did not make.
    """
    _root, db, _trip_id = trip_drive
    with Catalog(db) as catalog:
        elsewhere = catalog.create_trip(
            name="Kerala",
            slug="kerala",
            start_date="2020-01-01",
            end_date="2020-01-02",
            days=["2020-01-01", "2020-01-02"],
        )

    plan = _plan(db, RenameKind.TRIP, elsewhere, "Wayanad")

    assert plan.refusal is RenameRefusal.NOTHING_ON_THIS_DRIVE
    assert plan.old_name == "Kerala", "the refusal should still know what it is refusing about"


def test_the_move_starts_where_the_file_actually_is(trip_drive: tuple[Path, Path, int]) -> None:
    """⚠ **`old_relative` comes from the catalog row, never from the re-render.**

    `_plan_relatives` answers *"where would this go"*. For a library not yet migrated under the
    current template that is a DIFFERENT path from where the file sits - so a move planned from
    the rendered path would name a source that does not exist. The fixture's paths are
    deliberately not the layout's own, which is what makes this assertion mean something.
    """
    root, db, trip_id = trip_drive

    plan = _plan(db, RenameKind.TRIP, trip_id, "Corsica")

    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    for move in plan.moves:
        assert move.old_relative in on_disk, (
            f"the plan would move {move.old_relative!r}, which is not on the drive - "
            f"old_relative was taken from the re-render instead of the row"
        )
