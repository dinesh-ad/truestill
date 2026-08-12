"""Where the library lives is DECLARED, not inferred from a run that already happened. `(abx)`.

`path_hint.library` is written *after* a successful organize (`organize.py`), and read through
`take_live_path_hint`, whose own docstring says a hint "is never identity - only a convenience".
So until now the library's location was whatever the user happened to type into a field once, and
the first run was the run that decided.

`library.root` is the counterpart: a stated intent. The distinction is the whole design, and the
first test below is what holds it up.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
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
