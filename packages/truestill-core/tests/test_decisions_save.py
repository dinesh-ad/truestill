"""Putting the catalog's decisions onto every reachable drive, without destroying what is there.

**The write is a read-merge-replace, never a write.** `to_document` already carries unknown
sections back out of a `Decisions` that came FROM a document - but the trigger's object comes from
`gather_decisions`, and the catalog has never held those sections, so its `unknown` is empty. A
downgraded user restores, renames one trip, the trigger fires, and the newer version's captions
are deleted from their drive by the code written to prevent that. Preserving on write-back is not
preserving on write, and these tests drive the write from a catalog for that reason: a test that
hands the writer a document object proves the wrong one of the two.

**The same rule, applied to sections we DO understand.** A drive can hold decisions this catalog
does not - that is the lost-machine case, before a restore. Overwriting it with a near-empty
catalog's decisions destroys exactly what the feature exists to protect, so a write that would
lose them does not happen and is reported instead.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.decisions import (
    DECISIONS_NAME,
    DECISIONS_SAVED_AT_KEY,
    SaveOutcome,
    ensure_decisions_on_drives,
    read_decisions,
    save_decisions_to_reachable_drives,
)
from truestill_core.drive import DriveMarker, drive_path_hint, write_marker

_UUID_A = "19411f16-8a00-4873-9b32-04c595eebbe1"
_UUID_B = "7641a720-2c1f-4f0e-9a5f-2b1d3c4e5f60"
_STAMP = "2026-08-09T12:00:00+00:00"


def _register(catalog: Catalog, root: Path, uuid: str, label: str) -> Path:
    """A drive that is registered, marked and reachable - the ordinary case."""
    root.mkdir(parents=True, exist_ok=True)
    write_marker(root, DriveMarker(uuid=uuid, label=label, created="2026-01-01T00:00:00+00:00"))
    catalog.upsert_drive(uuid=uuid, label=label)
    catalog.set_setting(drive_path_hint(uuid), str(root))
    return root


def _with_a_trip(catalog: Catalog) -> None:
    catalog.create_trip(
        name="Wayanad",
        slug="wayanad",
        start_date="2014-08-14",
        end_date="2014-08-15",
        days=["2014-08-14", "2014-08-15"],
    )


def _document_at(root: Path) -> dict[str, object]:
    return json.loads((root / DECISIONS_NAME).read_text(encoding="utf-8"))


# --- the merge: the property the write-back test cannot see -------------------------------


def test_an_unknown_section_survives_a_write_driven_by_the_catalog(tmp_path: Path) -> None:
    """THE MERGE, NOT THE PRESERVATION. The document handed to the drive is built by
    `gather_decisions`, so its `unknown` is empty by construction - only a read of what is
    already at that root can carry a newer version's section forward.

    A user who downgrades and renames one trip must not lose their captions to the trigger.
    """
    root = tmp_path / "drive"
    root.mkdir()
    (root / DECISIONS_NAME).write_text(
        json.dumps(
            {
                "format": 1,
                "written": "2026-08-01T00:00:00+00:00",
                "captions": {"a" * 64: "on the ferry"},
            }
        ),
        encoding="utf-8",
    )

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    document = _document_at(root)
    assert results[0].outcome is SaveOutcome.WRITTEN
    assert document["captions"] == {"a" * 64: "on the ferry"}, (
        "a section written by a newer Truestill was destroyed by a catalog-driven write"
    )
    assert [t["name"] for t in document["trips"]] == ["Wayanad"], "the new decisions did not land"


def test_a_document_holding_decisions_this_catalog_lacks_is_not_overwritten(
    tmp_path: Path,
) -> None:
    """THE LOST-MACHINE CASE, BEFORE A RESTORE EXISTS. A re-attached drive carries names a fresh
    catalog has never seen. Writing this catalog's decisions over them destroys the only copy -
    the exact loss this feature exists to prevent, performed by the feature."""
    root = tmp_path / "drive"
    root.mkdir()
    (root / DECISIONS_NAME).write_text(
        json.dumps(
            {
                "format": 1,
                "written": "2026-08-01T00:00:00+00:00",
                "trips": [
                    {
                        "name": "Ooty",
                        "slug": "ooty",
                        "start": "2013-09-13",
                        "end": "2013-09-16",
                        "days": ["2013-09-13"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before = (root / DECISIONS_NAME).read_text(encoding="utf-8")

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)  # a DIFFERENT trip; the catalog knows nothing of Ooty
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    assert results[0].outcome is SaveOutcome.WOULD_LOSE
    assert "trips" in results[0].detail, (
        f"the report does not name what would be lost: {results[0].detail}"
    )
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == before, (
        "the document was rewritten"
    )


def test_a_document_that_cannot_be_read_is_never_overwritten(tmp_path: Path) -> None:
    """Half a JSON file is still someone's names, and a human can often recover them. Replacing
    it because we could not parse it turns a damaged copy into no copy."""
    root = tmp_path / "drive"
    root.mkdir()
    (root / DECISIONS_NAME).write_text('{"format": 1, "trips": [', encoding="utf-8")

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    assert results[0].outcome is SaveOutcome.FAILED
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == '{"format": 1, "trips": ['


# --- every reachable drive, and only reachable ones ----------------------------------------


def test_every_reachable_drive_gets_the_same_document_and_the_same_stamp(tmp_path: Path) -> None:
    """One stamp for the run, not one per drive. Restore resolves disagreement by newest
    `written`, so two drives saved by the same run must not be able to disagree about which is
    newer - a per-drive clock read makes the last drive win a race nobody entered."""
    a = tmp_path / "a"
    b = tmp_path / "b"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, a, _UUID_A, "Output")
        _register(catalog, b, _UUID_B, "Backup")
        _with_a_trip(catalog)
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    assert [r.outcome for r in results] == [SaveOutcome.WRITTEN, SaveOutcome.WRITTEN]
    assert _document_at(a)["written"] == _document_at(b)["written"] == _STAMP
    assert _document_at(a)["drive"] == {"uuid": _UUID_A, "label": "Output", "notes": None}
    assert _document_at(b)["drive"] == {"uuid": _UUID_B, "label": "Backup", "notes": None}


def test_an_unreachable_drive_is_reported_and_nothing_is_written(tmp_path: Path) -> None:
    """A drive that is not plugged in is the ordinary state, not a failure - and writing to the
    path it used to be at would put a decisions file in whatever is mounted there now."""
    gone = tmp_path / "gone"
    gone.mkdir()  # a real directory, but no marker: something else is mounted here

    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid=_UUID_A, label="Output")
        catalog.set_setting(drive_path_hint(_UUID_A), str(gone))
        _with_a_trip(catalog)
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    assert results[0].outcome is SaveOutcome.UNREACHABLE
    assert not list(gone.iterdir()), "a document was written to a path this drive is not at"


def test_a_drive_that_cannot_take_the_document_never_costs_the_others_theirs(
    tmp_path: Path,
) -> None:
    """ONE BAD DRIVE NEVER COSTS THE OTHERS THEIR COPY, on every platform.

    The obstruction is a directory sitting where the document goes, rather than a read-only
    drive: `chmod` on a directory does nothing on Windows, so a permission-based version of this
    test passes there for the wrong reason and proves isolation on two platforms out of three.
    The realistic read-only case is covered below, POSIX-only and marked as such.
    """
    blocked = tmp_path / "blocked"
    fine = tmp_path / "fine"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, blocked, _UUID_A, "Blocked")
        _register(catalog, fine, _UUID_B, "Fine")
        _with_a_trip(catalog)
        (blocked / DECISIONS_NAME).mkdir()
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    by_uuid = {r.uuid: r for r in results}
    assert by_uuid[_UUID_A].outcome is SaveOutcome.FAILED
    assert by_uuid[_UUID_A].detail
    assert by_uuid[_UUID_B].outcome is SaveOutcome.WRITTEN
    assert (fine / DECISIONS_NAME).exists()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="a read-only directory is POSIX permissions, and root ignores them",
)
def test_a_read_only_drive_is_reported_rather_than_written_to(tmp_path: Path) -> None:
    """The realistic shape of the case above: a disk with the write-protect tab on, which is a
    normal Tuesday for removable media rather than an exception."""
    locked = tmp_path / "locked"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, locked, _UUID_A, "Locked")
        _with_a_trip(catalog)
        locked.chmod(0o500)
        try:
            results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)
        finally:
            locked.chmod(0o700)

    assert results[0].outcome is SaveOutcome.FAILED
    assert not (locked / DECISIONS_NAME).exists()


# --- the upgrade write ---------------------------------------------------------------------


def test_the_upgrade_write_happens_once_and_not_again(tmp_path: Path) -> None:
    """Existing users have decisions and no drive copy, and the one most at risk has a finished
    library and has stopped naming things - so a trigger of 'after a decision changes' never
    fires for them. This is the run that protects them, and it is not a modal."""
    root = tmp_path / "drive"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)

        first = ensure_decisions_on_drives(catalog, stamp=_STAMP)
        stamped = catalog.get_setting(DECISIONS_SAVED_AT_KEY)
        (root / DECISIONS_NAME).unlink()
        second = ensure_decisions_on_drives(catalog, stamp=_STAMP)

    assert first is not None
    assert first[0].outcome is SaveOutcome.WRITTEN
    assert stamped == _STAMP
    assert second is None, "the upgrade write ran twice"
    assert not (root / DECISIONS_NAME).exists(), "the second run wrote anyway"


def test_the_upgrade_write_is_not_recorded_when_no_drive_took_it(tmp_path: Path) -> None:
    """CRY-WOLF HALF, and the case that decides whether this protects anyone. A user whose drive
    is in a drawer at upgrade time must get the write when they next plug it in - recording the
    attempt would mean they never do."""
    gone = tmp_path / "gone"
    gone.mkdir()

    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid=_UUID_A, label="Output")
        catalog.set_setting(drive_path_hint(_UUID_A), str(gone))
        _with_a_trip(catalog)

        ensure_decisions_on_drives(catalog, stamp=_STAMP)

        assert catalog.get_setting(DECISIONS_SAVED_AT_KEY) is None, (
            "an upgrade write that reached no drive was recorded as done"
        )


def test_the_bookkeeping_key_never_reaches_a_drive(tmp_path: Path) -> None:
    """`decisions.saved_at` is this machine's note to itself, not a decision. Restored onto
    another machine it would suppress that machine's upgrade write - the document would carry the
    reason it is never written again."""
    root = tmp_path / "drive"

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, "2026-08-01T00:00:00+00:00")
        save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    text = (root / DECISIONS_NAME).read_text(encoding="utf-8")
    assert DECISIONS_SAVED_AT_KEY not in text
    assert "decisions." not in text


# --- the format gate: a newer document is never overwritten by an older reader --------------


def _document(root: Path, body: dict[str, object]) -> str:
    root.mkdir(parents=True, exist_ok=True)
    (root / DECISIONS_NAME).write_text(json.dumps(body), encoding="utf-8")
    return (root / DECISIONS_NAME).read_text(encoding="utf-8")


def test_a_document_from_a_newer_truestill_is_never_overwritten(tmp_path: Path) -> None:
    """THE LOSS THIS CLOSES, and it was live. A `format: 2` document was read, its unknown
    sections carried forward, and its KNOWN sections overwritten by this version's - so a user
    who downgraded lost every trip name the newer version had recorded differently, while the
    sections we could not understand survived. Exactly backwards.

    `FORMAT_VERSION`'s contract is that a bump means a reader must refuse, and until now nothing
    read the field at all.
    """
    root = tmp_path / "drive"
    before = _document(
        root,
        {
            "format": 2,
            "written": "2026-09-01T00:00:00+00:00",
            "trips": [{"name": "Ooty", "slug": "ooty", "start": "2013-09-13", "end": "2013-09-16"}],
            "captions": {"a" * 64: "written by a version this one predates"},
        },
    )

    with Catalog(tmp_path / "c.sqlite") as catalog:
        _register(catalog, root, _UUID_A, "Output")
        _with_a_trip(catalog)
        results = save_decisions_to_reachable_drives(catalog, stamp=_STAMP)

    assert results[0].outcome is SaveOutcome.NEWER_VERSION
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == before, (
        "an older Truestill rewrote a newer version's document"
    )


def test_the_refusal_names_the_remedy_rather_than_the_errno(tmp_path: Path) -> None:
    """A refusal without a remedy is the stranded-names failure this feature exists to prevent.
    The names are on the disk and readable; the user needs to be told what to run."""
    root = tmp_path / "drive"
    _document(root, {"format": 99, "written": "2026-09-01T00:00:00+00:00"})

    found = read_decisions(root)

    assert found.too_new is True
    assert found.format_version == 99
    assert found.error is not None
    assert "newer" in found.error.lower()
    assert "upgrade" in found.error.lower(), f"no remedy named: {found.error!r}"


def test_a_document_of_this_version_is_still_read(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A gate that refused everything would pass the two tests above and stop the
    feature working at all."""
    root = tmp_path / "drive"
    _document(root, {"format": 1, "written": "2026-08-01T00:00:00+00:00", "skipped_clusters": []})

    found = read_decisions(root)

    assert found.too_new is False
    assert found.decisions is not None
    assert found.error is None


def test_a_document_that_does_not_say_its_format_is_read_rather_than_refused(
    tmp_path: Path,
) -> None:
    """Missing reads as current, the same way a missing section reads as empty: a hand-written or
    truncated-by-an-editor document is not evidence of a newer version, and refusing it would
    strand names on a disk the user can see."""
    root = tmp_path / "drive"
    _document(root, {"written": "2026-08-01T00:00:00+00:00", "skipped_clusters": ["b" * 64]})

    found = read_decisions(root)

    assert found.too_new is False
    assert found.decisions is not None
    assert found.decisions.skipped_clusters == ("b" * 64,)


def test_a_format_that_is_not_a_number_is_refused_rather_than_crashing(tmp_path: Path) -> None:
    """`int("banana")` raises, and this module's whole contract is that it never does."""
    root = tmp_path / "drive"
    before = _document(root, {"format": "banana", "written": "2026-08-01T00:00:00+00:00"})

    found = read_decisions(root)

    assert found.error is not None
    assert found.decisions is None
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == before
