"""The typed word is checked where the write happens, not where it is typed. `(ahe)`

⚠ **THE BAKE COULD BE STARTED WITH NO CONFIRMATION AT ALL.** :data:`CONFIRM_WORD` was shipped to
the browser inside the *preview* payload, compared in JavaScript, and **never sent back**. The
route read exactly one body key, `path`; `bake_run(path, db)` took no confirmation parameter. So
the typed field was ceremony: anything that could reach the loopback port with the session token
could rewrite every confirmed file in one POST - on the only operation in the product that runs
``-overwrite_original`` and keeps **no sidecar**, so the date the file used to carry is gone.

**Why it survived:** this was the only mutating run with no route-level test. Checked before
writing this file - `grep -rn "dates/bake" packages/truestill-app/tests/` returned nothing. The
service was covered (`test_bake_preview.py`, `test_bake_cancel.py`); the seam where a request
becomes a write was not, and that is exactly where the guard was missing.

⚠ **THE CHECK IS IN `bake_run`, NOT THE ROUTE, and that is the design.** The route is one caller;
`PROJECT_STATUS.md` §1b commits to a second one, and a guard on the caller is the shape `(afu)`
punished - a check written for one surface has to be re-written, correctly, by whoever adds the
next. `confirmation` has **no default**, the ruling `MigrationStop.kind` and `jobs.start`'s
`mutating` already carry.

⚠ **THE CENSUS, because one instance is a bug and two are a class** (`(agc)`'s shape). Six
`typedConfirm` call sites in `app.js` - migrate apply and undo, organize, organize-undo,
clean-empty, and this one. **None of the other five is enforced server-side either**, established
by `grep -rn 'confirm' server.py` (no route reads a confirmation key) and by reading every
`mutating=True` handler. This commit fixes **only the bake**, deliberately: it is the one that is
irreversible with no sidecar, while an organize move is undoable, a migrate journals before it
touches disk and clean-empty reports rather than deleting. The other five are recorded, not fixed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from PIL import Image
from starlette.testclient import TestClient
from truestill_app.service.bake import CONFIRM_WORD, NOT_CONFIRMED, bake_run
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

CONFIRMED = datetime(2011, 3, 4, 9, 15, 0)


def _library(tmp_path: Path) -> Path:
    """One confirmed photo on a real drive, at the path the `client` fixture serves."""
    db = tmp_path / "c.sqlite"
    here = tmp_path / "Everyday"
    here.mkdir()
    marker = create_marker(here, label="Everyday")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
        path = here / "Camera/2014/a.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (48, 32), "navy").save(path)
        sha = sha256_file(path)
        catalog.record_uploaded(
            source_path="/src/a.jpg",
            original_name="a.jpg",
            sha256=sha,
            copy_sha256=sha,
            perceptual=None,
            size=path.stat().st_size,
            captured_at="2014-08-16T10:46:26",
            category="Camera",
            relative="Camera/2014/a.jpg",
            drive_uuid=marker.uuid,
        )
        catalog.confirm_date(sha, CONFIRMED.isoformat(), confirmed_by="test")
    return here


# ------------------------------------------------------------------ the service, deterministically


def test_an_unconfirmed_bake_never_becomes_a_job(tmp_path: Path) -> None:
    """**The regression, at the layer that decides.**

    A refusal is a `Mapping`; a job is a callable. Asserting the TYPE rather than a response body
    is what makes this deterministic - `_start_drive_job` runs the job on another thread, so a
    test that watched the file for a write would be racing it.
    """
    here = _library(tmp_path)
    refused = bake_run(here, tmp_path / "c.sqlite", confirmation="")

    assert isinstance(refused, Mapping), "a bake with no confirmation was handed back as a job"
    assert refused["code"] == NOT_CONFIRMED
    assert not callable(refused), "nothing runnable may come back from an unconfirmed request"


def test_a_wrong_word_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """Cry-wolf half: the check must compare, not merely test for presence."""
    here = _library(tmp_path)
    refused = bake_run(here, tmp_path / "c.sqlite", confirmation="yes")

    assert isinstance(refused, Mapping)
    assert refused["code"] == NOT_CONFIRMED


def test_the_right_word_still_builds_a_job(tmp_path: Path) -> None:
    """Cry-wolf half: a correctly confirmed bake must still run, or the guard is a wall."""
    here = _library(tmp_path)
    accepted = bake_run(here, tmp_path / "c.sqlite", confirmation=CONFIRM_WORD)

    assert callable(accepted), f"a confirmed bake was refused: {accepted}"


def test_the_refusal_does_not_read_as_a_fault_of_the_drive(tmp_path: Path) -> None:
    """⚠ A missing word is the CALLER's error, so nothing may blame the user's hardware.

    `drive_label` is empty on purpose. Naming a drive here would put a working device's name on a
    programming mistake, which is the wording defect `(afa)` records one surface over.
    """
    here = _library(tmp_path)
    refused = bake_run(here, tmp_path / "c.sqlite", confirmation="")

    assert isinstance(refused, Mapping)
    assert refused["drive_label"] == "", "a caller's mistake is reported against a drive"
    assert CONFIRM_WORD in str(refused["error"]), "the refusal does not name what it wanted"


# ------------------------------------------------------------------------- the route, end to end


def test_the_route_refuses_an_unconfirmed_post_with_400(client: TestClient, tmp_path: Path) -> None:
    """**The seam that had no test, which is why this survived.**

    ⚠ **400, not the 200 every other refusal on this route takes.** `(agk)`/P24's ruling is that
    the status is spent on the outcome it describes: a UI refusal a person should read stays 200,
    a request that arrived malformed does not.
    """
    here = _library(tmp_path)
    response = client.post("/api/dates/bake/run", json={"path": str(here)})

    assert response.status_code == 400, "an unconfirmed bake was accepted by the route"
    body = response.json()
    assert body["code"] == NOT_CONFIRMED
    assert "job_id" not in body, "a refused bake must not leave a job behind"


def test_the_route_refuses_a_wrong_word(client: TestClient, tmp_path: Path) -> None:
    here = _library(tmp_path)
    response = client.post("/api/dates/bake/run", json={"path": str(here), "confirm": "set  dates"})

    assert response.status_code == 400
    assert response.json()["code"] == NOT_CONFIRMED


def test_the_route_accepts_the_typed_word(client: TestClient, tmp_path: Path) -> None:
    """Cry-wolf, end to end: the confirmed path must still reach a job."""
    here = _library(tmp_path)
    response = client.post("/api/dates/bake/run", json={"path": str(here), "confirm": CONFIRM_WORD})

    assert response.status_code == 200, response.text
    assert response.json().get("job_id"), f"a confirmed bake started no job: {response.text}"


# ------------------------------------------------------------------------------- the sending half


def test_the_browser_sends_the_word_it_collected() -> None:
    """The word used to be compared in JavaScript and never leave. `(ahe)`

    Read as text, per `test_the_rearrange_card_name.py`, because the browser lane is not part of
    the routine loop. This proves the key is on the request; it does not prove the field is
    visible, which is the browser lane's question.
    """
    script = (Path(__file__).resolve().parents[1] / "src/truestill_app/static/app.js").read_text(
        encoding="utf-8"
    )
    assert '"/api/dates/bake/run", { path, confirm }' in script, (
        "the bake request no longer carries the confirmation the user typed"
    )
    assert "startBake(path, r.confirm_word)" in script, (
        "the typed word is collected and not handed to the request"
    )
