"""The app's half of the free tier: a refused run, and a destination that was never touched.

⚠ **ASSERTED ON THE DISK, NEVER ON THE CALL.** D16 §4 rules that a run over the cap is refused
before it starts and never stopped part-way, because half an organize run is the worst state this
product can leave a library in. A version that copied two files and then raised would satisfy
`pytest.raises` perfectly, so every test here looks at the destination afterwards.

The app's refusal travels as an exception, which is the channel `DestinationError` already uses
for the other refusal that happens after planning and before anything moves - the job runner turns
it into a terminal error frame carrying core's own sentence and the class name.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import nacl.signing
import pytest
from PIL import Image
from truestill_app.service.organize import organize_preview_run, organize_run
from truestill_core import allowance, licence
from truestill_core.licence_notice import RunNotAllowedError

KID = "app-cap-throwaway"


def _photo(path: Path, seed: int) -> None:
    image = Image.new("RGB", (48, 48))
    pixels = image.load()
    assert pixels is not None
    for x in range(48):
        for y in range(48):
            pixels[x, y] = ((x * 5 + seed * 40) % 256, (y * 5) % 256, (x + y + seed) % 256)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, Path]:
    source, destination = tmp_path / "src", tmp_path / "dest"
    destination.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        _photo(source / f"{index}.jpg", seed=index)
    return source, destination, tmp_path / "catalog.sqlite"


def run(source: Path, destination: Path, db: Path) -> object:
    """The real job target, driven the way a route drives it."""
    return organize_run(source, destination, db)(lambda _p: None, threading.Event())


def photographs_in(destination: Path) -> list[Path]:
    """Everything but the two dotfiles a run writes on a drive."""
    return [
        path for path in destination.rglob("*") if path.is_file() and not path.name.startswith(".")
    ]


def test_a_run_over_the_allowance_raises_and_the_destination_is_untouched(
    library: tuple[Path, Path, Path],
) -> None:
    """**The ruling, on the disk.** Nothing copied, and the exception carries core's sentence.

    `photographs_in` is asserted empty rather than `len(...) < 3`: "fewer than it planned" is what
    a run stopped part-way also looks like, and those are the two outcomes this test exists to
    tell apart.
    """
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE)

    with pytest.raises(RunNotAllowedError) as refused:
        run(source, destination, db)

    assert photographs_in(destination) == []
    assert "free allowance" in str(refused.value)
    assert allowance.RUN_DID_NOT_START in str(refused.value)


def test_the_refusal_leaves_no_drive_marker_and_no_catalog_row(
    library: tuple[Path, Path, Path],
) -> None:
    """⚠ **Refused BEFORE the destination is registered**, which is the half a "nothing copied"
    assertion misses.

    The check sits above `_register_destination` and `_open_organize_run` on purpose. A refusal
    placed below either would leave a drive identity minted for a run that never happened and an
    open run row the rebuild guard would later read - paperwork for work that was refused.
    """
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE)

    with pytest.raises(RunNotAllowedError):
        run(source, destination, db)

    assert not (destination / ".truestill-drive.json").exists()
    # ⚠ Counted as ROWS, not searched as a string. The first version grepped the database file
    # for "organize_runs" and failed on a clean refusal, because that is the TABLE NAME and the
    # schema carries it from the moment the catalog is created - an assertion that could only
    # ever have passed if the catalog did not exist.
    with closing(sqlite3.connect(db)) as connection:
        open_runs = connection.execute("SELECT count(*) FROM organize_runs").fetchone()[0]
    assert open_runs == 0


def test_a_permitted_run_organizes_and_charges_what_it_wrote(
    library: tuple[Path, Path, Path],
) -> None:
    """The ordinary path, and the anti-vacuity half of every refusal above.

    Without it, a service that raised `RunNotAllowedError` unconditionally would satisfy both
    tests above and organize nothing, ever.
    """
    source, destination, db = library

    run(source, destination, db)

    assert len(photographs_in(destination)) == 3
    assert allowance.files_written() == 3


def test_the_preview_is_complete_and_silent_about_the_cap(
    library: tuple[Path, Path, Path],
) -> None:
    """⚠ **D16 §5: the preview never consults the allowance.**

    A preview over an exhausted allowance must still produce its whole summary, because a number
    that moves as a user types is the countdown D6 §3 forbids. This drives the real preview job
    with the allowance fully spent and asserts it answers normally - and that it charges nothing,
    because a preview writes no files.
    """
    source, _destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE * 10)

    summary = organize_preview_run(source, _destination, db)(lambda _p: None, threading.Event())

    assert isinstance(summary, dict)
    assert summary["will_organize"] == 3
    assert allowance.files_written() == allowance.FREE_FILE_ALLOWANCE * 10


def test_a_run_that_fits_exactly_starts_and_leaves_the_allowance_spent(
    library: tuple[Path, Path, Path],
) -> None:
    """The boundary on this surface too: exactly what remains must start and must finish.

    The allowance is what may be written, not what may be approached - a `<` where `<=` belongs
    would refuse this run and make the advertised number a lie by one.
    """
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE - 3)

    run(source, destination, db)

    assert len(photographs_in(destination)) == 3
    assert allowance.files_written() == allowance.FREE_FILE_ALLOWANCE
    assert allowance.remaining_for(licence.LicenceState.ABSENT, allowance.files_written()) == 0


def test_one_file_over_the_boundary_refuses_on_this_surface_too(
    library: tuple[Path, Path, Path],
) -> None:
    """Paired with the test above: either alone is satisfied by a comparison wrong by one in the
    direction that test does not look."""
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE - 2)

    with pytest.raises(RunNotAllowedError):
        run(source, destination, db)

    assert photographs_in(destination) == []


def test_a_cancelled_run_is_charged_for_what_it_had_already_filed(
    library: tuple[Path, Path, Path],
) -> None:
    """⚠ **Cancellation is charged for what landed, and that is the honest answer.**

    `execute` returns the results it managed when `cancel` is set, so a run stopped halfway by the
    user has really put those photographs in the library. Forgiving them would make the cap
    avoidable by pressing Stop; charging for the whole plan would bill for files that were never
    written. The count is asserted to equal what is actually on the disk, which is the only
    definition that stays true.
    """
    source, destination, db = library
    cancel = threading.Event()

    def stop_after_the_first(progress: object) -> None:
        done = getattr(progress, "done", 0)
        if done >= 1:
            cancel.set()

    organize_run(source, destination, db)(stop_after_the_first, cancel)

    written = len(photographs_in(destination))
    assert allowance.files_written() == written
    assert written < 3, "the run was not actually cancelled, so this proves nothing"


def _install_licence(monkeypatch: pytest.MonkeyPatch, covers_through: int) -> None:
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
        "covers_through": covers_through,
        "issued_at": "2026-09-11",
        "updates_until": "2027-09-11",
    }
    encoded = licence.encode_payload(fields)
    licence.write_licence(
        f"{encoded}.{licence.b64url_encode(signer.sign(licence.signing_input(encoded)).signature)}"
    )


@pytest.fixture
def entitled(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ACTIVE licence: bought, and covering this build."""
    _install_licence(monkeypatch, licence.BUILD_EPOCH)


@pytest.fixture
def lapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A LAPSED licence: bought, and no longer entitled to NEW versions."""
    _install_licence(monkeypatch, licence.BUILD_EPOCH - 1)


def test_an_entitled_run_is_never_refused(
    library: tuple[Path, Path, Path],
    entitled: None,  # noqa: ARG001 - a fixture used for its effect: it installs the licence
) -> None:
    """A paid licence lifts the cap, through a real run rather than through `may_start`.

    The counter is left far past the free allowance deliberately: an entitled run must not consult
    it, and a version that read the number before the licence would refuse a paying customer.
    """
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE * 5)

    run(source, destination, db)

    assert len(photographs_in(destination)) == 3


def test_a_lapsed_licence_organizes_past_the_free_allowance(
    library: tuple[Path, Path, Path],
    lapsed: None,  # noqa: ARG001 - a fixture used for its effect: it installs the licence
) -> None:
    """⚠ **D16 §2 THROUGH A REAL RUN, and a mutation proved nothing else reached it.**

    "A lapsed licence loses nothing it bought" is the ruling most likely to be broken by someone
    tidying `remaining_for`, and making LAPSED capped SURVIVED every end-to-end test in this
    commit - because all of them installed an ACTIVE licence. The unit test on `remaining_for`
    caught it; nothing proved the whole chain honoured it.

    So this run is at the free allowance and has a lapsed licence, and it must organize anyway. A
    version that demoted lapsed customers to the free tier would refuse exactly this, and the
    person it refuses has paid.
    """
    source, destination, db = library
    allowance.record_files_written(allowance.FREE_FILE_ALLOWANCE)

    run(source, destination, db)

    assert len(photographs_in(destination)) == 3
    assert licence.read_licence().state is licence.LicenceState.LAPSED
