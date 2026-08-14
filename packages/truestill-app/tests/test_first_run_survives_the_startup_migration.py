"""A genuine first run still says "No catalog yet", even though the app creates the catalog.

**The defect this exists to prevent, which is two adjacent lines in the wrong order.**
`create_app` migrates the catalog before serving, so by the time any request runs the file
exists. `library_status` inspects the catalog on **every** request. So an `inspect_catalog` that
happens after the migration can never report `WILL_CREATE` again - a genuine first run would be
told its catalog is `EMPTY`, whose message hints the user may have opened the *wrong* catalog.
That is a false accusation on a first launch, and nothing else in the suite notices it:
`test_fs_http.py` already tolerates either value (`in ("will_create", "empty")`).

`WILL_CREATE` would become unreachable for an implementation reason rather than because the
world changed. It is still true on a first run - there really was no catalog - and that is the
whole argument for keeping it reachable.

**What bounds the captured value**, because a value cached at boot that outlives the truth is
the next defect: `library_status` consults it **only when the live reading is `EMPTY`**. Any
real content makes the live reading `READY` or `EMPTY_WITH_DRIVES` and the boot value is
ignored, so it cannot survive contact with data. A user who deletes their catalog mid-session
gets `WILL_CREATE` from the live reading anyway - the same answer by a different route. Both
directions are asserted below, not just the happy one.
"""

from __future__ import annotations

from pathlib import Path

from app_support import TOKEN
from starlette.testclient import TestClient
from truestill_app import server
from truestill_core.catalog import Catalog

_HEADERS = {"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}


def _presence(app: object) -> str:
    with TestClient(app, headers=_HEADERS) as client:  # type: ignore[arg-type]
        return str(client.get("/api/library/status").json()["catalog_presence"])


def test_a_genuine_first_run_still_reports_will_create(tmp_path: Path) -> None:
    """THE GUARD. Fails if the presence capture moves after the startup migration."""
    db = tmp_path / "catalog.sqlite"
    assert not db.exists(), "the fixture must start with no catalog for this to mean anything"

    app = server.create_app(token=TOKEN, db=db)
    # BEFORE any request, deliberately. Asserting this after one would prove nothing: the first
    # request opens the catalog and creates the file itself, so the check would pass with the
    # startup migration deleted. Verified - removing it left the earlier version of this test
    # green.
    assert db.is_file(), (
        "building the app did not create the catalog, so the startup migration is not running "
        "and this test is not exercising the situation it guards"
    )

    presence = _presence(app)
    assert presence == "will_create", (
        f"a first run reported {presence!r}. The app creates the catalog before serving, so "
        "presence must be captured BEFORE that step - see `service.prepare_catalog`, where the "
        "inspect and the migrate are one function precisely so they cannot be reordered."
    )


def test_a_catalog_with_content_is_never_called_first_run(tmp_path: Path) -> None:
    """The bound, and the half that stops the boot value outliving the truth.

    Without this, "always report what boot saw" would pass the test above and be wrong forever
    after the first import.
    """
    db = tmp_path / "catalog.sqlite"
    # The app boots on an ABSENT catalog, so the boot value really is WILL_CREATE and the
    # override below is genuinely reachable. Seeding before boot would make boot presence
    # EMPTY_WITH_DRIVES, the override unreachable, and this test vacuous - which is exactly how
    # its first version passed while the bound was deleted.
    app = server.create_app(token=TOKEN, db=db)
    assert _presence(app) == "will_create", "precondition: this app booted on a first run"

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid="11111111-1111-1111-1111-111111111111", label="Archive")

    assert _presence(app) != "will_create", (
        "content landed and the SAME process still reported a first run. The boot value must be "
        "consulted only while the live reading is EMPTY, or it outlives the truth the moment "
        "anything is imported."
    )


def test_an_empty_catalog_that_predates_this_process_is_not_a_first_run(tmp_path: Path) -> None:
    """The other side of the bound: EMPTY is still reachable, and still means what it says.

    A catalog that already existed - the mistaken-working-directory case the EMPTY message is
    written for - must not be relabelled as a first run just because it is also empty.
    """
    db = tmp_path / "catalog.sqlite"
    with Catalog(db):
        pass
    assert db.is_file()

    assert _presence(server.create_app(token=TOKEN, db=db)) == "empty", (
        "an empty catalog that existed before this process started was reported as a first run. "
        "The boot capture must record what was on disk, not assume absence."
    )
