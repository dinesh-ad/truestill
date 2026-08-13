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
    ("bad", "expected", "refused_by"),
    [
        pytest.param("a" * 63, 400, "our guard", id="too short"),
        pytest.param("A" * 64, 400, "our guard", id="uppercase"),
        pytest.param("g" * 64, 400, "our guard", id="not hex"),
        pytest.param("..%2f..%2fetc%2fpasswd", 404, "the router", id="encoded traversal"),
        pytest.param("....//....//etc/passwd", 404, "the router", id="doubled-dot traversal"),
        pytest.param("%2e%2e%2f" + "a" * 55, 404, "the router", id="encoded prefix"),
        pytest.param("", 404, "the router", id="empty"),
        pytest.param("a" * 32 + "/" + "a" * 31, 404, "the router", id="separator mid-string"),
    ],
)
def test_nothing_that_is_not_a_content_id_reaches_a_filesystem(
    bad: str, expected: int, refused_by: str, library: tuple[Path, Path, str]
) -> None:
    """Each malformed id is pinned to the EXACT code, and to which mechanism produced it.

    **THIS TEST USED TO ASSERT `status in {400, 404}` AND A MUTATION AUDIT FOUND IT UNPROVEN.**
    That disjunction is satisfied whether or not our shape check exists: strip the check and a
    63-character id stops being a 400 and becomes a cache miss, a catalog miss, then a 404 -
    still inside the allowed set, still green. An assertion loose enough to cover both the guard
    and its absence measures neither.

    The two mechanisms are genuinely different and are now separated rather than blurred. Ids
    carrying a separator never reach the handler - so those cases pin the fact that this route is
    declared `{sha256}`, ONE path segment, and not `{sha256:path}`. That is a property of our
    code, not of Starlette: the path converter is a standard footgun, and switching to it lets
    every separator case through to the handler and fails five of these. The rest land in the
    handler, where 400 is our guard speaking and any other code means it stopped speaking.

    ⚠ **A literal `../../../../etc/passwd` case was REMOVED, not forgotten.** httpx resolves it
    to `/etc/passwd` before the request is sent, so it never reached this route at all - the
    reassuring 404 came from "no route matches /etc/passwd". It was the most convincing-looking
    case here and the only one that tested nothing whatsoever. The encoded forms above are what
    an attacker actually sends and what actually arrives.
    """
    db, _drive, _sha = library
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{bad}")

    assert response.status_code == expected, (
        f"{bad!r} answered {response.status_code}, expected {expected} from {refused_by}"
    )
    assert b"root:" not in response.content


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


def test_unknown_content_is_indistinguishable_from_an_unreachable_copy(
    library: tuple[Path, Path, str],
) -> None:
    """The two must answer IDENTICALLY, because the difference is what the library holds.

    **The first version asserted only that unknown content is a 404, and a mutation audit found
    it unproven** - nothing in the code distinguishes the cases, so no mutation of existing code
    could break it, and a test nothing can break is a test that measures nothing. Worse, it was
    the wrong claim: the property is not "unknown is 404", it is "unknown and unreachable are the
    same answer". A future change that made unknown content a 410 would have kept it green while
    turning the route into a membership oracle over the library.

    So the two responses are now compared to each other. Any divergence - code, body, or header
    - fails, whichever side moves.
    """
    db, drive, present = library
    unknown = "b" * 64
    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        never_catalogued = client.get(f"/api/thumb/{unknown}")
        (drive / RELATIVE).unlink()  # catalogued, drive mounted, file gone
        catalogued_but_gone = client.get(f"/api/thumb/{present}")

    assert never_catalogued.status_code == 404
    assert catalogued_but_gone.status_code == never_catalogued.status_code, (
        "a caller can tell a catalogued hash from an unknown one by the status code"
    )
    assert catalogued_but_gone.text == never_catalogued.text, (
        f"the bodies differ, which is the same oracle in prose: "
        f"{catalogued_but_gone.text!r} vs {never_catalogued.text!r}"
    )


def test_a_mounted_drive_missing_the_file_is_not_treated_as_holding_it(
    library: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """FOUND BY A MUTATION THAT KILLED NOTHING, which is the other useful outcome of an audit.

    Deleting the `candidate.is_file()` check broke no test. Every existing case either had the
    file or had the whole drive gone - and when the drive root is gone `take_live_path_hint`
    clears the hint first, so the check was never reached. The state it exists for was untested:
    **the drive is mounted and this one file is not on it**, which is an ordinary deleted photo
    or a backup that was interrupted part way.

    Without the check the route hands `thumbnails.thumbnail` a path that is not a file. The
    honest answer is the same 404 as any other unreachable copy - never a crash, and never a
    second drive's copy silently skipped because the first drive answered first.
    """
    db, drive, sha = library
    second = tmp_path / "backup"
    (second / RELATIVE).parent.mkdir(parents=True)
    Image.new("RGB", (800, 600), (10, 160, 90)).save(second / RELATIVE, "JPEG", quality=90)

    (drive / RELATIVE).unlink()  # mounted, catalogued, file gone

    app = create_app(token=TOKEN, db=db)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        response = client.get(f"/api/thumb/{sha}")

    assert response.status_code == 404, (
        f"a mounted drive missing the file answered {response.status_code}"
    )


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
