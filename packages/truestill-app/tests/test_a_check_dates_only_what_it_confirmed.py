"""A check that contradicted the custody claim must not date it. `(abg)` Stage 2.

**Stage 1 introduced this, which is why it is worth a file of its own.** Stage 1 carried
`drives.last_verified` to the number a person reads - `custody_checked_at` on the strip. It did
not ask what advances that date, and the answer was: every verify run, unconditionally. So a run
whose own summary said `missing: 2269` stamped the drive as verified *now*, and the reassuring
sentence got **fresher** on the strength of evidence that contradicted it. That is `(abg)`'s own
thesis - history reported as state - reappearing inside `(abg)`'s own fix, and it is worse than
the defect Stage 1 addressed: Stage 1 made the claim datable and the date meaningless.

The rule is not new and is deliberately not restated here: `custody_freshness` already argues that
a claim is only as fresh as its **weakest leg**, and this is that argument one level down. The
drive's date is derived from its copies rather than stamped beside them, which makes it
structurally incapable of over-claiming rather than merely correct today.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from truestill_app.service import verify as verify_service
from truestill_app.service.verify import verify_run
from truestill_core import verify as core_verify
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

RELATIVE = "Camera/2014/a.jpg"
SECOND = "Camera/2014/b.jpg"


def _drive_with_two_copies(tmp_path: Path) -> tuple[Path, Path, str]:
    """A marked drive holding two recorded copies, both present and both matching."""
    db = tmp_path / "c.sqlite"
    root = tmp_path / "Everyday"
    root.mkdir()
    marker = create_marker(root, label="Everyday")

    shas = []
    for relative, payload in ((RELATIVE, b"first"), (SECOND, b"second")):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        shas.append(sha256_file(path))

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        for relative, sha in ((RELATIVE, shas[0]), (SECOND, shas[1])):
            catalog.record_uploaded(
                source_path=f"/src/{Path(relative).name}",
                original_name=Path(relative).name,
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=5,
                captured_at=None,
                category="Camera",
                relative=relative,
                drive_uuid=marker.uuid,
            )
    return db, root, marker.uuid


def _run(target: object, *, cancel: threading.Event | None = None) -> dict[str, Any]:
    assert callable(target), f"verify_run soft-failed: {target}"
    summary: dict[str, Any] = target(lambda _p: None, cancel or threading.Event())
    return summary


def _drive_date(db: Path, uuid: str) -> str | None:
    with Catalog(db) as catalog:
        row = next(d for d in catalog.list_drives() if d["uuid"] == uuid)
    value = row["last_verified"]
    return None if value is None else str(value)


def test_a_run_that_found_every_copy_missing_does_not_date_the_claim(tmp_path: Path) -> None:
    """THE DEFECT, stated as the sentence a user would read.

    The drive is present and identifies itself; its files are not there. Every copy comes back
    `MISSING`, and the custody strip must not then report the claim as checked today.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    for relative in (RELATIVE, SECOND):
        (root / relative).unlink()

    summary = _run(verify_run(root, db))

    assert summary["missing"] == 2, "the run did not observe the absences it is judged on"
    assert summary["verified"] == 0
    assert _drive_date(db, uuid) is None, (
        "a check that confirmed nothing dated the custody claim - the claim got fresher on "
        "evidence that contradicted it"
    )


def test_a_cancelled_run_does_not_date_the_claim(tmp_path: Path) -> None:
    """The same defect without a single failure in it, which is why it needs its own test.

    Everything on this drive is healthy; the run simply stops before confirming any of it.
    `verify_copies` returns partial results on cancel and the old stamp did not care, so a run
    cancelled at the first file dated the whole drive.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    cancelled = threading.Event()
    cancelled.set()

    summary = _run(verify_run(root, db), cancel=cancelled)

    assert summary["verified"] == 0, "the cancel did not take effect, so this proves nothing"
    assert summary["missing"] == 0, "the files were supposed to be present and healthy"
    assert _drive_date(db, uuid) is None, "a cancelled check dated the custody claim"


def test_a_partial_confirmation_dates_the_claim_by_its_weakest_leg(tmp_path: Path) -> None:
    """Confirming SOME copies must not date the drive, because the claim is about all of them.

    `custody_freshness`'s own rule one level down. A version that stamped on any success would
    pass both tests above and still over-claim here.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    (root / SECOND).unlink()

    summary = _run(verify_run(root, db))

    assert (summary["verified"], summary["missing"]) == (1, 1)
    assert _drive_date(db, uuid) is None, "one confirmed copy dated a claim about two"


def test_a_run_that_confirmed_everything_still_dates_the_claim(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A version that never dates anything passes every test above."""
    db, root, uuid = _drive_with_two_copies(tmp_path)

    summary = _run(verify_run(root, db))

    assert summary["verified"] == 2
    assert _drive_date(db, uuid) is not None, "a fully confirmed drive was left undated"


def test_a_copy_looked_for_and_not_found_stops_counting_as_a_place(tmp_path: Path) -> None:
    """The count the entry is about. A promise excludes what was looked for and not found.

    Both files are recorded on one drive, so they are already single-copy; what changes is
    `custody_floor`, which must move them from "held by one drive" to "no copy at all" - the most
    exposed thing in the library, and today invisible.
    """
    db, root, _uuid = _drive_with_two_copies(tmp_path)
    for relative in (RELATIVE, SECOND):
        (root / relative).unlink()

    with Catalog(db) as catalog:
        before = catalog.custody_floor()
        assert (before["no_copy"], before["held"]) == (0, 2), "fixture is not what this assumes"

    _run(verify_run(root, db))

    with Catalog(db) as catalog:
        after = catalog.custody_floor()
        assert after["no_copy"] == 2, "files whose only copy was not found still count as held"
        assert after["held"] == 0
        assert catalog.single_copy_count() == 0, "an absent copy still counted as a place"
        assert catalog.drives_holding([r["sha256"] for r in catalog.single_copy_shas()]) == []


def test_the_drive_list_keeps_the_recorded_count_and_names_the_shortfall(tmp_path: Path) -> None:
    """THE OTHER COUNTING RULE, and it is deliberately the opposite one.

    A promise excludes what was not found; a **history** gains a number rather than losing one.
    `Output` must read "2,269 recorded, 2,269 not found on 11 Aug", not `0` - a count that quietly
    drops to zero destroys the only clue to what happened.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    (root / SECOND).unlink()

    _run(verify_run(root, db))

    with Catalog(db) as catalog:
        row = next(d for d in catalog.list_drives() if d["uuid"] == uuid)
    assert row["file_count"] == 2, "the drive list forgot what was recorded there"
    assert row["missing_count"] == 1, "the drive list did not name the shortfall"


def test_a_drive_pulled_out_mid_run_records_no_absences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ONE WINDOW THAT IS NOT STRUCTURAL, and the reason the marker is read twice.

    Everything else is guaranteed upstream: `verify_run` soft-fails without a marker, so a drive
    that was never there cannot produce a negative at all. But a drive yanked *during* a run is
    present at the start and absent by the end, and every copy it had not reached yet reads as
    missing. Recording those would report a user's backup as gone because they unplugged it.

    The marker read here is the SECOND one - the first already happened when the job was built.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    for relative in (RELATIVE, SECOND):
        (root / relative).unlink()
    # Built while the drive is still identified - that read happens here, outside the patch, so
    # the only `read_marker` left inside the target is the post-run one this is aimed at.
    target = verify_run(root, db)
    monkeypatch.setattr(verify_service, "read_marker", lambda _path: None)

    summary = _run(target)

    assert summary["missing"] == 2, "the run must still REPORT what it saw"
    with Catalog(db) as catalog:
        assert catalog.single_copy_count() == 2, (
            "a drive unplugged mid-run had its copies recorded as gone"
        )
    assert _drive_date(db, uuid) is None


def test_a_copy_that_could_not_be_read_is_not_recorded_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`UNREADABLE` is *we could not look*, not *it is not there* - `(ach)`'s lesson.

    An EIO or a permission denial on a file that is sitting right where it should be must not
    take it out of the custody count. It does hold the drive's date at NULL, because nothing
    about that copy was confirmed.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)

    def unreadable(_path: str) -> str:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(core_verify, "_hash_path", unreadable)

    summary = _run(verify_run(root, db))

    assert summary["unreadable"] == 2, "the fixture did not produce the status it is named for"
    assert summary["missing"] == 0
    with Catalog(db) as catalog:
        assert catalog.single_copy_count() == 2, "an unreadable copy was recorded as gone"
    assert _drive_date(db, uuid) is None, "a copy nobody could read dated the claim"


def test_a_copy_that_comes_back_is_counted_again(tmp_path: Path) -> None:
    """A REMEMBERED ABSENCE IS SPENT THE MOMENT THE COPY IS FOUND AGAIN.

    Found by mutation: removing the `missing_at = NULL` from `mark_copy_verified` killed no test.
    Without it a user who restores a drive and re-checks it sees their files still reported as
    living in one place, and nothing they can do will change it - the catalog would be stuck on
    an observation it had already disproved. The stuck state is worse than the original defect,
    because the original at least corrected itself when the truth was good news.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    payloads = {RELATIVE: b"first", SECOND: b"second"}
    for relative in payloads:
        (root / relative).unlink()
    _run(verify_run(root, db))
    with Catalog(db) as catalog:
        assert catalog.single_copy_count() == 0, "the fixture never recorded the absences"

    for relative, payload in payloads.items():
        (root / relative).write_bytes(payload)
    _run(verify_run(root, db))

    with Catalog(db) as catalog:
        assert catalog.single_copy_count() == 2, "a restored copy stayed uncounted"
        row = next(d for d in catalog.list_drives() if d["uuid"] == uuid)
    assert row["missing_count"] == 0, "the drive card still names a shortfall that was made good"
    assert _drive_date(db, uuid) is not None, "a fully re-confirmed drive was left undated"


def test_recopying_onto_a_drive_also_spends_the_absence(tmp_path: Path) -> None:
    """The other way back, and it must not require the user to think of running a check.

    `record_copy` is what a backup run calls. A restore that copied every file back and left them
    all uncounted until someone remembered to verify would be the same stuck state by a different
    route - which is why the clear lives in the upsert as well.
    """
    db, root, uuid = _drive_with_two_copies(tmp_path)
    for relative in (RELATIVE, SECOND):
        (root / relative).unlink()
    _run(verify_run(root, db))

    with Catalog(db) as catalog:
        for row in catalog.copies_on_drive(uuid):
            catalog.record_copy(
                sha256=row["sha256"],
                drive_uuid=uuid,
                relative=row["relative"],
                copy_sha256=row["copy_sha256"],
                size=row["size"],
            )
        assert catalog.single_copy_count() == 2, "a re-copied file stayed uncounted"
