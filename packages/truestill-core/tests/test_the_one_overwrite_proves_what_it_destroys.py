"""`_free_relative`'s reclaimable bypass is the one branch that may destroy bytes. `(alc)`

Everything else in this product suffixes around an occupied name - *"never lose data"*. This one
branch overwrites, and until now its entire authorisation was `relative == reclaimable`: a string
comparison against a catalog row.

**What the row proves and what it does not.** `copy_row` is keyed by content, so a row means *we
once wrote this content at that path on this drive*. It does **not** mean the bytes there now are
ours - a user who replaced an organized photograph with their own edit leaves the row untouched,
and `dedup.credible_copies` (size-only, and it says so) then sends us straight here.

⚠ **CONTENT CANNOT PROVE OWNERSHIP, AND THE INVERSE TEST IS THE ONE THAT WORKS.** Asking *"do the
bytes match the record?"* can never authorise this branch: it fires only when the copy is **not**
credible, so the bytes are presumed wrong, and a test requiring them to match would never fire at
all. What a hash of a wrong file **can** settle is whether destroying it destroys a photograph the
catalog knows. That is a refusal, not a permission.

**No filesystem is needed for the case half.** `_free_relative` takes plain strings and a flag, so
the folding and non-folding branches both run on every lane with no `skipif` - `(ala)`'s seam,
reused.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from truestill_core.catalog import Catalog
from truestill_core.destinations.base import Destination
from truestill_core.destinations.local import LocalDestination
from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
    RuleName,
)
from truestill_core.organizer import (
    OVERWRITE_DECLINED,
    IngestContext,
    _destination_folds_case,
    _free_relative,
    _MetadataBaker,
    _occupant_sha,
    _reclaimable_target,
    _WriteRun,
)

RECORDED = "Saved/2013/Photo.JPG"
DRIFTED = "Saved/2013/photo.jpg"


# ------------------------------------------------------------------- the case half, both ways


def test_a_case_drift_still_finds_the_path_it_may_repair() -> None:
    """The headline for the fold. On NTFS and APFS these two spellings are one file.

    Without it the bypass misses, `exists` answers True, and the repair lands beside the corpse
    as `…_1.jpg` - `(ain)`'s measured shape, nine files from three photographs.
    """
    # ⚠ **The drifted name must be OCCUPIED, or the test cannot tell the branches apart.** With
    # an empty destination `exists` is False and the ordinary path also returns `(relative,
    # False)` - the first draft did that and a mutation reverting the fold survived it.
    final, renamed = _free_relative(
        _Destination(occupied=(DRIFTED,)), DRIFTED, reclaimable=RECORDED, fold_case=True
    )

    assert final == DRIFTED
    assert not renamed


def test_the_same_drift_is_two_files_where_the_filesystem_says_so() -> None:
    """⚠ **The half that makes folding safe to do at all.**

    On ext4 `Photo.JPG` and `photo.jpg` are two genuinely different files. Folding here would
    authorise overwriting **the wrong one** - which is why `(ala)` chose to ask the mount rather
    than fold everywhere, and why this branch inherits that choice rather than making its own.
    """
    final, renamed = _free_relative(
        _Destination(occupied=(DRIFTED,)), DRIFTED, reclaimable=RECORDED, fold_case=False
    )

    assert final != DRIFTED
    assert renamed


def test_an_exact_match_is_unaffected_by_the_flag() -> None:
    """The overwhelmingly common shape: the render and the record agree. Neither flag changes it."""
    for fold in (True, False):
        assert _free_relative(
            _Destination(occupied=(RECORDED,)), RECORDED, reclaimable=RECORDED, fold_case=fold
        ) == (RECORDED, False)


def test_a_different_photograph_at_the_same_name_is_still_suffixed() -> None:
    """The rule this branch is an exception to, asserted so the exception cannot swallow it."""
    final, renamed = _free_relative(
        _Destination(occupied=(RECORDED,)), RECORDED, reclaimable="Saved/2013/Other.JPG"
    )

    assert final == "Saved/2013/Photo_1.JPG"
    assert renamed


# ------------------------------------------------------------ the read that decides ownership


def test_an_empty_file_is_never_read() -> None:
    """⚠ **Zero bytes is not a photograph, and skipping the read is what keeps this free.**

    It is the commonest shape an interrupted write leaves - `(aja)` measured 836 of them - and
    overwriting zero bytes destroys nothing. A version that hashed them would pay a read per
    damaged file for an answer that is decided by the size it already has.
    """
    destination = _Destination(occupied=(RECORDED,), sizes={RECORDED: 0})

    assert _occupant_sha(destination, RECORDED) is None
    assert destination.checksums == [], "an empty file was read"


def test_a_file_with_bytes_is_read(tmp_path: Path) -> None:
    """The other direction, against a real `LocalDestination` rather than a stub."""
    (tmp_path / "Saved" / "2013").mkdir(parents=True)
    (tmp_path / RECORDED).write_bytes(b"\xff\xd8\xff\xe0 not empty")

    assert _occupant_sha(LocalDestination(tmp_path), RECORDED) is not None


def test_an_unreadable_occupant_reads_as_nothing_worth_keeping(tmp_path: Path) -> None:
    """A path we recorded, that cannot be read, is the corpse this branch exists to replace.

    `DestinationError` is caught rather than propagated: one unreadable file must not stop a run,
    and the honest reading of "our own recorded path holds something we cannot even open" is that
    there is nothing there to protect.
    """
    assert _occupant_sha(LocalDestination(tmp_path), "Saved/2013/absent.jpg") is None


# ----------------------------------------------------------------------------- the probe, once


def test_a_destination_with_no_local_root_never_folds() -> None:
    """⚠ **An rclone remote cannot be stat'd, and a guess could only authorise an overwrite.**

    The same stand-down `local_root`'s own docstring describes, applied to the one decision where
    being wrong is destructive rather than merely slow.
    """
    assert _destination_folds_case(_Destination(occupied=())) is False


def test_the_probe_agrees_with_the_filesystem_under_it(tmp_path: Path) -> None:
    """Derived from what the filesystem says, so it is correct on every lane.

    A `skipif` by platform would run nowhere in CI and prove nothing; this runs everywhere and
    exercises the folding branch for real on a macOS or Windows runner.
    """
    (tmp_path / "Photo.JPG").write_bytes(b"x")

    assert _destination_folds_case(LocalDestination(tmp_path)) is (tmp_path / "photo.jpg").exists()


def test_an_empty_destination_answers_no_rather_than_guessing(tmp_path: Path) -> None:
    """A first organize has nothing to probe and nothing to collide with. `False` is right."""
    assert _destination_folds_case(LocalDestination(tmp_path)) is False


def test_the_declined_sentence_names_the_file_it_kept() -> None:
    """A note a user can act on, not an apology. `(aja)`: *"Every automatic path reports success."*"""
    said = OVERWRITE_DECLINED.format(path=RECORDED)

    assert RECORDED in said
    assert "did not overwrite" in said


class _Destination:
    """The smallest thing `_free_relative` and `_occupant_sha` need, with a read counter."""

    def __init__(
        self,
        *,
        occupied: tuple[str, ...],
        sizes: dict[str, int] | None = None,
        sha: str = "c" * 64,
    ) -> None:
        self._occupied = set(occupied)
        self._sizes = sizes
        self._sha = sha
        self.checksums: list[str] = []

    def exists(self, relative_path: str) -> bool:
        return relative_path in self._occupied

    def sizes(self) -> dict[str, int] | None:
        return self._sizes

    def checksum(self, relative_path: str) -> str:
        self.checksums.append(relative_path)
        return self._sha

    def local_root(self) -> Path | None:
        return None


# ------------------------------------------- the three outcomes, decided where the catalog is


def _run(catalog: Catalog, destination: object, *, fold_case: bool = False) -> _WriteRun:
    """A `_WriteRun` carrying only what `_reclaimable_target` reads."""
    return _WriteRun(
        destination=cast("Destination", destination),
        catalog=catalog,
        set_timestamps=False,
        move=False,
        relocation=None,
        by_source={},
        ingest=IngestContext(),
        albums_by_sha={},
        baker=_MetadataBaker([]),
        drive_uuid="drive-1",
        fold_case=fold_case,
    )


def _resolution(sha: str) -> Resolution:
    decision = Decision(
        source=Path("holiday.jpg"),
        category=CategoryMatch(
            label="Saved", confidence=Confidence.LOW, rule=RuleName.FALLBACK, reason="-"
        ),
        captured_at=None,
        date_source=DateSource.NONE,
        date_tag=None,
        relative=Path(RECORDED),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


OURS = "a" * 64
THEIRS = "b" * 64
STRANGER = "c" * 64


def test_an_intact_copy_is_not_rewritten(tmp_path: Path) -> None:
    """⚠ **Reachable only through a bug one layer up, and a mutation proved the e2e test blind.**

    `credible_copies` compares sizes **by path** (`(alb)` item 9), so on a folding filesystem a
    case drift makes a perfectly good copy look incredible and dedup sends us here with nothing
    to repair. On ext4 that cannot be staged end to end - so it is asserted at the function that
    decides, where the inputs can be stated directly.
    """
    with Catalog(tmp_path / "c.db") as catalog:
        catalog.record_copy(
            sha256=OURS, drive_uuid="drive-1", relative=RECORDED, copy_sha256=OURS, size=10
        )
        destination = _Destination(occupied=(RECORDED,), sizes={RECORDED: 10}, sha=OURS)

        target, note = _reclaimable_target(_run(catalog, destination), _resolution(OURS), RECORDED)

    assert target is None, "an intact copy was offered up to be overwritten"
    assert note is None, "nothing was declined; there was nothing to decline"


def test_a_photograph_the_catalog_knows_is_declined(tmp_path: Path) -> None:
    """The refusal. Content cannot prove the file is ours; it can prove destroying it is a loss."""
    with Catalog(tmp_path / "c.db") as catalog:
        catalog.record_copy(
            sha256=OURS, drive_uuid="drive-1", relative=RECORDED, copy_sha256=OURS, size=10
        )
        catalog.record_copy(
            sha256=THEIRS,
            drive_uuid="drive-1",
            relative="Saved/2013/Beach.JPG",
            copy_sha256=THEIRS,
            size=20,
        )
        destination = _Destination(occupied=(RECORDED,), sizes={RECORDED: 20}, sha=THEIRS)

        target, note = _reclaimable_target(_run(catalog, destination), _resolution(OURS), RECORDED)

    assert target is None
    assert note is not None
    assert RECORDED in note


def test_a_corpse_is_offered_for_repair(tmp_path: Path) -> None:
    """The branch `(aja)` built. Bytes nothing accounts for, at our own recorded path."""
    with Catalog(tmp_path / "c.db") as catalog:
        catalog.record_copy(
            sha256=OURS, drive_uuid="drive-1", relative=RECORDED, copy_sha256=OURS, size=10
        )
        destination = _Destination(occupied=(RECORDED,), sizes={RECORDED: 3}, sha=STRANGER)

        target, note = _reclaimable_target(_run(catalog, destination), _resolution(OURS), RECORDED)

    assert target == RECORDED
    assert note is None


def test_a_baked_copy_is_not_mistaken_for_a_stranger(tmp_path: Path) -> None:
    """⚠ **`copy_sha256`, not `sha256`, and this is why `content_is_accounted_for` reads both.**

    A Takeout bake rewrites the file, so what a drive holds differs from what arrived - by
    design. Asking only `files.sha256` would call a baked photograph unknown, and this branch
    reads unknown as *"safe to destroy"*.
    """
    baked = "d" * 64
    with Catalog(tmp_path / "c.db") as catalog:
        catalog.record_copy(
            sha256=OURS, drive_uuid="drive-1", relative=RECORDED, copy_sha256=OURS, size=10
        )
        # Another photograph whose copy was baked: its bytes on the drive are `baked`, and the
        # `files` table has never seen that hash.
        catalog.record_copy(
            sha256=THEIRS,
            drive_uuid="drive-1",
            relative="Saved/2013/Baked.JPG",
            copy_sha256=baked,
            size=20,
        )
        destination = _Destination(occupied=(RECORDED,), sizes={RECORDED: 20}, sha=baked)

        target, note = _reclaimable_target(_run(catalog, destination), _resolution(OURS), RECORDED)

    assert target is None, "a baked photograph was treated as a stranger and overwritten"
    assert note is not None
