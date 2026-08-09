"""The decisions document: what a human decided, in a form that outlives the catalog.

**Why this exists.** A catalog can be lost - machine formatted, disk died, file corrupted. The
photos survive on their drives; the DECISIONS do not. Nothing on disk knows "Wayanad"; a human
typed it. Everything else in the catalog - hashes, dates, GPS, camera, categories, placements -
is recomputable by reading the files again. **This is the part that is not.**

**Why not a server.** The market leader has servers, a subscription and the photos, and still
cannot restore a lost catalog. And the backups it does take fail on DISCOVERABILITY rather than
storage: users could not find them, believed they were weekly when the newest was months old, and
found zipped files with undecodable names. Storage was never the problem.

**The least recomputable entry is `date_confirmations`.** Every other decision is a name that
could be retyped from memory. A confirmed date is a human OVERRULING the evidence, and re-reading
the file reproduces the wrong answer they corrected. `skipped_clusters` is the same class: lose it
and the screen re-asks every question the user already declined.

**Event membership is deliberately absent.** `events.signature` is already a SHA-256 over its
sorted member SHA-256s, so a restore re-clusters and matches signatures rather than carrying a
list. Identical membership reproduces the signature and the name re-attaches; a mismatch means
membership changed, and that is exactly the case where the name must NOT be auto-applied
(`d7c6bfc`). Correctness first - the 221 KB it saves is a side effect.
"""

from __future__ import annotations

import json

import pytest
from truestill_core.decisions import FORMAT_VERSION, Decisions, from_document, to_document

_FULL = Decisions(
    drive_uuid="19411f16-8a00-4873-9b32-04c595eebbe1",
    drive_label="Output",
    drive_notes="the spare disk",
    settings={"layout_template": "{yyyy}/{yyyy}-{mm}", "ui.text.size": "medium"},
    trips=(
        {
            "name": "Wayanad",
            "slug": "wayanad",
            "start": "2014-08-14",
            "end": "2014-08-17",
            # A trip's days ride inside the trip. A catalog rowid does not survive the machine
            # that minted it, and carrying one is what let a restore hand every day to trip one.
            "days": ["2014-08-14", "2014-08-15"],
        },
    ),
    events=(
        {
            "name": "Gokul Marriage",
            "slug": "gokul-marriage",
            "start": "2015-10-25",
            "signature": "a" * 64,
        },
    ),
    skipped_clusters=("b" * 64, "c" * 64),
    date_confirmations=(
        {"sha256": "d" * 64, "captured_at": "2015-07-05T11:55:16", "confirmed_by": "user"},
    ),
    albums=({"name": "Favourites", "members": ["e" * 64]},),
    written="2026-08-09T12:00:00+00:00",
)


def test_a_document_round_trips_without_losing_anything() -> None:
    """The whole point: what goes to the drive comes back the same."""
    assert from_document(to_document(_FULL)) == _FULL


def test_the_document_is_json_a_person_can_read() -> None:
    """It must be readable in a text editor when Truestill is gone - that IS the feature.

    Asserted on the rendered text, not on the dict: a structure that serialises to one long line,
    or to base64, satisfies a dict comparison and fails a human at 2am.
    """
    text = json.dumps(to_document(_FULL), indent=2, sort_keys=True)

    assert "Wayanad" in text
    assert "Gokul Marriage" in text
    assert text.count("\n") > 10, "collapsed to a single line; nobody can read that"


def test_the_document_names_its_format_version() -> None:
    """A reader with no version cannot tell an old document from a corrupt one."""
    assert to_document(_FULL)["format"] == FORMAT_VERSION


# --- forward compatibility: the guard that matters most -----------------------------------


def test_an_unknown_key_from_a_future_version_does_not_break_a_restore() -> None:
    """THE ONE THAT MATTERS. A newer Truestill will add fields. An older one reading that drive
    must restore what it understands and keep going - refusing would strand a user's names on a
    disk they can see, which is the failure this whole feature exists to prevent."""
    document = to_document(_FULL)
    document["captions"] = {"f" * 64: "a caption a future version added"}
    document["trips"][0]["weather"] = "monsoon"

    restored = from_document(document)

    assert restored.trips[0]["name"] == "Wayanad", "a sibling key broke a field beside it"
    assert restored.drive_label == "Output"
    assert restored.skipped_clusters == _FULL.skipped_clusters


def test_an_unknown_key_survives_a_round_trip_rather_than_being_dropped() -> None:
    """NOT VACUOUS, and this is what separates real forward compatibility from a shrug.

    Tolerating an unknown key is easy: ignore it. But an older Truestill that reads a drive,
    restores, and later WRITES it back would then silently delete the newer version's data - the
    user downgrades once and loses their captions. Preservation is the requirement; survival of
    the read is only half of it.
    """
    document = to_document(_FULL)
    document["captions"] = {"f" * 64: "written by a newer version"}

    again = to_document(from_document(document))

    assert again["captions"] == {"f" * 64: "written by a newer version"}


def test_a_missing_optional_section_reads_as_empty_rather_than_raising() -> None:
    """An older document simply has fewer sections. That is not corruption."""
    document = to_document(_FULL)
    del document["albums"]
    del document["date_confirmations"]

    restored = from_document(document)

    assert restored.albums == ()
    assert restored.date_confirmations == ()
    assert restored.drive_label == "Output"


# --- privacy: asserted, because a docstring is not a guard ---------------------------------


def test_the_document_never_carries_a_path_hint() -> None:
    """`settings` holds `path_hint.drive.<uuid>` values that are absolute local paths - a
    username, a folder layout, and in one real case the existence of a Crypto Folder. This file
    lands on a drive the user may lend or sell, and those hints are useless on another machine.

    Asserted on the rendered TEXT, so a hint smuggled in under any key still fails.
    """
    leaky = Decisions(
        drive_uuid="u",
        drive_label="Output",
        settings={
            "layout_template": "{yyyy}",
            "path_hint.drive.19411f16": "/home/someone/Photos/Backup",
        },
        written="2026-08-09T12:00:00+00:00",
    )

    text = json.dumps(to_document(leaky))

    assert "path_hint" not in text
    # A neutral path, deliberately: writing a real home directory into a public
    # repository - inside the test that exists to stop personal paths leaking - is the
    # same mistake one layer up. The repo's own naming guard caught it.
    assert "/home/someone" not in text
    assert "layout_template" in text, "the exclusion took the whole section with it"


@pytest.mark.parametrize("banned", ["source_path", "gps_latitude", "camera_make", "perceptual"])
def test_the_document_carries_nothing_recomputable_from_the_files(banned: str) -> None:
    """Everything here must be a human decision. Anything a rescan can recompute is bulk that
    makes the file bigger, staler and more revealing than it needs to be."""
    assert banned not in json.dumps(to_document(_FULL))


def test_event_membership_is_not_enumerated() -> None:
    """Membership travels as a signature, never as a list of SHA-256s - correctness first, and
    221 KB smaller at full membership as a consequence."""
    document = to_document(_FULL)

    assert document["events"][0]["signature"] == "a" * 64
    assert "members" not in document["events"][0]
