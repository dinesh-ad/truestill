"""Layout migration: planning, copy-only relocation, and crash-safe resume.

The resume tests reconstruct the exact on-disk + catalog state a crash would leave at each step
of the copy -> verify -> flip-catalog -> remove-old sequence, then assert a re-run converges.
"""

from __future__ import annotations

import threading
from pathlib import Path, PurePosixPath

import pytest
from truestill_core import migrate
from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.drive import MARKER_NAME
from truestill_core.exif import ExiftoolMissingError
from truestill_core.hashing import sha256_file
from truestill_core.layout import (
    DEFAULT_EVERYDAY_DAY_THRESHOLD,
    DEFAULT_SCHEME,
    EventNaming,
    LayoutScheme,
    LayoutTemplate,
)
from truestill_core.migrate import (
    ROUTE_TIMELINE,
    Move,
    label_routes,
    plan_migration,
    rederive_rules,
    run_migration,
    undo_migration,
)
from truestill_core.progress import Progress


def _scheme(template: str) -> LayoutScheme:
    """A migration scheme from one template -- the legacy shape these tests exercise."""
    parsed = LayoutTemplate.parse(template)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


_NO_EXIFTOOL = "exiftool is not installed"
_DDL = "{category}/{yyyy}"  # drops the month the default adds -> every dated file must move


def _seed(
    catalog: Catalog, root: Path, drive_uuid: str, rows: list[tuple[str, str, str, bytes]]
) -> dict[str, str]:
    """Write real files and record them; return {relative: sha256}."""
    shas: dict[str, str] = {}
    for relative, category, captured, content in rows:
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


def _two_files(catalog: Catalog, root: Path) -> dict[str, str]:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    return _seed(
        catalog,
        root,
        "D1",
        [
            ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa"),
            ("WhatsApp/2024/01/b.jpg", "WhatsApp", "2024-01-15T00:00:00", b"bbbb"),
        ],
    )


def test_preview_moves_nothing(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(_DDL), apply=False)
    assert outcome.applied is False
    assert outcome.migrated == 0
    assert len(outcome.plan.moves) == 2
    assert (root / "Camera/2023/08/a.jpg").exists()  # untouched


def test_apply_relocates_and_updates_catalog(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        shas = _two_files(catalog, root)
        outcome = run_migration(catalog, LocalDestination(root), "D1", _scheme(_DDL), apply=True)
        assert outcome.migrated == 2
        assert (root / "Camera/2023/a.jpg").exists()
        assert not (root / "Camera/2023/08/a.jpg").exists()  # old removed
        assert catalog.copy_relative(shas["Camera/2023/08/a.jpg"], "D1") == "Camera/2023/a.jpg"
        assert catalog.pending_migration("D1") == []  # journal drained


def test_apply_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    scheme = _scheme(_DDL)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        run_migration(catalog, LocalDestination(root), "D1", scheme, apply=True)
        again = run_migration(catalog, LocalDestination(root), "D1", scheme, apply=True)
    assert again.migrated == 0
    assert again.plan.unchanged == 2


def test_only_the_given_drive_is_touched(tmp_path: Path) -> None:
    root1, root2 = tmp_path / "d1", tmp_path / "d2"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root1)
        catalog.upsert_drive(uuid="D2", label="Drive B")
        other = _seed(
            catalog,
            root2,
            "D2",
            [("Camera/2023/08/z.jpg", "Camera", "2023-08-20T14:30:00", b"zzzz")],
        )
        run_migration(catalog, LocalDestination(root1), "D1", _scheme(_DDL), apply=True)
        # D2's copy is left exactly where it was -- migration is one connected drive at a time.
        assert catalog.copy_relative(other["Camera/2023/08/z.jpg"], "D2") == "Camera/2023/08/z.jpg"
        assert (root2 / "Camera/2023/08/z.jpg").exists()


# -- crash recovery: reconstruct each intermediate state, then resume -----------------------


def _one_move(catalog: Catalog, root: Path) -> Move:
    sha = _seed(
        catalog, root, "D1", [("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa")]
    )["Camera/2023/08/a.jpg"]
    catalog.upsert_drive(uuid="D1", label="Drive A")
    return Move(sha, "Camera/2023/08/a.jpg", "Camera/2023/a.jpg", sha)


def test_resume_after_crash_before_catalog_flip(tmp_path: Path) -> None:
    # Crash state: new copy written + journalled, but the catalog still points at the old path.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        dest.relocate(move.old_relative, move.new_relative)  # new exists; old still exists

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert (root / "Camera/2023/a.jpg").exists()
        assert not (root / "Camera/2023/08/a.jpg").exists()
        assert catalog.copy_relative(move.sha256, "D1") == "Camera/2023/a.jpg"
        assert catalog.pending_migration("D1") == []


def test_resume_after_crash_after_flip_removes_orphan(tmp_path: Path) -> None:
    # Crash state: catalog already flipped to new, but the old copy was never removed (orphan).
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        dest.relocate(move.old_relative, move.new_relative)
        catalog.relocate_copy(
            move.sha256, "D1", move.new_relative
        )  # catalog flipped; old orphan remains

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert not (root / "Camera/2023/08/a.jpg").exists()  # orphan cleaned
        assert (root / "Camera/2023/a.jpg").exists()
        assert catalog.pending_migration("D1") == []


def test_resume_repairs_partial_copy(tmp_path: Path) -> None:
    # Crash state: the new copy was only half-written (wrong bytes); catalog still points at old.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        move = _one_move(catalog, root)
        dest = LocalDestination(root)
        catalog.record_migration_moves(
            [(move.sha256, "D1", move.old_relative, move.new_relative, move.copy_sha256, "run-1")]
        )
        corrupt = root / move.new_relative
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_bytes(b"XX")  # partial/corrupt -> must not be trusted

        run_migration(catalog, dest, "D1", _scheme(_DDL), apply=True)

        assert sha256_file(root / "Camera/2023/a.jpg") == move.copy_sha256  # re-copied and verified
        assert not (root / "Camera/2023/08/a.jpg").exists()
        assert catalog.pending_migration("D1") == []


def test_plan_flags_collision(tmp_path: Path) -> None:
    # Two files whose new paths differ only in case collide on a case-insensitive filesystem.
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                ("camera/2023/08/a.jpg", "camera", "2023-08-20T00:00:00", b"aaaa"),
                ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T00:00:00", b"bbbb"),
            ],
        )
        plan = plan_migration(catalog, "D1", _scheme("{category}/{yyyy}/{mm}/{dd}"))
    assert any("same path" in w for w in plan.warnings)


# --- (mm): an event's naming must come from its OWN placement, never a fixed EVERYDAY guess ---


def _named_event(
    catalog: Catalog, *, sha: str, name: str, slug: str, start_date: str, signature: str
) -> None:
    event_id = catalog.record_event(
        name=name, slug=slug, start_date=start_date, file_count=1, signature=signature
    )
    catalog.set_event_id([sha], event_id)


def _two_same_day_events_one_shared_name(catalog: Catalog, root: Path) -> None:
    """Two distinct events, same date and human name, different slugs.

    Colliding under READABLE naming (same date + same sanitized name) but never under SLUG
    naming (different slugs) -- the two placement namings genuinely disagree about whether
    these folders collide, which no shipped preset can show today (backlog (mm)).
    """
    catalog.upsert_drive(uuid="D1", label="Drive A")
    shas = _seed(
        catalog,
        root,
        "D1",
        [
            ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T09:00:00", b"aaaa"),
            ("Camera/2023/08/b.jpg", "Camera", "2023-08-20T18:00:00", b"bbbb"),
        ],
    )
    _named_event(
        catalog,
        sha=shas["Camera/2023/08/a.jpg"],
        name="Goa Trip",
        slug="goa-trip-morning",
        start_date="2023-08-20T00:00:00",
        signature="sig-a",
    )
    _named_event(
        catalog,
        sha=shas["Camera/2023/08/b.jpg"],
        name="Goa Trip",
        slug="goa-trip-evening",
        start_date="2023-08-20T00:00:00",
        signature="sig-b",
    )


def test_a_scheme_where_placements_genuinely_differ_disambiguates_by_each_events_own_naming(
    tmp_path: Path,
) -> None:
    """Fails against the pre-fix code, which reads EVERYDAY's naming for every event.

    EVERYDAY is READABLE here and EVENT_DAY is SLUG -- the two same-date, same-name events
    render identical READABLE folders (a collision) but distinct SLUG ones (no collision). The
    real per-file paths always route through EVENT_DAY (classify() returns it for any evented,
    timeline-routed file), so asking EVERYDAY's naming reports a collision that would never
    occur on disk. The fix (asking each event's own placement) reports none.
    """
    root = tmp_path / "drive"
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}"),  # EVERYDAY: default READABLE
        timeline_evented=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.SLUG),
    )
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_same_day_events_one_shared_name(catalog, root)
        plan = plan_migration(catalog, "D1", scheme, routes={"Camera": ROUTE_TIMELINE})
    assert not any("already uses" in w for w in plan.warnings)


def test_a_real_collision_is_still_caught_on_a_shared_naming_scheme(tmp_path: Path) -> None:
    """The other side of the same fixture, on the shape every shipped preset actually has.

    Every current scheme gives EVERYDAY and EVENT_DAY the same (READABLE) naming, so the two
    same-day, same-name events above genuinely do collide under either template -- the fix must
    not suppress that. Byte-identical to the pre-fix behaviour, since one shared naming is
    exactly the case backlog (mm) says was harmless.
    """
    root = tmp_path / "drive"
    scheme = _scheme("{yyyy}/{yyyy}-{mm}")  # timeline == timeline_evented == side_bin
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_same_day_events_one_shared_name(catalog, root)
        plan = plan_migration(catalog, "D1", scheme, routes={"Camera": ROUTE_TIMELINE})
    assert any("already uses" in w for w in plan.warnings)


def _fingerprint(root: Path) -> list[tuple[str, str]]:
    """Every file with its content hash -- catches a move, a rewrite or a deletion."""
    return sorted(
        (p.relative_to(root).as_posix(), sha256_file(p))
        for p in root.rglob("*")
        if p.is_file() and p.name != MARKER_NAME
    )


def test_forward_then_undo_returns_the_tree_and_the_catalog(tmp_path: Path) -> None:
    """The reverse gear, proved the same way preview purity was: byte-identical, both sides.

    A migration that cannot be undone is a one-way door on someone's only organized copy. This
    asserts the door swings: disk back to the same paths with the same content, and the catalog
    agreeing with disk again so `verify` still passes.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_tree = _fingerprint(root)
        before_paths = {r["relative"] for r in catalog.copies_for_migration("D1")}
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        assert _fingerprint(root) != before_tree  # it really did move

        outcome = undo_migration(catalog, dest, "D1", apply=True)

        assert outcome.reversed_files == 2
        assert outcome.clean
        assert {r["relative"] for r in catalog.copies_for_migration("D1")} == before_paths
        assert _fingerprint(root) == before_tree


def test_undo_is_resumable_when_interrupted_partway(tmp_path: Path) -> None:
    """Undo drops a journal row only after its file is verified back, so it can be re-run."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_tree = _fingerprint(root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)

        # A realistic interruption: the restore was written to disk but the process died
        # before the catalog flip, the removal and the journal drop.
        record = catalog.reversible_migration("D1")
        assert record is not None
        first = record[1][0]
        dest.relocate(str(first["new_relative"]), str(first["old_relative"]))

        # Re-running finishes every move, including the half-done one, without double-counting
        # or tripping over the copy already sitting at its old path.
        outcome = undo_migration(catalog, dest, "D1", apply=True)

        assert outcome.reversed_files == 2
        assert outcome.clean
        assert _fingerprint(root) == before_tree
        assert catalog.reversible_migration("D1") is None  # the record is spent


def test_undo_refuses_a_file_that_changed_since_the_migration(tmp_path: Path) -> None:
    """Someone edited the photo after it moved. Undo reports it and leaves it alone.

    Putting the old path back would discard whatever that edit was, which is exactly the kind of
    silent loss the copy-only invariant exists to prevent.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)

        record = catalog.reversible_migration("D1")
        assert record is not None
        moved = root / str(record[1][0]["new_relative"])
        moved.write_bytes(b"edited since the migration")

        outcome = undo_migration(catalog, dest, "D1", apply=True)

        # The untouched file goes back; the edited one is reported and left exactly as it is.
        assert outcome.reversed_files == 1
        assert not outcome.clean
        assert "changed since the migration" in outcome.refused[0][1]
        assert moved.read_bytes() == b"edited since the migration"
        assert catalog.reversible_migration("D1") is not None  # its record survives for a retry


def test_undo_preview_emits_progress_for_every_row(tmp_path: Path) -> None:
    """Preview pays the exists+checksum walk; silence on that walk is the (oo)-class freeze."""
    root = tmp_path / "drive"
    ticks: list[tuple[int, int, str, str]] = []
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        before_tree = _fingerprint(root)
        before_bytes = (tmp_path / "c.sqlite").read_bytes()

        outcome = undo_migration(
            catalog,
            dest,
            "D1",
            apply=False,
            progress=lambda p: ticks.append((p.done, p.total, p.phase, p.item)),
        )

        assert outcome.reversed_files == 2
        assert outcome.clean
        assert len(ticks) == 2
        assert [t[0] for t in ticks] == [1, 2]
        assert {t[1] for t in ticks} == {2}
        assert {t[2] for t in ticks} == {"restoring"}
        assert _fingerprint(root) == before_tree
        assert (tmp_path / "c.sqlite").read_bytes() == before_bytes


def test_undo_preview_progress_ticks_refused_rows_too(tmp_path: Path) -> None:
    """A refused row is still work the walk did - the bar must move for it, never freeze."""
    root = tmp_path / "drive"
    ticks: list[int] = []
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        record = catalog.reversible_migration("D1")
        assert record is not None
        (root / str(record[1][0]["new_relative"])).write_bytes(b"edited")

        outcome = undo_migration(
            catalog,
            dest,
            "D1",
            apply=False,
            progress=lambda p: ticks.append(p.done),
        )

    assert outcome.reversed_files == 1
    assert len(outcome.refused) == 1
    assert ticks == [1, 2]


def test_undo_cancel_stops_the_walk_and_leaves_the_journal_resumable(tmp_path: Path) -> None:
    """Cancel mid-apply forgets only verified rows; the rest stay for a resume."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_tree = _fingerprint(root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        before_record = catalog.reversible_migration("D1")
        assert before_record is not None
        assert len(before_record[1]) == 2

        cancel = threading.Event()
        seen = 0

        def _progress(_p: Progress) -> None:
            nonlocal seen
            seen += 1
            if seen >= 1:
                cancel.set()

        partial = undo_migration(catalog, dest, "D1", apply=True, progress=_progress, cancel=cancel)

        assert partial.reversed_files == 1
        mid = catalog.reversible_migration("D1")
        assert mid is not None
        assert len(mid[1]) == 1  # one row remains; the forgotten one is gone

        resumed = undo_migration(catalog, dest, "D1", apply=True)
        assert resumed.reversed_files == 1
        assert resumed.clean
        assert catalog.reversible_migration("D1") is None
        assert _fingerprint(root) == before_tree


def test_undo_preview_cancel_writes_nothing(tmp_path: Path) -> None:
    """A cancelled preview is still a preview: no relocate, no journal forget."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        before_bytes = (tmp_path / "c.sqlite").read_bytes()
        before_tree = _fingerprint(root)
        cancel = threading.Event()
        cancel.set()

        outcome = undo_migration(catalog, dest, "D1", apply=False, cancel=cancel)

        assert outcome.reversed_files == 0
        assert outcome.refused == []
        assert (tmp_path / "c.sqlite").read_bytes() == before_bytes
        assert _fingerprint(root) == before_tree
        assert catalog.reversible_migration("D1") is not None


def test_a_new_migration_supersedes_the_previous_reversal_record(tmp_path: Path) -> None:
    """Retention is bounded by supersession, not by a timer -- one run's record per drive."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        dest = LocalDestination(root)
        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), apply=True)
        first = catalog.reversible_migration("D1")
        assert first is not None

        run_migration(catalog, dest, "D1", _scheme("{yyyy}/{yyyy}-{mm}/{dd}"), apply=True)
        second = catalog.reversible_migration("D1")

        assert second is not None
        assert second[0] != first[0]  # a new run
        assert len(second[1]) == 2  # and only its own moves are retained


def test_rederivation_degrades_instead_of_failing_when_exiftool_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No binary means no evidence -- which is a per-label decision, not a crashed migration.

    Found by a CI run where Chocolatey's feed timed out and exiftool was silently absent: the
    re-derivation raised instead of degrading, on a path a user reaches with `migrate-layout`.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)

        def missing(_paths, **_kwargs):
            raise ExiftoolMissingError(_NO_EXIFTOOL)

        monkeypatch.setattr(migrate, "read_metadata", missing)
        routes = label_routes(catalog, "D1")
        assert any(r.needs_decision for r in routes)  # there is something to re-derive

        assert rederive_rules(catalog, "D1", root, routes) == {}  # degraded, not raised


def test_migrating_one_drive_leaves_another_drives_undo_record_intact(tmp_path: Path) -> None:
    """Supersession is per drive, so a second library's migration cannot disarm the first's.

    Two drives hold the same content by design (3-2-1), and they are migrated one at a time --
    so if starting a run cleared the journal globally, migrating the second drive would silently
    take away the ability to reverse the first.
    """
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(
            catalog,
            root_a,
            "D1",
            [("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa")],
        )
        _seed(
            catalog,
            root_b,
            "D2",
            [("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa")],
        )

        run_migration(catalog, LocalDestination(root_a), "D1", _scheme(_DDL), apply=True)
        first = catalog.reversible_migration("D1")
        assert first is not None

        run_migration(catalog, LocalDestination(root_b), "D2", _scheme(_DDL), apply=True)

        still_there = catalog.reversible_migration("D1")
        assert still_there is not None
        assert still_there[0] == first[0]  # the same run, untouched
        assert catalog.reversible_migration("D2") is not None  # and D2 has its own


# --- Stage 2d, 13.4: migration wiring -- a confirmed trip actually relocates its files ---


def _confirmed_trip(
    catalog: Catalog, *, name: str, slug: str, start_date: str, end_date: str, days: list[str]
) -> int:
    return catalog.create_trip(
        name=name, slug=slug, start_date=start_date, end_date=end_date, days=days
    )


def test_the_worked_example_plans_the_trip_header_then_day(tmp_path: Path) -> None:
    """The §10 worked example, built: naming Aug 15-16 on an already-organized drive plans the
    trip's own header folder, then each claimed day beneath it - through the same preview path
    an event's migration already used (Stage 2d, 13.4)."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                ("Camera/2014/08/a.jpg", "Camera", "2014-08-15T10:00:00", b"aaaa"),
                ("Camera/2014/08/b.jpg", "Camera", "2014-08-16T10:00:00", b"bbbb"),
            ],
        )
        _confirmed_trip(
            catalog,
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-15",
            end_date="2014-08-16",
            days=["2014-08-15", "2014-08-16"],
        )
        plan = plan_migration(
            catalog, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), routes={"Camera": ROUTE_TIMELINE}
        )
    by_old = {m.old_relative: m.new_relative for m in plan.moves}
    assert by_old["Camera/2014/08/a.jpg"] == "2014/2014-08/2014-08-15 - Wayanad/2014-08-15/a.jpg"
    assert by_old["Camera/2014/08/b.jpg"] == "2014/2014-08/2014-08-15 - Wayanad/2014-08-16/b.jpg"


def test_a_camera_photo_in_a_trip_is_routed_by_its_own_evidence_not_side_binned(
    tmp_path: Path,
) -> None:
    """A trip inherits the §13.7 fix, rather than re-solving it: a `Camera`-labelled row is
    ambiguous by construction, so it still needs `routes`/`rules_by_sha` to reach the timeline.
    Without a route decision, `plan_migration`'s conservative default (unmapped -> side bin)
    fires exactly as it would outside any trip; passing the decision `label_routes` +
    `rederive_rules` would actually resolve to routes it into the trip folder instead.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [("Camera/2014/08/a.jpg", "Camera", "2014-08-15T10:00:00", b"aaaa")],
        )
        _confirmed_trip(
            catalog,
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-15",
            end_date="2014-08-15",
            days=["2014-08-15"],
        )
        scheme = _scheme("{yyyy}/{yyyy}-{mm}")
        side_binned = plan_migration(catalog, "D1", scheme)  # no routes: conservative default
        timelined = plan_migration(catalog, "D1", scheme, routes={"Camera": ROUTE_TIMELINE})

    side_new = {m.old_relative: m.new_relative for m in side_binned.moves}["Camera/2014/08/a.jpg"]
    timeline_new = {m.old_relative: m.new_relative for m in timelined.moves}["Camera/2014/08/a.jpg"]
    assert "Wayanad" not in side_new  # conservative default: side bin, not the trip folder
    assert "Wayanad" in timeline_new  # routed by its own evidence: lands in the trip folder


def test_a_non_camera_file_on_a_trip_day_stays_in_its_side_bin(tmp_path: Path) -> None:
    """A trip claims every *Camera* photo taken that day (§2) - never a WhatsApp or Screenshot
    file that happens to share the date. `trip_days` is joined day-keyed (any category), unlike
    `events` (only ever linked to a Camera cluster's own files by construction), so this is not
    safe by construction the way the event branch is - it is guarded explicitly.

    Fails against the defect first: with the row-level ``rule == TIMELINE_RULE`` guard on `trip`
    removed, a WhatsApp file captured on the trip's day is pulled into the trip's day folder,
    because `LayoutTemplate._render` appends trip segments whenever `context.trip` is set,
    regardless of which placement's template is actually rendering. Confirmed failing with the
    guard commented out (the WhatsApp file lands under ``.../Wayanad/2014-08-15/...``); restored.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                ("Camera/2014/08/a.jpg", "Camera", "2014-08-15T10:00:00", b"aaaa"),
                ("WhatsApp/2014/08/b.jpg", "WhatsApp", "2014-08-15T11:00:00", b"bbbb"),
            ],
        )
        _confirmed_trip(
            catalog,
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-15",
            end_date="2014-08-15",
            days=["2014-08-15"],
        )
        plan = plan_migration(
            catalog,
            "D1",
            _scheme("{category}/{yyyy}/{yyyy}-{mm}"),
            routes={"Camera": ROUTE_TIMELINE},
        )
    by_old = {m.old_relative: m.new_relative for m in plan.moves}
    assert "Wayanad" not in by_old.get("WhatsApp/2014/08/b.jpg", "")


# --- (mm) widened: an event and a trip's naming, not just two events' ---


def test_an_event_sharing_a_day_with_a_trip_is_fully_dissolved_not_cross_planned(
    tmp_path: Path,
) -> None:
    """Why a genuine event-vs-trip header collision cannot arise in practice, proved rather than
    assumed: `trip_days` claims the whole day (§2), so an event dated the SAME day as a trip is
    dissolved entirely - none of its files plan an EVENT_DAY path; they plan TRIP_DAY like every
    other file that day, and no collision warning is raised because the event never becomes a
    disambiguation candidate at all (`_migration_headers`'s exclusion)."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        shas = _seed(
            catalog,
            root,
            "D1",
            [("Camera/2023/08/a.jpg", "Camera", "2023-08-20T09:00:00", b"aaaa")],
        )
        _named_event(
            catalog,
            sha=shas["Camera/2023/08/a.jpg"],
            name="Goa Trip",
            slug="goa-trip-event",
            start_date="2023-08-20T00:00:00",
            signature="sig-event",
        )
        _confirmed_trip(
            catalog,
            name="Goa Trip",
            slug="goa-trip-real",
            start_date="2023-08-20",
            end_date="2023-08-20",
            days=["2023-08-20"],
        )
        plan = plan_migration(
            catalog, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), routes={"Camera": ROUTE_TIMELINE}
        )
    by_old = {m.old_relative: m.new_relative for m in plan.moves}
    assert by_old["Camera/2023/08/a.jpg"] == "2023/2023-08/2023-08-20 - Goa Trip/2023-08-20/a.jpg"
    assert not any("already uses" in w for w in plan.warnings)  # nothing left to collide with


def test_two_events_still_collide_correctly_when_a_trip_is_also_present(tmp_path: Path) -> None:
    """Regression for folding trips into the same disambiguation pass (decision (a) below): two
    same-day, same-name events must still collide exactly as before (backlog (mm)'s original
    fixture), even when an unrelated confirmed trip on a different date is migrated in the same
    run. Fails if unifying `events`/trips into one `headers` dict ever let an unrelated trip
    entry crowd out or reorder the pre-existing per-naming grouping."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_same_day_events_one_shared_name(catalog, root)
        _seed(
            catalog,
            root,
            "D1",
            [("Camera/2023/09/c.jpg", "Camera", "2023-09-10T09:00:00", b"cccc")],
        )
        _confirmed_trip(
            catalog,
            name="Unrelated Trip",
            slug="unrelated-trip",
            start_date="2023-09-10",
            end_date="2023-09-10",
            days=["2023-09-10"],
        )
        plan = plan_migration(
            catalog, "D1", _scheme("{yyyy}/{yyyy}-{mm}"), routes={"Camera": ROUTE_TIMELINE}
        )
    assert any("already uses" in w for w in plan.warnings)  # the two events still collide


def test_a_trip_and_an_event_with_different_namings_are_alarmed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Decision (a) for backlog (mm)'s Stage 13.4 widening - grouping headers by their *resolved
    naming*, not by event-vs-trip - is what let the regression above pass: an event and a trip
    that happen to share a naming land in the same disambiguation group automatically. Proven
    here from the other side: `TRIP_DAY` deliberately configured with a naming that diverges from
    `EVENT_DAY`'s (13.2's escape hatch; no production caller sets it) puts them in different
    groups, and - since two different namings render structurally different text (`READABLE` vs
    `SLUG`) - a real collision between them was never reachable in the first place (see the
    dissolution proof above: same date always dissolves the event, and different dates always
    render different date prefixes regardless of naming). The divergence itself is still alarmed
    (the `dedup.LINEAR_SCAN_ALARM` pattern), so a future caller who *does* diverge the two
    namings is told, not left to discover it unassisted.
    """
    root = tmp_path / "drive"
    scheme = LayoutScheme.of(
        timeline=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}"),
        timeline_evented=LayoutTemplate.parse(
            "{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.READABLE
        ),
        trip_day=LayoutTemplate.parse("{yyyy}/{yyyy}-{mm}", event_naming=EventNaming.SLUG),
    )
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        shas = _seed(
            catalog,
            root,
            "D1",
            [
                ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T09:00:00", b"aaaa"),
                ("Camera/2023/09/b.jpg", "Camera", "2023-09-10T09:00:00", b"bbbb"),
            ],
        )
        _named_event(
            catalog,
            sha=shas["Camera/2023/08/a.jpg"],
            name="Goa Trip",
            slug="goa-trip-event",
            start_date="2023-08-20T00:00:00",
            signature="sig-event",
        )
        _confirmed_trip(
            catalog,
            name="Goa Trip",
            slug="goa-trip-real",
            start_date="2023-09-10",
            end_date="2023-09-10",
            days=["2023-09-10"],
        )
        with caplog.at_level("WARNING", logger="truestill_core.migrate"):
            plan = plan_migration(catalog, "D1", scheme, routes={"Camera": ROUTE_TIMELINE})
    assert not any("already uses" in w for w in plan.warnings)  # different dates: never collide
    assert any("not cross-checked" in r.message for r in caplog.records)  # but told, not silent


def test_trip_preview_moves_nothing_and_apply_relocates_as_planned(tmp_path: Path) -> None:
    """The file-moving safety rule this stage exists to prove both directions of: preview alone
    is side-effect-free, and apply moves exactly what preview showed - the same preview-then-
    confirm gate every other migration in this app already requires, not a looser one for trips.
    """
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [("Camera/2014/08/a.jpg", "Camera", "2014-08-15T10:00:00", b"aaaa")],
        )
        _confirmed_trip(
            catalog,
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-15",
            end_date="2014-08-15",
            days=["2014-08-15"],
        )
        scheme = _scheme("{yyyy}/{yyyy}-{mm}")
        preview = run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            scheme,
            apply=False,
            routes={"Camera": ROUTE_TIMELINE},
        )
        assert preview.migrated == 0
        assert (root / "Camera/2014/08/a.jpg").exists()  # untouched by preview alone

        outcome = run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            scheme,
            apply=True,
            routes={"Camera": ROUTE_TIMELINE},
        )
    assert outcome.migrated == 1
    assert (root / "2014/2014-08/2014-08-15 - Wayanad/2014-08-15/a.jpg").exists()
    assert not (root / "Camera/2014/08/a.jpg").exists()


# --- backlog (oo): progress on migration preview phases ---------------------------------


def test_migration_preview_emits_planning_ticks_with_row_total(tmp_path: Path) -> None:
    """Preview used to return after plan_migration with zero ticks - the (oo) silent freeze."""
    root = tmp_path / "drive"
    ticks: list[tuple[int, int, str]] = []
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before = (tmp_path / "c.sqlite").read_bytes()
        outcome = run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            _scheme(_DDL),
            apply=False,
            progress=lambda p: ticks.append((p.done, p.total, p.phase)),
        )
    assert outcome.applied is False
    assert outcome.migrated == 0
    assert len(ticks) == 2
    assert [t[0] for t in ticks] == [1, 2]
    assert {t[1] for t in ticks} == {2}
    assert {t[2] for t in ticks} == {"planning"}
    assert (tmp_path / "c.sqlite").read_bytes() == before


def test_plan_migration_cancel_stops_mid_loop_and_writes_nothing(tmp_path: Path) -> None:
    """A cancelled plan is pure: partial result, no catalog or disk change."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        before_db = (tmp_path / "c.sqlite").read_bytes()
        before_tree = _fingerprint(root)
        cancel = threading.Event()
        seen = 0

        def _progress(_p: Progress) -> None:
            nonlocal seen
            seen += 1
            if seen >= 1:
                cancel.set()

        plan = plan_migration(catalog, "D1", _scheme(_DDL), progress=_progress, cancel=cancel)
        assert seen == 1
        assert len(plan.moves) + plan.unchanged < 2 or len(plan.moves) <= 1
        assert (tmp_path / "c.sqlite").read_bytes() == before_db
        assert _fingerprint(root) == before_tree


def test_rederive_forwards_progress_with_scanning_phase_and_correct_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rederive_rules used to call read_metadata without progress - the dominant (oo) cost."""
    root = tmp_path / "drive"
    forwarded: list[tuple[object, object]] = []
    ticks: list[tuple[int, int, str]] = []

    def fake_read(paths, *, cache=None, progress=None, cancel=None):  # noqa: ARG001
        forwarded.append((progress, cancel))
        result = {}
        for i, path in enumerate(paths, start=1):
            if progress is not None:
                progress(Progress(i, len(paths), "scanning", path.name))
            result[path] = {"Make": "Canon", "Model": "EOS"}
        return result

    monkeypatch.setattr(migrate, "read_metadata", fake_read)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        routes = label_routes(catalog, "D1")
        assert any(r.needs_decision for r in routes)
        before = (tmp_path / "c.sqlite").read_bytes()
        rules = rederive_rules(
            catalog,
            "D1",
            root,
            routes,
            progress=lambda p: ticks.append((p.done, p.total, p.phase)),
        )
    assert forwarded
    assert forwarded[0][0] is not None
    # Only Camera is ambiguous; WhatsApp is a deterministic side bin and is never re-read.
    assert len(ticks) == 1
    assert ticks[0] == (1, 1, "scanning")
    assert rules  # categorize produced a rule for the readable Camera file
    assert (tmp_path / "c.sqlite").read_bytes() == before


def test_rederive_cancel_stops_read_and_leaves_no_partial_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel mid-rederive must not write the catalog; unread files get no invented rule."""
    root = tmp_path / "drive"
    cancel = threading.Event()
    seen = 0

    def fake_read(paths, *, cache=None, progress=None, cancel=None):  # noqa: ARG001
        nonlocal seen
        result = {}
        for i, path in enumerate(paths, start=1):
            if cancel is not None and cancel.is_set():
                break
            if progress is not None:
                progress(Progress(i, len(paths), "scanning", path.name))
            result[path] = {"Make": "Canon", "Model": "EOS"}
            seen += 1
            if seen >= 1 and cancel is not None:
                cancel.set()
        return result

    monkeypatch.setattr(migrate, "read_metadata", fake_read)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(
            catalog,
            root,
            "D1",
            [
                ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa"),
                ("Camera/2023/08/b.jpg", "Camera", "2023-08-21T14:30:00", b"bbbb"),
            ],
        )
        routes = label_routes(catalog, "D1")
        before = (tmp_path / "c.sqlite").read_bytes()
        before_tree = _fingerprint(root)
        rules = rederive_rules(catalog, "D1", root, routes, cancel=cancel)
        assert len(rules) == 1
        assert (tmp_path / "c.sqlite").read_bytes() == before
        assert _fingerprint(root) == before_tree


def test_preview_run_emits_both_scanning_and_planning_phases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two preview costs are distinct phases so the UI can name each honestly."""
    root = tmp_path / "drive"
    phases: list[str] = []

    def fake_read(paths, *, cache=None, progress=None, cancel=None):  # noqa: ARG001
        result = {}
        for i, path in enumerate(paths, start=1):
            if progress is not None:
                progress(Progress(i, len(paths), "scanning", path.name))
            result[path] = {"Make": "Canon", "Model": "EOS"}
        return result

    monkeypatch.setattr(migrate, "read_metadata", fake_read)
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _two_files(catalog, root)
        routes = label_routes(catalog, "D1")
        rules = rederive_rules(
            catalog,
            "D1",
            root,
            routes,
            progress=lambda p: phases.append(p.phase),
        )
        run_migration(
            catalog,
            LocalDestination(root),
            "D1",
            _scheme(_DDL),
            apply=False,
            routes={r.label: ROUTE_TIMELINE for r in routes},
            rules_by_sha=rules,
            progress=lambda p: phases.append(p.phase),
        )
    assert "scanning" in phases
    assert "planning" in phases
    assert phases.index("scanning") < phases.index("planning")


# --- backlog (gg): Everyday day-folder threshold reconcile ---------------------------------


def test_migrate_month_to_day_states_count_and_threshold_per_day(tmp_path: Path) -> None:
    """Over-threshold unevented day in the monthly bucket moves once, with a named reason."""
    root = tmp_path / "drive"
    day = "2014-08-17"
    n = DEFAULT_EVERYDAY_DAY_THRESHOLD + 1
    rows = [
        (
            f"2014/2014-08/2014-08 - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T10:{i % 60:02d}:00",
            f"payload-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == n
    assert all("2014-08-17 - Everyday" in m.new_relative for m in plan.moves)
    assert all("2014-08 - Everyday" in m.old_relative for m in plan.moves)
    assert plan.day_folder_reasons == (
        (
            f"{day} now has {n} photos, over your threshold of {DEFAULT_EVERYDAY_DAY_THRESHOLD} "
            "- moving to its own day folder"
        ),
    )


def test_migrate_day_to_month_states_count_and_threshold_per_day(tmp_path: Path) -> None:
    """Under-threshold day folder coalesces back to monthly Everyday, with the reverse reason."""
    root = tmp_path / "drive"
    day = "2014-08-18"
    n = 5
    rows = [
        (
            f"2014/2014-08/{day} - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T11:{i % 60:02d}:00",
            f"under-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == n
    assert all("2014-08 - Everyday" in m.new_relative for m in plan.moves)
    assert plan.day_folder_reasons == (
        (
            f"{day} now has {n} photos, at or under your threshold of "
            f"{DEFAULT_EVERYDAY_DAY_THRESHOLD} - moving back into the monthly Everyday folder"
        ),
    )


def test_migrate_unchanged_day_produces_no_moves_and_no_reason(tmp_path: Path) -> None:
    """Already correctly placed: no churn."""
    root = tmp_path / "drive"
    day = "2014-08-19"
    n = DEFAULT_EVERYDAY_DAY_THRESHOLD + 1
    rows = [
        (
            f"2014/2014-08/{day} - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T12:{i % 60:02d}:00",
            f"ok-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert plan.moves == []
    assert plan.unchanged == n
    assert plan.day_folder_reasons == ()


def test_migrate_both_directions_in_one_reconcile_pass(tmp_path: Path) -> None:
    """One plan: month→day when over, day→month when under; one reason each."""
    root = tmp_path / "drive"
    over_day = "2014-08-15"
    under_day = "2014-08-16"
    over_n = DEFAULT_EVERYDAY_DAY_THRESHOLD + 1
    under_n = 3
    rows = [
        (
            f"2014/2014-08/2014-08 - Everyday/over_{i:03d}.jpg",
            "Camera",
            f"{over_day}T09:{i % 60:02d}:00",
            f"over-{i}".encode(),
        )
        for i in range(over_n)
    ] + [
        (
            f"2014/2014-08/{under_day} - Everyday/under_{i:03d}.jpg",
            "Camera",
            f"{under_day}T09:{i % 60:02d}:00",
            f"under-{i}".encode(),
        )
        for i in range(under_n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == over_n + under_n
    assert len(plan.day_folder_reasons) == 2
    assert plan.day_folder_reasons[0].startswith(over_day)
    assert "over your threshold" in plan.day_folder_reasons[0]
    assert f"{over_n} photos" in plan.day_folder_reasons[0]
    assert plan.day_folder_reasons[1].startswith(under_day)
    assert "at or under your threshold" in plan.day_folder_reasons[1]
    assert f"{under_n} photos" in plan.day_folder_reasons[1]


def test_hermetic_41_unevented_plans_day_bucket_with_named_reason(tmp_path: Path) -> None:
    """Exactly one over the default (41): month Everyday → day folder + reason naming 41 and 40.

    Mutation: commenting out the ``heavy_day`` render flag (always Everyday) fails this test
    (paths stay monthly, reasons empty). Confirmed fail-then-restore 2026-07-30.
    """
    root = tmp_path / "drive"
    day = "2014-08-21"
    n = 41
    assert n == DEFAULT_EVERYDAY_DAY_THRESHOLD + 1
    rows = [
        (
            f"2014/2014-08/2014-08 - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T10:{i % 60:02d}:00",
            f"h41-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == n
    assert all(f"{day} - Everyday" in m.new_relative for m in plan.moves)
    assert plan.day_folder_reasons == (
        (
            f"{day} now has 41 photos, over your threshold of {DEFAULT_EVERYDAY_DAY_THRESHOLD} "
            "- moving to its own day folder"
        ),
    )


def test_hermetic_39_unevented_plans_monthly_everyday(tmp_path: Path) -> None:
    """Exactly one under the default (39): day Everyday → monthly bucket + reverse reason.

    Mutation: flipping ``heavy_capture_days`` from ``n > limit`` to ``n >= limit`` would leave
    a day of 40 in DAY_BUCKET; at 39 this still coalesces, but treating every positive count as
    heavy (``n > 0``) leaves these in the day folder with no reason. Confirmed fail-then-restore
    2026-07-30 by forcing ``heavy_day = True`` in migrate render and watching this fail.
    """
    root = tmp_path / "drive"
    day = "2014-08-22"
    n = 39
    assert n == DEFAULT_EVERYDAY_DAY_THRESHOLD - 1
    rows = [
        (
            f"2014/2014-08/{day} - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T11:{i % 60:02d}:00",
            f"h39-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == n
    assert all("2014-08 - Everyday" in m.new_relative for m in plan.moves)
    assert all(f"{day} - Everyday" not in m.new_relative for m in plan.moves)
    assert plan.day_folder_reasons == (
        (
            f"{day} now has 39 photos, at or under your threshold of "
            f"{DEFAULT_EVERYDAY_DAY_THRESHOLD} - moving back into the monthly Everyday folder"
        ),
    )


def test_hermetic_trip_claimed_100_is_trip_day_not_day_bucket(tmp_path: Path) -> None:
    """100 photos on a trip-claimed day → TRIP_DAY regardless of threshold; no day-folder reason.

    Mutation: skipping ``_confirmed_trip`` sends these to ``DAY_BUCKET`` with an Everyday
    reason. Confirmed fail-then-restore 2026-07-30.
    """
    root = tmp_path / "drive"
    day = "2014-08-23"
    n = 100
    rows = [
        (
            f"2014/2014-08/2014-08 - Everyday/img_{i:03d}.jpg",
            "Camera",
            f"{day}T12:{i % 60:02d}:00",
            f"trip100-{i}".encode(),
        )
        for i in range(n)
    ]
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="D1", label="Drive A")
        _seed(catalog, root, "D1", rows)
        _confirmed_trip(
            catalog,
            name="Wayanad",
            slug="wayanad",
            start_date=day,
            end_date=day,
            days=[day],
        )
        plan = plan_migration(catalog, "D1", DEFAULT_SCHEME, routes={"Camera": ROUTE_TIMELINE})
    assert len(plan.moves) == n
    assert all("Wayanad" in m.new_relative for m in plan.moves)
    assert all(f"{day} - Everyday" not in m.new_relative for m in plan.moves)
    assert plan.day_folder_reasons == ()
