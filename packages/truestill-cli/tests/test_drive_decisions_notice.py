"""A drive that is carrying decisions says so, on the two screens that touch a drive.

**Restore works and nothing points at it** - the Adobe failure one step later. A user who has
lost their machine has a rescue file, a working command, and no way to learn either exists.

**Two places, because neither covers the other.** `drives --init` is the lost-machine path: the
catalog is empty, so `drives` iterates zero rows and touches no path at all. The listing is the
partial case - a catalog that exists, a drive that is registered, and decisions on it this
machine does not have.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.decisions import DECISIONS_NAME, Decisions, write_decisions
from truestill_core.drive import create_marker, drive_path_hint

_TRIP = {
    "name": "Wayanad",
    "slug": "wayanad",
    "start": "2014-08-14",
    "end": "2014-08-14",
    "days": ["2014-08-14"],
}


def _drive(tmp_path: Path, **kwargs: object) -> tuple[Path, str]:
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Output")
    write_decisions(
        root,
        Decisions(
            drive_uuid=marker.uuid,
            drive_label="Output",
            written="2026-08-01T00:00:00+00:00",
            **kwargs,  # type: ignore[arg-type]
        ),
    )
    return root, marker.uuid


def test_init_offers_the_restore_when_the_drive_knows_more_than_the_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE LOST-MACHINE PATH. `drives` on an empty catalog iterates zero rows and touches no
    path, so the listing cannot be where this user is told. `--init` is holding the root."""
    root, _ = _drive(tmp_path, trips=(_TRIP,))
    db = tmp_path / "c.sqlite"

    code = main(["drives", "--init", str(root), "--label", "Output", "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    assert "truestill restore" in out, "the command that would recover them was not named"
    assert "trips" in out


def test_init_says_nothing_when_the_catalog_already_has_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CRY-WOLF HALF. Every ordinary re-attach carries a document the catalog already has, and an
    offer on every one of those is a line people learn to skip past."""
    root, uuid = _drive(tmp_path, trips=(_TRIP,))
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.create_trip(
            name="Wayanad",
            slug="wayanad",
            start_date="2014-08-14",
            end_date="2014-08-14",
            days=["2014-08-14"],
        )

    main(["drives", "--init", str(root), "--label", "Output", "--db", str(db), "--uuid", uuid])

    assert "truestill restore" not in capsys.readouterr().out


def test_the_listing_offers_it_for_a_reachable_drive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE PARTIAL CASE: the catalog exists and knows this drive, but not what is written on it."""
    root, uuid = _drive(tmp_path, trips=(_TRIP,))
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Output")
        catalog.set_setting(drive_path_hint(uuid), str(root))

    code = main(["drives", "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    assert "truestill restore" in out


def test_an_empty_catalog_still_just_says_how_to_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REGRESSION GUARD. The listing's existing behaviour on a fresh catalog is one helpful line,
    and the new read must not turn that into an error or a stack of nothing-to-say."""
    code = main(["drives", "--db", str(tmp_path / "c.sqlite")])

    assert code == 0
    assert "No drives known" in capsys.readouterr().out


def test_a_newer_document_leads_with_the_names_being_safe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One wording, every surface. The order is the message: safe and readable, then why, then
    the remedy - and no offer to fix, convert or overwrite."""
    root = tmp_path / "drive"
    root.mkdir()
    create_marker(root, "Output")
    (root / DECISIONS_NAME).write_text(json.dumps({"format": 9}), encoding="utf-8")
    db = tmp_path / "c.sqlite"

    main(["drives", "--init", str(root), "--label", "Output", "--db", str(db)])

    out = capsys.readouterr().out
    assert out.index("safe") < out.index("cannot use") < out.index("Upgrade")
    assert "truestill restore" in out


def test_the_offer_goes_away_once_the_decisions_are_restored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONLY THE SECOND LOOK TELLS THESE APART. An offer that stays after the user has acted on it
    is worse than no offer: it says the rescue did not work. Restore, then list again."""
    root, uuid = _drive(tmp_path, trips=(_TRIP,))
    db = tmp_path / "c.sqlite"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Output")
        catalog.set_setting(drive_path_hint(uuid), str(root))
    monkeypatch.setattr("builtins.input", lambda *_: "restore")
    main(["restore", str(root), "--db", str(db), "--apply"])
    capsys.readouterr()

    main(["drives", "--db", str(db)])

    assert "truestill restore" not in capsys.readouterr().out
