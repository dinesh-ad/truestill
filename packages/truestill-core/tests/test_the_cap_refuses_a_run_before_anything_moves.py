"""The free tier, joined up: a real CLI run refused, and the counter charged for what landed.

⚠ **EVERYTHING FOR THIS EXISTED AND NOTHING WAS JOINED.** `may_start` decided, `files_written`
counted, `notice_for` worded it, and the organize run called none of them - so the free tier was a
design rather than a behaviour. These tests drive `truestill organize --apply` end to end,
against real files on disk, and assert on the destination rather than on a return value.

**Why the CLI and not a unit of the check**: a unit test of `_allowance_refusal` would pass on a
pipeline that never calls it, which is precisely the state this commit found. The refusal is only
real if a run that should not start does not start, and the only way to know that is to look at
the destination afterwards.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import nacl.signing
import pytest
from truestill_cli.cli import ALLOWANCE_EXHAUSTED_EXIT, main
from truestill_core import allowance, licence
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)


def _result(status: ActionStatus) -> ActionResult:
    """One result carrying nothing but its status - the only field the count reads."""
    decision = Decision(
        source=Path("/src/a.jpg"),
        category=CategoryMatch(
            label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
        ),
        captured_at=datetime(2014, 1, 5, 18, 12),
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path("Camera/2014/01/a.jpg"),
    )
    resolution = Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )
    return ActionResult(resolution, status, None)


KID = "cap-throwaway"


@pytest.fixture
def library(tmp_path: Path, gradient_png: Path, gradient_jpeg_recompressed: Path) -> Path:
    """A source of three distinguishable photographs, and an empty destination beside it."""
    source = tmp_path / "source"
    source.mkdir()
    for index, original in enumerate((gradient_png, gradient_jpeg_recompressed, gradient_png)):
        target = source / f"photo-{index}{original.suffix}"
        target.write_bytes(original.read_bytes())
        # A distinct tail so the three are not exact duplicates of one another, which would make
        # `will_organize` 1 and the boundary tests meaningless.
        with target.open("ab") as handle:
            handle.write(b"\x00" * (index + 1))
    return source


def organize(source: Path, destination: Path, db: Path, *extra: str) -> int:
    """`truestill organize SOURCE DESTINATION`, exactly as a person types it."""
    return main(["organize", str(source), str(destination), "--db", str(db), *extra])


def files_under(destination: Path) -> list[Path]:
    """The PHOTOGRAPHS in the destination, which is what the cap counts.

    ⚠ **Dotfiles are excluded and that is not cosmetic.** A run also writes
    `.truestill-drive.json` and `.truestill-decisions.json`, so a naive count reads 5 where the
    run organized 3 - which would have made the boundary tests below assert the wrong number in
    the direction that hides an off-by-two.
    """
    return [
        path for path in destination.rglob("*") if path.is_file() and not path.name.startswith(".")
    ]


def spend(used: int) -> None:
    """Put the installation `used` files into its free allowance."""
    allowance.record_files_written(used)


# --- the refusal --------------------------------------------------------------------------------


def test_a_run_over_the_allowance_refuses_and_the_destination_stays_empty(
    library: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The ruling, asserted where it matters: on the disk.**

    D16 §4 - the run is refused BEFORE it starts, never stopped part-way, because half an
    organize run is the worst state this product can leave a library in. So the assertion is that
    the destination is **untouched**, not that a call returned a number. A pipeline that moved two
    files and then refused would satisfy an exit-code check perfectly.
    """
    destination = tmp_path / "library"
    spend(allowance.FREE_FILE_ALLOWANCE)

    code = organize(library, destination, tmp_path / "catalog.sqlite", "--apply")

    assert code == ALLOWANCE_EXHAUSTED_EXIT
    assert not destination.exists() or files_under(destination) == []
    refusal = capsys.readouterr().err
    assert "free allowance" in refusal
    assert allowance.RUN_DID_NOT_START in refusal


def test_the_refusal_charges_nothing_for_the_run_it_refused(library: Path, tmp_path: Path) -> None:
    """A refused run wrote no files, so it must cost no allowance.

    Without this, a user at the cap who tried twice would be charged twice for nothing - and the
    counter would drift away from what the library actually holds, which is the one thing it is
    supposed to track.
    """
    spend(allowance.FREE_FILE_ALLOWANCE)

    organize(library, tmp_path / "library", tmp_path / "catalog.sqlite", "--apply")

    assert allowance.files_written() == allowance.FREE_FILE_ALLOWANCE


def test_a_preview_is_never_refused_however_far_over_the_allowance_it_is(
    library: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ **D16 §5: the preview stays complete and silent about the cap.**

    A number that moves as a user types is the countdown D6 §3 forbids by name. A dry run over an
    exhausted allowance must therefore print its whole report and exit as it always did - and must
    say nothing about a licence, which is the half that would otherwise creep back in as a
    "helpful" warning.
    """
    spend(allowance.FREE_FILE_ALLOWANCE * 10)

    code = organize(library, tmp_path / "library", tmp_path / "catalog.sqlite")

    assert code != ALLOWANCE_EXHAUSTED_EXIT
    printed = capsys.readouterr()
    assert "allowance" not in (printed.out + printed.err).lower()


def test_a_preview_does_not_touch_the_counter(library: Path, tmp_path: Path) -> None:
    """A dry run writes no files, so it charges nothing - and does not create the counter file
    either. The second half matters: a preview that created an empty counter would make "has this
    installation ever organized anything" answerable wrongly."""
    organize(library, tmp_path / "library", tmp_path / "catalog.sqlite")

    assert allowance.files_written() == 0


# --- the boundary -------------------------------------------------------------------------------


def test_a_run_that_fits_exactly_starts_and_spends_the_allowance_to_the_last_file(
    library: Path, tmp_path: Path
) -> None:
    """**Exactly at the boundary, which is the case a `<` instead of `<=` gets wrong.**

    The allowance is what may be written, not what may be approached. A run of exactly what
    remains must start, must finish, and must leave the allowance at zero - not at one, and not
    refused. Asserted on all three: the files landed, the counter is spent, and nothing remains.
    """
    destination = tmp_path / "library"
    organized = 3
    spend(allowance.FREE_FILE_ALLOWANCE - organized)

    code = organize(library, destination, tmp_path / "catalog.sqlite", "--apply")

    assert code == 0
    assert len(files_under(destination)) == organized, files_under(destination)
    assert allowance.files_written() == allowance.FREE_FILE_ALLOWANCE
    assert allowance.remaining_for(licence.LicenceState.ABSENT, allowance.files_written()) == 0


def test_one_file_over_the_boundary_refuses(library: Path, tmp_path: Path) -> None:
    """The other side of the same line, one file away.

    Paired with the test above deliberately: either alone is satisfied by a comparison that is
    wrong by one in the direction that test does not look.
    """
    destination = tmp_path / "library"
    spend(allowance.FREE_FILE_ALLOWANCE - 2)

    code = organize(library, destination, tmp_path / "catalog.sqlite", "--apply")

    assert code == ALLOWANCE_EXHAUSTED_EXIT
    assert not destination.exists() or files_under(destination) == []


# --- the counting -------------------------------------------------------------------------------


def test_a_run_charges_for_the_files_it_wrote(library: Path, tmp_path: Path) -> None:
    """The ordinary case: three photographs in, three files charged, counted afterwards."""
    organize(library, tmp_path / "library", tmp_path / "catalog.sqlite", "--apply")

    assert allowance.files_written() == 3


def test_a_second_run_over_the_same_source_charges_nothing_more(
    library: Path, tmp_path: Path
) -> None:
    """⚠ **Re-running is how people recover from a partial run, and it must not cost twice.**

    The second pass finds every file already in the library, so every result is `DUPLICATE` -
    which `FILES_WRITTEN_STATUSES` does not count. A cap that charged for duplicates would punish
    the ordinary recovery path and drift away from what the library holds.
    """
    destination = tmp_path / "library"
    db = tmp_path / "catalog.sqlite"
    organize(library, destination, db, "--apply")
    after_first = allowance.files_written()

    organize(library, destination, db, "--apply")

    assert after_first == 3
    assert allowance.files_written() == 3


@pytest.mark.parametrize(
    ("status", "charged"),
    [
        (ActionStatus.UPLOADED, True),
        (ActionStatus.RENAMED, True),
        (ActionStatus.MOVED, True),
        (ActionStatus.MOVE_KEPT, True),
        (ActionStatus.MOVED_IN_PLACE, True),
        (ActionStatus.ALREADY_PLACED, False),
        (ActionStatus.DUPLICATE, False),
        (ActionStatus.SKIPPED_UNDATED, False),
        (ActionStatus.FAILED, False),
        (ActionStatus.PLANNED, False),
    ],
)
def test_every_status_is_decided_one_way_or_the_other(status: ActionStatus, charged: bool) -> None:
    """**The census: no outcome falls through into an answer nobody chose.**

    ⚠ `MOVED_IN_PLACE` is charged and `ALREADY_PLACED` is not, which is the pair a reader will
    assume wrong. A rename files a photograph and costs allowance; an in-place re-run over a file
    already at its target does nothing at all and must not. That asymmetry is also what makes
    this set different from `organizer._BYTES_WRITTEN_STATUSES`, which answers "did bytes reach a
    disk" and excludes both.
    """
    assert allowance.files_written_by([_result(status)]) == (1 if charged else 0)


def test_the_status_census_covers_the_whole_enum() -> None:
    """Anti-vacuity for the table above: a status added later must not be silently uncharged.

    The parametrised test asserts each status it names; a new one would simply not appear, and
    the default - uncounted - would be a decision nobody made.
    """
    named = {
        ActionStatus.UPLOADED,
        ActionStatus.RENAMED,
        ActionStatus.MOVED,
        ActionStatus.MOVE_KEPT,
        ActionStatus.MOVED_IN_PLACE,
        ActionStatus.ALREADY_PLACED,
        ActionStatus.DUPLICATE,
        ActionStatus.SKIPPED_UNDATED,
        ActionStatus.FAILED,
        ActionStatus.PLANNED,
    }

    assert named == set(ActionStatus)


# --- a licence lifts the cap ---------------------------------------------------------------------


@pytest.fixture
def entitled(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ACTIVE licence installed on this installation, signed by a throwaway key."""
    signer = nacl.signing.SigningKey.generate()
    monkeypatch.setitem(licence.PUBLIC_KEYS, KID, licence.b64url_encode(bytes(signer.verify_key)))
    fields: dict[str, object] = {
        "v": licence.PAYLOAD_VERSION,
        "kid": KID,
        "sub": "a",
        "lic": "l",
        "name": "A Buyer",
        "email": "b@example.com",
        "edition": "pro",
        "covers_through": licence.BUILD_EPOCH,
        "issued_at": "2026-09-11",
        "updates_until": "2027-09-11",
    }
    encoded = licence.encode_payload(fields)
    licence.write_licence(
        f"{encoded}.{licence.b64url_encode(signer.sign(licence.signing_input(encoded)).signature)}"
    )


def test_an_entitled_run_is_never_refused_however_much_it_has_written(
    library: Path,
    tmp_path: Path,
    entitled: None,  # noqa: ARG001 - a fixture used for its effect: it installs the licence
) -> None:
    """A paid licence lifts the cap, asserted through a real run rather than through `may_start`.

    The counter is deliberately left far past the free allowance: an entitled run must not consult
    it at all, and a version that checked the number before the licence would refuse a customer
    who had paid.
    """
    destination = tmp_path / "library"
    spend(allowance.FREE_FILE_ALLOWANCE * 5)

    code = organize(library, destination, tmp_path / "catalog.sqlite", "--apply")

    assert code == 0
    assert len(files_under(destination)) == 3
