"""The two long writes that do **not** go through `execute` watch the ground too.

`7a88c6e` wired `RunHealth` into `execute`, which covers organize on both surfaces. Two loops
copy for just as long and reach it by neither route:

* `migrate.run_migration` - `LocalDestination.relocate` is a `shutil.copy2`, so a layout change
  **rewrites every byte of the library**. On a cloud-mounted drive those bytes go through the
  client's local cache, which is the 192 GB migration `run_health.py` opens with.
* `service.backup.backup_run` - its own copy loop, in the app package only.

**What each already has, and what it does not, measured rather than assumed.** Both call
`DestinationDevice` per file (backup explicitly, migrate through `LocalDestination._make_parent`),
which is **fail-closed and therefore stricter** than the periodic device watch - so neither gains
anything there, and this file says so rather than implying otherwise. What they gain is the
**space** half:

* migrate has **no free-space check at all**;
* backup has one, on ``shutil.disk_usage(target)`` - the *target*, which on a mounted drive is
  the remote's free space while the disk that actually fills is the local one. That is the exact
  confusion `RunHealth` was written to correct, on a second surface.

**Sizes cost nothing new.** Backup's rows already carry `size`; `copies_for_migration` was
already fetching its row and merely did not select `fc.size`. Neither loop gains a `stat`.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
from truestill_core import run_health
from truestill_core.catalog import Catalog
from truestill_core.destinations.local import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.layout import LayoutScheme, LayoutTemplate
from truestill_core.migrate import plan_migration, run_migration
from truestill_core.run_health import ABSOLUTE_FLOOR_BYTES, watcher_for

_GB = 1024**3


# --- the shared builder, so three sites cannot drift ---------------------------------------------


def test_no_local_root_means_no_watcher(tmp_path: Path) -> None:
    """A remote has no device to lose and no local disk of its own to fill."""
    assert watcher_for(None, tmp_path / "c.sqlite") is None


def test_no_catalog_means_no_watcher(tmp_path: Path) -> None:
    """**The probe is never substituted.**

    The disk that fills is the one the cloud client caches to, and the catalog's folder is the
    local path Truestill is sure of. Probing the destination instead would measure the remote's
    free space - which is precisely the mistake this guard exists to correct, so guessing here
    would rebuild it inside the fix.
    """
    assert watcher_for(tmp_path, None) is None


def test_both_present_builds_a_watcher_probing_the_local_path(tmp_path: Path) -> None:
    catalog = tmp_path / "data" / "c.sqlite"
    catalog.parent.mkdir()
    health = watcher_for(tmp_path, catalog)
    assert health is not None
    assert health.probe == catalog.parent, "the probe is the catalog's folder, not the drive"


# --- the space verdict these two loops are here for ---------------------------------------------


def test_a_filling_local_disk_stops_a_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One reading is enough for space: a local `disk_usage` does not fail transiently, and
    waiting for three would mean watching the disk fill while declining to say so."""
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 500 * _GB)
    health = watcher_for(tmp_path, tmp_path / "c.sqlite")
    assert health is not None

    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES // 2)
    verdict = health.check(largest_remaining=0, written_bytes=10 * _GB)

    assert not verdict.ok
    assert "disk is nearly full" in verdict.detail
    # The message must point at the cause a user cannot see, or it is just a number.
    assert "cache" in verdict.detail


def test_the_message_names_the_local_disk_and_not_the_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole reason this is worth wiring twice.

    A user watching a 4 TB drive fill up is told their *computer* is full. If the wording does
    not make that distinction, the report sends them to check the wrong disk.
    """
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: 1)
    health = watcher_for(tmp_path, tmp_path / "c.sqlite")
    assert health is not None

    detail = health.check(largest_remaining=0, written_bytes=0).detail
    assert "this computer's disk" in detail


# --- migrate, end to end ------------------------------------------------------------------------


def _scheme(template: str) -> LayoutScheme:
    parsed = LayoutTemplate.parse(template)
    return LayoutScheme.of(timeline=parsed, timeline_evented=parsed, side_bin=parsed)


def _library(catalog: Catalog, root: Path) -> None:
    catalog.upsert_drive(uuid="D1", label="Drive A")
    for relative, category, captured, content in (
        ("Camera/2023/08/a.jpg", "Camera", "2023-08-20T14:30:00", b"aaaa"),
        ("Camera/2023/08/b.jpg", "Camera", "2023-08-21T14:30:00", b"bbbbbb"),
        ("WhatsApp/2024/01/c.jpg", "WhatsApp", "2024-01-15T00:00:00", b"cc"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        sha = sha256_file(path)
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
            drive_uuid="D1",
        )


def test_a_migration_stops_when_this_computer_fills_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The 192 GB run this guard was written for.**

    `relocate` is a `copy2`, so a layout change rewrites the whole library - and on a mounted
    cloud drive every byte passes through the client's local cache. Migration had no free-space
    check of any kind, on either disk.
    """
    root = tmp_path / "drive"
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES // 2)

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _library(catalog, root)
        outcome = run_migration(
            catalog, LocalDestination(root), "D1", _scheme("{category}/{yyyy}"), apply=True
        )

    assert outcome.stopped is not None, "the run must say why it stopped"
    assert "this computer's disk" in outcome.stopped
    assert outcome.migrated < len(outcome.plan.moves)


def test_a_stopped_migration_leaves_a_resumable_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stop must leave the unapplied moves replayable.

    **The mechanism, checked rather than assumed** - my first version of this docstring named
    `finish_migration_run` as what would discard the journal, and a mutation proved that wrong:
    it only stamps `completed_at` on the *run* row. What clears a move is
    `complete_migration_move`, called by `_apply_move` per move, so a move never applied is
    still pending by construction. The property is real and worth pinning; the reason I first
    gave for it was not.
    """
    root = tmp_path / "drive"
    monkeypatch.setattr(run_health, "TICK_SECONDS", 0.0)
    monkeypatch.setattr(
        run_health, "read_device", lambda _p: run_health.DeviceReading(7, definite=True)
    )
    monkeypatch.setattr(run_health, "free_bytes", lambda _p: ABSOLUTE_FLOOR_BYTES // 2)

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _library(catalog, root)
        run_migration(
            catalog, LocalDestination(root), "D1", _scheme("{category}/{yyyy}"), apply=True
        )
        assert catalog.pending_migration("D1"), "the journal must survive a stop"


def test_a_healthy_migration_is_untouched(tmp_path: Path) -> None:
    """Cry-wolf, with the real clock and the real disk: every move applied, nothing reported."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _library(catalog, root)
        outcome = run_migration(
            catalog, LocalDestination(root), "D1", _scheme("{category}/{yyyy}"), apply=True
        )

    assert outcome.stopped is None
    assert outcome.migrated == len(outcome.plan.moves)


def test_the_plan_carries_the_size_it_already_had(tmp_path: Path) -> None:
    """No `stat` was added. `copies_for_migration` was fetching the row already and simply did
    not select `fc.size`; a size read from disk here would be one per file on a FUSE mount."""
    root = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _library(catalog, root)
        plan = plan_migration(catalog, "D1", _scheme("{category}/{yyyy}"))

    assert plan.moves, "the fixture must actually move something"
    assert sorted(m.size for m in plan.moves) == [2, 4, 6]
