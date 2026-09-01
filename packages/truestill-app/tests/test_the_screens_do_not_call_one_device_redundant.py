"""The four screens that asserted redundancy now read one verdict from core. `(aiy)`

**The last four of six surfaces.** `reclaim` (`e6ef82c`) and `status` (`8511aef`) were fixed
first because one deletes and the other is the command a worried user runs. These four reach a
screen, so they are one commit: four would run the 26-minute browser lane four times to answer one
question.

⚠ **`app.js`'s backup card was different in kind from the other three.** They ask the wrong
question - a count of registrations; it asked **no question at all**:

    sub: "Your library now lives in more than one place."

An unconditional string literal, true or false, on every backup ever run.

🔑 **ONE VERDICT, ONE SENTENCE, THREE PAYLOADS.** `drive.copy_independence` decides,
`drive.LIBRARY_REDUNDANCY` words it, and the payloads hand it over - the shape `(ajf)`'s
`eject_note` established. A screen composes nothing.

⚠ **THE THREE-HOLDER CASE IS HERE ON PURPOSE.** `e6ef82c` shipped a predicate that was wrong for
``[7, 7, 9]`` and **no test written for it could have caught that**, because every case had two
holders and the predicate has three states. A set with more members than states is the minimum
that can distinguish them.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
from truestill_core.catalog import Catalog
from truestill_core.drive import (
    LIBRARY_REDUNDANCY,
    CopyIndependence,
    copy_independence,
    create_marker,
    drive_path_hint,
)
from truestill_core.hashing import sha256_file

_APP = Path(__file__).resolve().parents[1] / "src" / "truestill_app"
_APP_JS = (_APP / "static" / "app.js").read_text(encoding="utf-8")


def test_the_backup_card_no_longer_asserts_redundancy_with_no_query() -> None:
    """⚠ THE DETECTOR for the surface that consulted nothing."""
    assert 'sub: "Your library now lives in more than one place."' not in _APP_JS, (
        "the unconditional literal is back"
    )
    assert "r.independence_note" in _APP_JS, "the card does not read the verdict it was given"


def test_every_screen_reads_the_verdict_rather_than_composing_one() -> None:
    """Four surfaces, one source. A screen that spells its own sentence is what this refuses."""
    for marker, what in (
        ("r.independence_note", "the backup completion card"),
        ("s.independence_note", "the custody strip"),
        ('safety.independence !== "not_independent"', "the Stats safe class"),
        ('lib.independence === "not_independent"', "the drive-card pips"),
    ):
        assert marker in _APP_JS, f"{what} does not read the verdict"
    for sentence in LIBRARY_REDUNDANCY.values():
        assert sentence not in _APP_JS, (
            "a screen spells a sentence core owns; it must be handed over, not retyped"
        )


def test_the_pips_report_failure_domains_not_registrations() -> None:
    """Two folders on one stick filled two green pips on both cards."""
    assert (
        'const pips = lib.independence === "not_independent" ? 1 : Math.min(drives.length, 3);'
        in _APP_JS
    )


def test_the_strip_turns_at_risk_only_on_a_proven_shared_device() -> None:
    """`unknown` must not be dressed as an alarm - `DriveReach`'s ruling, applied to a screen."""
    assert 'const notIndependent = s.independence === "not_independent";' in _APP_JS
    assert 'atRisk || notIndependent ? "at-risk"' in _APP_JS


# ---------------------------------------------------------------- the three-holder case


def test_three_holders_two_devices_is_not_reported_as_one_failure_domain() -> None:
    """⚠ **THE CASE `e6ef82c` GOT WRONG.** Content on ``[7, 7, 9]`` survives device 7."""
    assert copy_independence([7, 7, 9]) is CopyIndependence.POSSIBLY_INDEPENDENT


def test_three_holders_one_device_is_proven() -> None:
    assert copy_independence([7, 7, 7]) is CopyIndependence.NOT_INDEPENDENT


def test_three_holders_with_one_unaskable_is_unknown_not_proven() -> None:
    """The unasked drive may be the one that supplies the diversity."""
    assert copy_independence([7, 7, None]) is CopyIndependence.UNKNOWN


def test_every_verdict_has_a_sentence() -> None:
    """A state with no wording would reach a screen as an empty string and say nothing."""
    for verdict in CopyIndependence:
        assert LIBRARY_REDUNDANCY[verdict].strip(), f"{verdict} has no sentence"


def test_the_payloads_carry_the_verdict_over_http(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    """⚠ **THE WIRE, because a screen test reads a file and proves nothing about a route.**

    Two registered drives inside one `tmp_path` are one device by construction - soak ten's shape
    without a stick. Both payloads the screens read must say so.
    """
    content = b"one-photo"
    source = tmp_path / "src/a.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    sha = sha256_file(source)
    for i, name in enumerate(("drive", "backup")):
        root = tmp_path / "stick" / name
        root.mkdir(parents=True, exist_ok=True)
        copy = root / "Camera/a.jpg"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(content)
        marker = create_marker(root, f"D{i}")
        with Catalog(db_path) as catalog:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(drive_path_hint(marker.uuid), str(root))
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
                drive_uuid=marker.uuid,
            )

    status = client.get("/api/library/status").json()
    assert status["independence"] == "not_independent"
    assert status["independence_note"] == LIBRARY_REDUNDANCY[CopyIndependence.NOT_INDEPENDENT]

    stats = client.get("/api/library/stats").json()
    assert stats["safety"]["independence"] == "not_independent"
