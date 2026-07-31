"""What a user is told after confirming a date, and what must still be true when they close the tab.

**Three states, and the card must distinguish them concretely.** A confirmation changes what the
library believes *immediately*; it does not move the file and it does not touch the bytes. So the
honest report is three sentences with real values in them - *"now dated 4 March 2011"*, *"still
filed under 2014 on disk"*, *"the file itself still says 2014 inside"* - and not the generalised
*"changes apply on the next operation"*, which is true and useless: it tells a user nothing about
which of their photos is where.

**The card must not imply either follow-up has happened.** Someone who confirms a date and closes
the tab should hold an accurate belief about what changed. Both next steps are offered as links
and neither runs; each writes to user files and each already has its own
preview-then-typed-confirm.

**A defect this file found.** ``confirmations_to_bake`` filters on
``file_copies.date_baked_at IS NULL``, and `confirm_date` did not clear it. So: confirm, bake,
then change your mind - the second confirmation was durable in the catalog and **could never
reach the files**, because every copy already looked baked. The invariant is now explicit:
``date_baked_at`` is non-NULL only while the bytes carry the *current* confirmed date.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.date_rescue import confirm_file_date
from truestill_core.catalog import Catalog
from truestill_core.models import DateSource

SHA = "sha-000"
UUID = "DRIVE-1"


def _library(db: Path, *, source: str = DateSource.EXIF.value) -> None:
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=UUID, label="Everyday")
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=SHA,
            copy_sha256=SHA,
            perceptual=None,
            size=10,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative="Camera/2014/a.jpg",
            drive_uuid=UUID,
            date_source=source,
        )


# --- the three states -------------------------------------------------------------------------


def test_the_card_says_what_the_library_now_believes(tmp_path: Path) -> None:
    """State one, and the only one that is true immediately."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    assert result["ok"] is True
    assert "2011-03-04" in result["states"][0]


def test_the_card_says_where_the_file_still_sits(tmp_path: Path) -> None:
    """State two, with the real year - not "its previous location"."""
    db = tmp_path / "c.sqlite"
    _library(db)

    states = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")["states"]

    assert any("2014" in s and "disk" in s.lower() for s in states), states


def test_the_card_says_what_the_file_itself_still_says(tmp_path: Path) -> None:
    """State three: the bytes are untouched, and for an EXIF-dated photo they carry the old date."""
    db = tmp_path / "c.sqlite"
    _library(db, source=DateSource.EXIF.value)

    states = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")["states"]

    assert any("2014" in s and "inside" in s.lower() for s in states), states


def test_a_file_with_no_embedded_date_is_not_said_to_carry_one(tmp_path: Path) -> None:
    """Cry-wolf half. A filename-dated photo has nothing inside it, and claiming it says 2014
    would be a new false statement invented by the screen that exists to stop those."""
    db = tmp_path / "c.sqlite"
    _library(db, source=DateSource.FILENAME.value)

    states = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")["states"]

    inside = next(s for s in states if "inside" in s.lower())
    assert "2014" not in inside, inside
    assert "no date" in inside.lower()


def test_the_card_never_claims_the_file_moved_or_was_rewritten(tmp_path: Path) -> None:
    """The belief a user carries away must be accurate: nothing on disk changed."""
    db = tmp_path / "c.sqlite"
    _library(db)

    joined = " ".join(confirm_file_date(db, sha256=SHA, date_text="2011-03-04")["states"]).lower()

    for lie in ("moved", "renamed", "updated the file", "written into"):
        assert lie not in joined, f"the card implies something that did not happen: {lie!r}"


# --- the next steps ---------------------------------------------------------------------------


def test_both_next_steps_are_offered_and_neither_has_run(tmp_path: Path) -> None:
    """Offered as choices, never performed. Each writes to user files behind its own confirm."""
    db = tmp_path / "c.sqlite"
    _library(db)

    result = confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    actions = {a["action"] for a in result["next_steps"]}
    assert actions == {"bake", "migrate"}
    assert all(not a["done"] for a in result["next_steps"])


def test_confirming_writes_no_file(tmp_path: Path) -> None:
    """The action is catalog-only. The drive is untouched until a user asks for more."""
    db = tmp_path / "c.sqlite"
    _library(db)
    drive = tmp_path / "drive"
    drive.mkdir()
    (drive / "a.jpg").write_bytes(b"original")

    confirm_file_date(db, sha256=SHA, date_text="2011-03-04")

    assert (drive / "a.jpg").read_bytes() == b"original"


# --- the defect this file found ----------------------------------------------------------------


def test_changing_your_mind_after_a_bake_can_still_reach_the_files(tmp_path: Path) -> None:
    """confirm -> bake -> re-confirm must leave the new date bakeable.

    ``confirmations_to_bake`` filters on ``date_baked_at IS NULL``. Without clearing it, the
    second confirmation is durable in the catalog and can never reach the bytes: every copy
    already looks baked, so it is never offered again and the file keeps a date the user has
    explicitly replaced. Silent, and exactly the class of failure O4 was written for.
    """
    db = tmp_path / "c.sqlite"
    _library(db)
    confirm_file_date(db, sha256=SHA, date_text="2011-03-04")
    with Catalog(db) as catalog:
        catalog.record_bake(SHA, UUID, copy_sha256="baked-hash")
        assert catalog.confirmations_to_bake(UUID) == []  # baked: nothing pending

    confirm_file_date(db, sha256=SHA, date_text="1999-12-25")

    with Catalog(db) as catalog:
        pending = [str(r["sha256"]) for r in catalog.confirmations_to_bake(UUID)]
    assert pending == [SHA], "a re-confirmed date could never reach the files"


def test_the_card_admits_the_files_carry_a_previously_confirmed_date(tmp_path: Path) -> None:
    """After a bake, "the file says 2014" is wrong - it says whatever was last baked into it."""
    db = tmp_path / "c.sqlite"
    _library(db)
    confirm_file_date(db, sha256=SHA, date_text="2011-03-04")
    with Catalog(db) as catalog:
        catalog.record_bake(SHA, UUID, copy_sha256="baked-hash")

    states = confirm_file_date(db, sha256=SHA, date_text="1999-12-25")["states"]

    inside = next(s for s in states if "inside" in s.lower())
    assert "2011" in inside, inside
