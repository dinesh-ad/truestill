"""Two copies on one device do not make a backup, and `reclaim` must not delete on that. `(aiy)`

**The harm, measured in soak ten.** Two drives registered in two folders of one USB stick are two
`file_copies` rows, so `copy_count` is 2 and `ReclaimPlan.single_copy` - the only guard between a
user and ``reclaim --apply``, which argparse calls *"actually delete sources"* - is **empty**. The
originals are freed on the strength of a copy that fails at the same moment as the first.

🔑 **THE ASYMMETRY IS THE DESIGN.** `destinations/local.py` records what `st_dev` cannot do:
*"``st_dev`` can agree across btrfs subvolumes and bind mounts where a rename still fails."* Two
roots sharing a device **prove** they are not independent; two roots differing **prove nothing**,
because two partitions of one disk differ. So the check can falsify and never confirm, and the
third state is `POSSIBLY_INDEPENDENT` rather than anything that reads as confirmed.

⚠ **The regression this file exists to prevent is the FALSE NEGATIVE.** A user with two genuinely
separate drives must still reclaim without a warning that frightens them off - see
`test_two_drives_on_different_real_filesystems_do_not_warn`, which uses **two real filesystems**
rather than a fake.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.drive import (
    CopyIndependence,
    copy_independence,
    create_marker,
    drive_path_hint,
)
from truestill_core.hashing import sha256_file
from truestill_core.reclaim import plan_reclaim

#: Roots to try for a filesystem other than the one `tmp_path` is on. **Real mounts, never a fake**
#: - the point of the regression test is that the seam matches reality.
_OTHER_FS_CANDIDATES = (
    "/dev/shm",
    f"/run/user/{os.getuid()}" if os.name == "posix" else "",
    "/tmp",
)


def _second_filesystem(here: Path) -> Path | None:
    """A writable directory on a DIFFERENT device from ``here``, or ``None`` if the machine has one."""
    try:
        mine = here.stat().st_dev
    except OSError:  # pragma: no cover - tmp_path always exists
        return None
    for candidate in _OTHER_FS_CANDIDATES:
        if not candidate:
            continue
        root = Path(candidate)
        try:
            if root.is_dir() and root.stat().st_dev != mine and os.access(root, os.W_OK):
                return root
        except OSError:
            continue
    return None


def _seed(
    catalog: Catalog, source: Path, drive_root: Path, uuid: str, label: str, content: bytes
) -> None:
    """One source file, copied onto ``drive_root`` and recorded as a copy on ``uuid``."""
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    sha = sha256_file(source)
    copy = drive_root / "Camera/a.jpg"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(content)
    # A registered drive carries its marker; `drive_reach` reads it to decide CONNECTED, so a
    # fixture without one models an offline drive and every verdict comes out UNKNOWN.
    create_marker(drive_root, label, uuid=uuid)
    catalog.upsert_drive(uuid=uuid, label=label)
    catalog.set_setting(drive_path_hint(uuid), str(drive_root))
    catalog.record_uploaded(
        source_path=str(source),
        original_name=source.name,
        sha256=sha,
        copy_sha256=sha,
        perceptual=None,
        size=len(content),
        captured_at=None,
        category="Camera",
        relative="Camera/a.jpg",
        drive_uuid=uuid,
    )


# ---------------------------------------------------------------- the predicate, pure


def test_the_same_device_twice_is_proven_not_independent() -> None:
    assert copy_independence([7, 7]) is CopyIndependence.NOT_INDEPENDENT


def test_two_distinct_devices_are_enough_even_with_a_duplicate() -> None:
    """⚠ **CORRECTED 2026-09-01 (P179).** The test is distinct devices, not duplicate detection.

    Content on ``[7, 7, 9]`` survives device 7 failing, so calling it not-independent would be
    false - and `reclaim`'s surface said *"every copy on ONE DEVICE"* about exactly that shape
    until this was fixed. It over-warned and never under-warned, so nothing was unsafe; a warning
    that fires when nothing is wrong is the cry-wolf `run_health` names as the failure mode to
    fear.
    """
    assert copy_independence([7, 7, 9]) is CopyIndependence.POSSIBLY_INDEPENDENT


def test_an_unknown_holder_can_supply_the_missing_diversity() -> None:
    """``[7, 7, None]`` is UNKNOWN, not proven: the unasked drive may be somewhere else."""
    assert copy_independence([7, 7, None]) is CopyIndependence.UNKNOWN


def test_a_lone_copy_is_honestly_one_failure_domain() -> None:
    """True, and `single_copy` is where a user is told about it - see `ReclaimPlan.not_independent`."""
    assert copy_independence([9]) is CopyIndependence.NOT_INDEPENDENT


def test_an_unaskable_holder_is_unknown_not_a_verdict() -> None:
    assert copy_independence([7, None]) is CopyIndependence.UNKNOWN


def test_all_known_and_all_different_is_only_possibly_independent() -> None:
    """⚠ The name is the ruling: differing devices prove nothing about failure domains."""
    assert copy_independence([7, 9]) is CopyIndependence.POSSIBLY_INDEPENDENT


# ---------------------------------------------------------------- the wiring, real filesystems


def test_two_drives_under_one_root_warn(tmp_path: Path) -> None:
    """⚠ **THE DEFECT REPRODUCED.** Needs no corpus, no loop device and no second filesystem.

    This is soak ten in four lines: two registered drives inside one `tmp_path`, therefore one
    device. `single_copy` stays empty - the count is honestly 2 - and `not_independent` is what
    fires instead.
    """
    a, b = tmp_path / "stick/drive", tmp_path / "stick/backup"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, tmp_path / "src/a.jpg", a, "D1", "Drive A", b"content-a")
        _seed(catalog, tmp_path / "src/a.jpg", b, "D2", "Drive B", b"content-a")
        plan = plan_reclaim(catalog, "D1", a)

        assert plan.candidates, "nothing to reclaim - the fixture did not seed a candidate"
        assert plan.candidates[0].copies == 2, "the count is honestly two registrations"
        assert not plan.single_copy, "the old guard is silent here, which is the whole defect"
        assert len(plan.not_independent) == 1, (
            "two folders on one device were not reported as one failure domain"
        )


def test_two_drives_on_different_real_filesystems_do_not_warn(tmp_path: Path) -> None:
    """⚠ **THE REGRESSION.** A user with two genuinely separate drives must not be warned.

    **Two real filesystems**, discovered at runtime - not a monkeypatched device id, because the
    thing under test is whether the seam agrees with the kernel. Skipped only on a machine that
    genuinely has one filesystem, and the reason says so rather than passing quietly.
    """
    other = _second_filesystem(tmp_path)
    if other is None:  # pragma: no cover - depends on the machine, not the code
        pytest.skip("this machine exposes one filesystem; the case needs two real ones")
    b = other / f"truestill-aiy-{os.getpid()}"
    try:
        with Catalog(tmp_path / "c.sqlite") as catalog:
            _seed(catalog, tmp_path / "src/a.jpg", tmp_path / "drive", "D1", "A", b"content-a")
            _seed(catalog, tmp_path / "src/a.jpg", b, "D2", "B", b"content-a")
            plan = plan_reclaim(catalog, "D1", tmp_path / "drive")

            assert plan.candidates
            assert not plan.not_independent, (
                "two drives on different real filesystems were called one failure domain"
            )
            assert not plan.independence_unknown, "both drives are connected and were asked"
    finally:
        for path in sorted(b.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        b.rmdir()


def test_a_drive_that_cannot_be_asked_is_unknown_and_is_not_refused(tmp_path: Path) -> None:
    """The common case: a second drive in a drawer. Reported, never blocking."""
    a = tmp_path / "drive"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        _seed(catalog, tmp_path / "src/a.jpg", a, "D1", "A", b"content-a")
        _seed(catalog, tmp_path / "src/a.jpg", tmp_path / "gone", "D2", "B", b"content-a")
        # The second drive's remembered path stops answering - a drawer, not a deletion.
        catalog.set_setting(drive_path_hint("D2"), str(tmp_path / "not-here"))
        plan = plan_reclaim(catalog, "D1", a)

        assert plan.candidates, "an unaskable second drive must not remove the candidate"
        assert len(plan.independence_unknown) == 1
        assert not plan.not_independent, "unknown must never be reported as proven"
