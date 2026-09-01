"""Album membership must arrive on a catalog that never saw the one that recorded it. `(acg)`

**The defect.** `file_albums` keys ``(file_id, album_id)`` - both rowids, meaningless anywhere else
- and the document carried `albums=tuple({"name": name} for name in catalog.all_album_names())`:
the vocabulary and none of the work. A user moving machines got their album *names* and lost every
photograph in them, silently on every screen and with no way to rebuild it.

🔑 **The fix is `(ack)`'s method, already shipped for trips**: *"Fixed at the gather, because apply
cannot repair what the document discarded [...] No schema change was needed."* Both keys are
already guaranteed unique by the schema - `albums.name` and `files.sha256` - so the rowids stay
local and the document names what they point at.

**The field's answer to this question is that it cannot be done**: PhotoPrism #721 loses albums on
a container rebuild, a 2018 survey of Piwigo/Gallery2/Silvermine found *"no path to create a
portable album using any of those systems"*, and Immich users are advised to prefer tags because
*"if you leave Immich, your album organization is gone"*. Truestill already writes a document to
the drive, so the only thing missing was the keying.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.decisions import (
    Decisions,
    apply_decisions,
    gather_decisions,
    reconcile_documents,
)

PHOTO_A = "a" * 64
PHOTO_B = "b" * 64
NEVER_SEEN = "f" * 64


def _catalog_holding(db: Path, *shas: str) -> Catalog:
    """A catalog that knows ``shas`` as content, with no albums."""
    catalog = Catalog(db)
    for index, sha in enumerate(shas):
        catalog.record_uploaded(
            source_path=f"/src/{index}.jpg",
            original_name=f"{index}.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=10,
            captured_at=None,
            category="Camera",
            relative=f"Camera/{index}.jpg",
            drive_uuid=None,
        )
    return catalog


def test_membership_arrives_on_a_catalog_that_never_saw_the_first(tmp_path: Path) -> None:
    """The round trip, which is the whole entry: gather from A, apply into B."""
    with _catalog_holding(tmp_path / "a.sqlite", PHOTO_A, PHOTO_B) as source:
        source.record_album_members("Wayanad", [PHOTO_A, PHOTO_B])
        document = gather_decisions(source, "")

    assert document.albums == ({"name": "Wayanad", "members": [PHOTO_A, PHOTO_B]},), (
        f"the document did not carry membership: {document.albums}"
    )

    with _catalog_holding(tmp_path / "b.sqlite", PHOTO_A, PHOTO_B) as fresh:
        report = apply_decisions(fresh, document)

        assert fresh.album_members() == {"Wayanad": [PHOTO_A, PHOTO_B]}
        assert report.applied.get("albums") == 1
        assert report.awaiting_content == {}


def test_a_member_this_catalog_does_not_hold_is_counted_and_kept(tmp_path: Path) -> None:
    """⚠ **Nothing is silently dropped**, which is `awaiting_content`'s whole reason to exist:
    *"There IS an action: plug in the drive that holds those photos, scan, re-apply."*"""
    with _catalog_holding(tmp_path / "a.sqlite", PHOTO_A) as source:
        source.record_album_members("Wayanad", [PHOTO_A])
        document = gather_decisions(source, "")

    # The document names two members; this catalog holds one of them.
    document.albums[0]["members"].append(NEVER_SEEN)

    with _catalog_holding(tmp_path / "b.sqlite", PHOTO_A) as fresh:
        report = apply_decisions(fresh, document)

        assert fresh.album_members() == {"Wayanad": [PHOTO_A]}, "the known member must land"
        assert report.awaiting_content == {"albums": 1}, (
            "a member whose content is absent must be counted, not dropped"
        )
    # The document is untouched, so a later scan plus a re-apply lands it.
    assert NEVER_SEEN in document.albums[0]["members"]


def test_location_never_enters_because_an_album_has_no_copies(tmp_path: Path) -> None:
    """🔑 **`(aba)`'s distinction does not reach this case, and that is checked rather than assumed.**

    `file_albums` joins to ``files``, not ``file_copies``. Membership binds a name to *content*, so
    a member with no copy row at all - no drive, nowhere to be - still restores. *"Not at the
    recorded path"* and *"not on this drive"* are both facts about a copy.
    """
    with _catalog_holding(tmp_path / "a.sqlite", PHOTO_A) as source:
        source.record_album_members("Wayanad", [PHOTO_A])
        document = gather_decisions(source, "")

    with _catalog_holding(tmp_path / "b.sqlite", PHOTO_A) as fresh:
        assert fresh.copies_on_drive("no-such-drive") == [], "fixture check: no copy rows anywhere"
        apply_decisions(fresh, document)

        assert fresh.album_members() == {"Wayanad": [PHOTO_A]}


def test_applying_twice_changes_nothing(tmp_path: Path) -> None:
    """Idempotence: `apply_decisions` reports what changed, not what it was offered."""
    with _catalog_holding(tmp_path / "a.sqlite", PHOTO_A) as source:
        source.record_album_members("Wayanad", [PHOTO_A])
        document = gather_decisions(source, "")

    with _catalog_holding(tmp_path / "b.sqlite", PHOTO_A) as fresh:
        first = apply_decisions(fresh, document)
        second = apply_decisions(fresh, document)

        assert first.applied.get("albums") == 1
        assert "albums" not in second.applied, "a second restore reported work it did not do"


def test_two_drives_holding_different_members_are_unioned() -> None:
    """⚠ **UNION, NOT FIRST-WINS, and this is the test that pins it.**

    Two drives routinely hold different partial views of one album, because each was written by
    the ingest that ran there. `_merge_section`'s first-wins is right for a trip's days - one
    authority answers for them - and would silently drop every member the other drive knew about,
    which is `(acg)`'s own harm one layer up.

    Union is safe **because membership is append-only**: `grep -rn file_albums packages/*/src`
    finds two writers, both ``INSERT OR IGNORE``, and no ``DELETE``. There is no removal for a
    union to resurrect.
    """
    one = Decisions(
        written="2026-08-01T00:00:00+00:00",
        drive_uuid="u1",
        albums=({"name": "Wayanad", "members": [PHOTO_A]},),
    )
    two = Decisions(
        written="2026-08-02T00:00:00+00:00",
        drive_uuid="u2",
        albums=({"name": "Wayanad", "members": [PHOTO_B]},),
    )

    merged, _report = reconcile_documents([one, two])

    assert merged.albums == ({"name": "Wayanad", "members": [PHOTO_A, PHOTO_B]},), (
        f"a partial view from one drive was discarded: {merged.albums}"
    )
