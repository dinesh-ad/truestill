"""Where the library lives is DECLARED, not inferred from a run that already happened. `(abx)`.

`path_hint.library` is written *after* a successful organize (`organize.py`), and read through
`take_live_path_hint`, whose own docstring says a hint "is never identity - only a convenience".
So until now the library's location was whatever the user happened to type into a field once, and
the first run was the run that decided.

`library.root` is the counterpart: a stated intent. The distinction is the whole design, and the
first test below is what holds it up.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image
from starlette.testclient import TestClient
from truestill_app import service
from truestill_app.service.drives import LIBRARY_PATH_HINT, LIBRARY_ROOT_KEY
from truestill_core.catalog import Catalog


def _seed_file(db: Path) -> None:
    """One organized file, so the catalog is no longer empty."""
    with Catalog(db) as catalog:
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256="a" * 64,
            copy_sha256="a" * 64,
            perceptual=None,
            size=10,
            captured_at=None,
            category="Camera",
            relative="Camera/a.jpg",
        )


def test_the_declared_root_survives_its_path_becoming_unreachable(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    """**THE LOAD-BEARING TEST. Do not weaken it.**

    A declaration must outlive its path being temporarily gone - an external library drive is
    unplugged, a mount is not up yet. The observed hint beside it is *cleared* in exactly that
    case, by design (`take_live_path_hint`), and if the declaration were stored the same way then
    **first run would re-arm on every unplugged drive** - which is the defect `(abx)` is about,
    rearmed rather than fixed.

    The two are asserted together, on one vanished path, because the contrast IS the design: one
    forgets, the other does not.
    """
    gone = tmp_path / "external-library"
    gone.mkdir()
    with Catalog(db_path) as catalog:
        catalog.set_setting(LIBRARY_ROOT_KEY, str(gone))
        catalog.set_setting(LIBRARY_PATH_HINT, str(gone))
    gone.rmdir()  # the drive is unplugged

    status = client.get("/api/library/status").json()

    assert status["library_root"] == str(gone), "the declaration was forgotten when its path went"
    assert status["library_path"] is None, "the observed hint should be cleared - it is not"


def test_a_first_run_is_asked_where_the_library_should_live(client: TestClient) -> None:
    """No declaration and no files: the one state where the question has not been answered."""
    status = client.get("/api/library/status").json()
    assert status["library_root"] is None
    assert status["needs_library_root"] is True


def test_a_library_that_already_holds_files_is_never_asked(
    client: TestClient, db_path: Path
) -> None:
    """**CRY-WOLF HALF, first way.** A user who organized before this shipped has no declaration
    and must never be re-asked: they answered the question by doing it, and the hint records where.
    """
    _seed_file(db_path)
    status = client.get("/api/library/status").json()
    assert status["library_root"] is None, "the fixture is not the shape this test assumes"
    assert status["files"] == 1
    assert status["needs_library_root"] is False


def test_a_declared_root_whose_path_is_gone_is_still_not_re_asked(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    """**CRY-WOLF HALF, second way**, and the one the gate is really for.

    Declared, but the drive is unplugged and the catalog is empty - so `files == 0` alone would
    fire. The gate is *no declaration AND no files*, and this is the case that separates the two.
    """
    gone = tmp_path / "external-library"
    gone.mkdir()
    with Catalog(db_path) as catalog:
        catalog.set_setting(LIBRARY_ROOT_KEY, str(gone))
    gone.rmdir()

    status = client.get("/api/library/status").json()
    assert status["files"] == 0, "the fixture must be empty or this proves nothing"
    assert status["library_root"] == str(gone)
    assert status["needs_library_root"] is False


def test_declaring_a_root_records_it_and_ends_the_question(client: TestClient) -> None:
    """The endpoint the first-run card posts to."""
    assert client.get("/api/library/status").json()["needs_library_root"] is True

    saved = client.post("/api/library/root", json={"path": "~/Pictures/Truestill"}).json()
    assert saved["library_root"], saved

    after = client.get("/api/library/status").json()
    assert after["library_root"] == saved["library_root"]
    assert after["needs_library_root"] is False


def test_a_declared_root_is_stored_expanded_so_it_is_comparable(client: TestClient) -> None:
    """`~` in a stored path is a path that two pieces of code will disagree about."""
    saved = client.post("/api/library/root", json={"path": "~/Pictures/Truestill"}).json()
    assert not saved["library_root"].startswith("~"), saved
    assert saved["library_root"] == str(Path("~/Pictures/Truestill").expanduser())


def test_an_empty_declaration_is_refused_rather_than_stored(client: TestClient) -> None:
    """Storing a blank would answer the question with nothing and never ask again."""
    refused = client.post("/api/library/root", json={"path": "   "}).json()
    assert refused.get("error"), refused
    assert client.get("/api/library/status").json()["needs_library_root"] is True


def test_an_open_question_can_arrive_with_the_destination_already_filled_in(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    """⚠ **THE TWO CAN COEXIST, AND THE SCREEN MUST NOT READ ONE AS THE OTHER.**

    `organize.py` writes `path_hint.library` when a run COMPLETES, not only when it organized
    something. So a first-time user whose first run takes zero files ends with a hint and an empty
    catalog, and every part of `needs_library_root` still holds:

        library_root       None   - never declared
        files              0      - nothing was organized
        needs_library_root True   - the question is still OPEN
        library_path       set    - and `app.js` prefills `#org-dest` from it

    That prefill runs five lines before `renderFirstRunLibrary` on the same status load, so a
    visibility rule reading the FIELD would close a question nobody answered - hiding a decision
    the user was meant to make. `syncFirstRunVisibility` keys on a destination the USER named.

    This asserts the payload; the test below asserts a real run reaches this state.
    """
    landed = tmp_path / "Truestill"
    landed.mkdir()
    with Catalog(db_path) as catalog:
        catalog.set_setting(LIBRARY_PATH_HINT, str(landed))

    status = client.get("/api/library/status").json()

    assert status["files"] == 0, (
        "fixture check: the catalog must be empty for the question to be open"
    )
    assert status["library_root"] is None, "fixture check: nothing may have been declared"
    assert status["needs_library_root"] is True, "the question is not open, so nothing is at stake"
    assert status["library_path"] == str(landed), (
        "the hint did not survive, so this payload cannot prefill the destination and the "
        "coexistence this test exists to demonstrate was not reached"
    )


def test_a_run_that_organized_nothing_still_writes_the_hint(tmp_path: Path) -> None:
    """⚠ **THE PREMISE ABOVE, DRIVEN THROUGH A REAL RUN RATHER THAN HAND-MADE.**

    The test above sets the hint itself, so it proves what the payload does with that state and
    NOT that the state occurs - `ENGINEERING_STANDARD.md` §4's *"a fixture whose SUBJECT never
    entered the code path"*. This one runs `organize_run` and lets the product write it.

    ⚠ **MEDIA IS REQUIRED, and the first draft of this test got that wrong.** `organize_run`
    returns early on `if not files`, so a folder holding no photographs never reaches the hint
    write at all and a run over a text file proved the opposite of what it claimed. These are real
    JPEGs with no EXIF: found, dated nothing, and skipped by request.

    If the hint write is ever made conditional on having organized something, this goes red and
    the reachability argument in the client has to be re-made rather than quietly evaporating.
    """
    source, destination, db = tmp_path / "src", tmp_path / "Out", tmp_path / "c.sqlite"
    source.mkdir()
    for i in range(2):
        Image.new("RGB", (32, 32), (i * 40, 90, 120)).save(source / f"IMG_{i}.jpg", "JPEG")

    service.organize_run(source, destination, db, mode="copy", skip_undated=True)(
        lambda _p: None, threading.Event()
    )

    with Catalog(db) as catalog:
        organized = catalog.count()
        hint = catalog.get_setting(LIBRARY_PATH_HINT)
        declared = catalog.get_setting(LIBRARY_ROOT_KEY)

    assert organized == 0, f"fixture check: the run organized {organized} files, so it took some"
    assert declared is None, "fixture check: nothing may have been declared"
    assert hint == str(destination), (
        "a completed run did not write the library hint - the state the question-closing rule "
        "guards against is no longer reachable, and that rule's reason needs re-making"
    )
