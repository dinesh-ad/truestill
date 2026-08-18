"""`truestill verify` on a clone says the identity answers in two places. `(adx)` gap 1.

The traced defect: `cp -a B C` copies the marker, `verify C` reports every copy verified, the
remembered path silently moves to `C`, and `status` keeps saying the photos are on ONE drive while
two complete copies exist. **Under-reporting custody is the direction that gets a copy deleted.**

⚠ **The timestamp assertion is the one that pins the call ORDER**, which is the whole difficulty
here. `upsert_drive` refreshes `drives.last_seen` and the hint write replaces the remembered path -
the two halves of the evidence, destroyed five lines apart inside one transaction. A check placed
after either of them still produces a message; it just produces a *wrong* one, naming the moment it
ran instead of the previous sighting. Asserting the reported time is the OLD one is what makes the
ordering testable at all.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint

_EARLIER = "2019-01-02T03:04:05+00:00"


def _a_registered_drive(root: Path, db: Path) -> str:
    """A drive with a marker on disk and a catalog that remembers it here, seen long ago."""
    root.mkdir(parents=True, exist_ok=True)
    marker = create_marker(root, "Photos")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        catalog.set_setting(drive_path_hint(marker.uuid), str(root))
        catalog._conn.execute(
            "UPDATE drives SET last_seen = ? WHERE uuid = ?", (_EARLIER, marker.uuid)
        )
        catalog._conn.commit()
    return marker.uuid


def test_verifying_a_clone_says_the_drive_answers_in_two_places(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = tmp_path / "B"
    db = tmp_path / "catalog.sqlite"
    _a_registered_drive(original, db)
    clone = tmp_path / "C"
    shutil.copytree(original, clone)

    main(["verify", str(clone), "--db", str(db)])

    err = capsys.readouterr().err
    assert "also answers at" in err, (
        "verifying a clone said nothing. Both trees carry one drive id, so the catalog counts "
        "two real copies as one and its custody claim is short by one."
    )
    assert str(original) in err, "the other place must be named"
    assert str(clone) in err, "the place in use must be named"
    assert _EARLIER in err, (
        "the note did not carry the PREVIOUS sighting. `upsert_drive` refreshes `last_seen`, so "
        "reading it after that call reports the moment the check ran instead of when the other "
        "place was last seen - which is the ordering this test exists to pin."
    )
    assert "--force-new-identity" in err, "the remedy must be named"


def test_verifying_after_a_plain_move_says_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf guard, and the reason the rule reports only the unambiguous case.

    After `mv`, the old path is gone. A move and a clone whose original is unplugged are
    observationally identical, so a check that fired here would fire on every ordinary relocation
    and be trained away exactly like a false verify alarm.
    """
    original = tmp_path / "B"
    db = tmp_path / "catalog.sqlite"
    _a_registered_drive(original, db)
    moved = tmp_path / "C"
    original.rename(moved)

    main(["verify", str(moved), "--db", str(db)])

    assert "also answers at" not in capsys.readouterr().err
