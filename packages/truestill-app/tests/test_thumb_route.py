"""`GET /api/thumb/{sha256}`: the first route that returns file-derived bytes.

**This file is the security review's other half.** The review argued the boundary from source -
`LocalGuard` wraps the whole app, `/static/` is its only exemption, identity is content and never
a path. An argument is not a guard, so every clause of it is asserted here, including the two
that would be embarrassing to get wrong: that an unauthenticated caller gets nothing, and that a
path cannot be smuggled in where a content id belongs.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from app_support import TOKEN
from PIL import Image
from starlette.testclient import TestClient
from truestill_app.server import create_app
from truestill_core.catalog import Catalog
from truestill_core.destinations.base import DestinationError
from truestill_core.drive import drive_path_hint
from truestill_core.models import DateSource

UUID = "DRIVE-1"
RELATIVE = "Camera/2014/a.jpg"


def _seed(db: Path, drive_root: Path, *, size: tuple[int, int] = (1200, 900)) -> str:
    """A one-photo library whose drive is mounted at ``drive_root``, and the photo's sha."""
    photo = drive_root / RELATIVE
    photo.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 90, 160)).save(photo, "JPEG", quality=90)
    sha = hashlib.sha256(photo.read_bytes()).hexdigest()

    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=UUID, label="Everyday")
        catalog.record_uploaded(
            source_path=str(photo),
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=photo.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative=RELATIVE,
            drive_uuid=UUID,
            date_source=DateSource.EXIF.value,
        )
        # How the app learns where a drive is mounted right now - written by verify/attach in
        # production. Without it the copy is catalogued and unreachable, which is a real state
        # (drive unplugged) and the one `test_an_unplugged_drive` covers.
        catalog.set_setting(drive_path_hint(UUID), str(drive_root))
    return sha


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, Path, str]:
    db = tmp_path / "c.sqlite"
    drive = tmp_path / "drive"
    drive.mkdir()
    return db, drive, _seed(db, drive)


# ------------------------------------------------------------------------ the happy path


def test_it_returns_a_webp_a_browser_can_render(library: tuple[Path, Path, str]) -> None:
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(response.content)) as out:
        assert out.format == "WEBP"
        assert max(out.size) == 320


def test_a_content_addressed_url_is_declared_immutable_and_private(
    library: tuple[Path, Path, str],
) -> None:
    """`immutable` because the URL names bytes that cannot change. `private` because the URL also
    carries the session token - there is no shared cache on 127.0.0.1, and the declaration should
    still be true rather than merely harmless."""
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        cache_control = client.get(f"/api/thumb/{sha}").headers["cache-control"]

    assert "immutable" in cache_control
    assert "private" in cache_control, f"a tokenised URL declared {cache_control!r}"
    assert "public" not in cache_control


def test_the_second_request_is_served_without_the_drive(library: tuple[Path, Path, str]) -> None:
    """The cache, asserted by removing what a re-render would need rather than by timing it."""
    db, drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        first = client.get(f"/api/thumb/{sha}")
        (drive / RELATIVE).unlink()
        second = client.get(f"/api/thumb/{sha}")

    assert first.status_code == second.status_code == 200
    assert second.content == first.content


# ------------------------------------------------------------------------------ the boundary


def test_without_a_token_it_serves_nothing(library: tuple[Path, Path, str]) -> None:
    """THE ONE THAT MATTERS. `LocalGuard` wraps the whole app and exempts only `/static/`; this
    asserts the new route is on the guarded side of that line rather than trusting that it is."""
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357"}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 403
    assert b"WEBP" not in response.content


def test_a_wrong_token_serves_nothing(library: tuple[Path, Path, str]) -> None:
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357"}) as client:
        response = client.get(f"/api/thumb/{sha}", params={"token": "not-the-token"})

    assert response.status_code == 403


def test_the_query_parameter_token_works_because_an_img_cannot_send_a_header(
    library: tuple[Path, Path, str],
) -> None:
    """Not a convenience: an `<img src>` has no way to set `X-Truestill-Token`, so if this ever
    stopped working the grid would go blank with a 403 per tile and no obvious cause."""
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357"}) as client:
        response = client.get(f"/api/thumb/{sha}", params={"token": TOKEN})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


def test_a_cross_origin_page_is_refused(library: tuple[Path, Path, str]) -> None:
    """A malicious page embedding `<img src="http://127.0.0.1:7357/api/thumb/...">` sends an
    `Origin`. Even holding a leaked token, it is refused before the handler runs."""
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}", headers={"origin": "https://evil.example"})

    assert response.status_code == 403


def test_a_rebinding_host_is_refused(library: tuple[Path, Path, str]) -> None:
    db, _drive, sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "evil.example", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 421


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("..%2f..%2fetc%2fpasswd", id="encoded traversal"),
        pytest.param("....//....//etc/passwd", id="doubled-dot traversal"),
        pytest.param("a" * 63, id="too short"),
        pytest.param("A" * 64, id="uppercase"),
        pytest.param("g" * 64, id="not hex"),
        pytest.param("%2e%2e%2f" + "a" * 55, id="encoded prefix"),
        pytest.param("../../../../etc/passwd", id="plain traversal"),
    ],
)
def test_nothing_that_is_not_a_content_id_reaches_a_filesystem(
    bad: str, library: tuple[Path, Path, str]
) -> None:
    """**Never 200, and never 500.** A 200 would mean bytes escaped; a 500 would mean the string
    reached something that tried to use it and blew up. 400 and 404 are both correct answers -
    which one depends on whether Starlette's router matched the path at all, and pinning that
    would be asserting Starlette's URL parsing rather than our guard."""
    db, _drive, _sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{bad}")

    assert response.status_code in {400, 404}, f"{bad!r} answered {response.status_code}"
    assert b"root:" not in response.content


def test_a_wrong_shaped_id_is_refused_by_our_guard_and_not_merely_unmatched(
    library: tuple[Path, Path, str],
) -> None:
    """The parametrized test above cannot tell our guard from Starlette's router - a traversal
    with separators never reaches the handler, so it answers 404 whether we validate or not.

    This one closes that: a 63-character hex string matches `{sha256}` and lands in the handler,
    so **400 rather than 404** is the guard speaking. Drop the shape check and it becomes a cache
    miss, then a catalog miss, then a 404 - and the test above stays green.
    """
    db, _drive, _sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{'a' * 63}")

    assert response.status_code == 400, "a malformed id reaching the handler was not refused by us"


def test_a_catalog_row_whose_relative_path_escapes_the_drive_serves_nothing(
    library: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """THE SECOND JOIN the security review named, and the only one not owned by `cache_path`.

    `copy_relative` returns a string that is joined onto a drive root. It is our own string, but
    "our own" is a property of every writer that has ever touched that row, not of the read - so
    the join goes through `check_contained`, which already owns exactly this question for the
    destination backends.

    A `DestinationError` here is a corrupt catalog, not a user state, so it is deliberately NOT
    converted into a tidy 404: it propagates. What must never happen is bytes coming back.
    """
    db, _drive, sha = library
    secret = tmp_path / "secret.jpg"
    Image.new("RGB", (60, 40), (200, 10, 10)).save(secret, "JPEG")

    with Catalog(db) as catalog:
        catalog.record_copy(
            sha256=sha,
            drive_uuid=UUID,
            relative=f"../{secret.name}",
            copy_sha256=sha,
            size=secret.stat().st_size,
        )

    app = create_app(token=TOKEN, db=db)
    with (
        TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client,
        pytest.raises(DestinationError),
    ):
        client.get(f"/api/thumb/{sha}")


# ------------------------------------------------------------- what it says when it cannot draw


def test_unknown_content_is_a_404_and_says_nothing_about_what_exists(
    library: tuple[Path, Path, str],
) -> None:
    """Unknown content and an unplugged drive answer the SAME code on purpose. A distinct one
    would let a caller enumerate which hashes the library holds."""
    db, _drive, _sha = library
    unknown = "b" * 64
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{unknown}")

    assert response.status_code == 404


def test_an_unplugged_drive_is_a_404_rather_than_a_crash(library: tuple[Path, Path, str]) -> None:
    db, drive, sha = library
    for path in sorted(drive.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    drive.rmdir()

    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 404


def test_a_file_that_is_not_an_image_says_so_instead_of_failing_silently(
    library: tuple[Path, Path, str],
) -> None:
    """415, distinct from 404, because "it is gone" and "it is there and unreadable" are different
    facts about different things - the same distinction `date_rescue` makes for sidecars."""
    db, drive, sha = library
    (drive / RELATIVE).write_bytes(b"this is not a jpeg")

    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 415
